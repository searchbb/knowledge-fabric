"""Gap #7 regression tests: theme attach/detach audit event coverage.

These tests live next to ``test_global_theme_registry_api.py`` but focus
specifically on the B-solution invariant: ``attach_concepts`` and
``detach_concepts`` must emit ``concept_attached`` / ``concept_detached``
evolution events when (and only when) there is an actual delta, with
the correct ``actor_type`` / ``source`` / ``run_id`` plumbed through.

See ``docs/superpowers/specs/2026-04-11-auto-url-pipeline-design.md`` for
the design context.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.config import Config
from app.services.registry import global_theme_registry as themes
from app.services.registry.evolution_log import _log_path


@pytest.fixture(autouse=True)
def _isolate_registry_files(tmp_path, monkeypatch):
    """Redirect Config.UPLOAD_FOLDER so each test gets a fresh JSON store.

    The theme/evolution services both persist to
    ``<UPLOAD_FOLDER>/projects/*.json``. Pointing UPLOAD_FOLDER at a
    tmp dir isolates our asserts from any real development data and
    prevents tests from polluting each other's state.
    """
    fake_root = tmp_path / "uploads"
    (fake_root / "projects").mkdir(parents=True)
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(fake_root))
    yield


def _load_events() -> list[dict]:
    path = Path(_log_path())
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("events") or []


def _create_theme() -> str:
    theme = themes.create_theme(name="Test Theme", description="", domain="tech")
    return theme["theme_id"]


class TestAttachEmitsEvent:
    def test_attach_one_concept_emits_concept_attached(self):
        theme_id = _create_theme()
        # Drain the 'created' event from theme creation so our asserts
        # below only see concept_attached.
        events_before = [e["event_type"] for e in _load_events()]
        themes.attach_concepts(theme_id, concept_entry_ids=["canon_abc"])
        events_after = _load_events()

        new_events = [
            e for e in events_after if e["event_type"] == "concept_attached"
        ]
        assert len(new_events) == 1
        event = new_events[0]
        assert event["entity_type"] == "global_theme"
        assert event["entity_id"] == theme_id
        assert event["details"]["concept_entry_ids"] == ["canon_abc"]
        # default actor when no kwargs passed
        assert event["actor_type"] == "human"
        assert event["source"] == "workspace_ui"

    def test_attach_auto_pipeline_kwargs_propagate(self):
        theme_id = _create_theme()
        themes.attach_concepts(
            theme_id,
            concept_entry_ids=["canon_abc"],
            actor_type="auto",
            actor_id="auto_pipeline",
            run_id="auto_run_test",
            source="auto_url_pipeline",
        )
        events = [
            e for e in _load_events() if e["event_type"] == "concept_attached"
        ]
        assert len(events) == 1
        assert events[0]["actor_type"] == "auto"
        assert events[0]["actor_id"] == "auto_pipeline"
        assert events[0]["run_id"] == "auto_run_test"
        assert events[0]["source"] == "auto_url_pipeline"

    def test_attach_records_only_newly_added(self):
        theme_id = _create_theme()
        # First attach two concepts
        themes.attach_concepts(theme_id, concept_entry_ids=["canon_a", "canon_b"])
        # Second call re-adds canon_a (already there) + canon_c (new)
        themes.attach_concepts(
            theme_id, concept_entry_ids=["canon_a", "canon_c"]
        )
        events = [
            e for e in _load_events() if e["event_type"] == "concept_attached"
        ]
        assert len(events) == 2
        # Second event should ONLY mention canon_c, not canon_a
        assert events[-1]["details"]["concept_entry_ids"] == ["canon_c"]

    def test_attach_idempotent_noop_emits_nothing(self):
        theme_id = _create_theme()
        themes.attach_concepts(theme_id, concept_entry_ids=["canon_a"])
        events_before = len(
            [e for e in _load_events() if e["event_type"] == "concept_attached"]
        )
        before_theme = themes.get_theme(theme_id)
        before_updated_at = before_theme["updated_at"]

        # Exactly the same payload again
        themes.attach_concepts(theme_id, concept_entry_ids=["canon_a"])

        events_after = len(
            [e for e in _load_events() if e["event_type"] == "concept_attached"]
        )
        assert events_after == events_before, "no-op attach must not emit"

        after_theme = themes.get_theme(theme_id)
        assert after_theme["updated_at"] == before_updated_at, (
            "no-op attach must not bump updated_at"
        )


class TestDetachEmitsEvent:
    def test_detach_real_removal_emits_concept_detached(self):
        theme_id = _create_theme()
        themes.attach_concepts(theme_id, concept_entry_ids=["canon_a", "canon_b"])
        themes.detach_concepts(theme_id, concept_entry_ids=["canon_a"])

        events = [
            e for e in _load_events() if e["event_type"] == "concept_detached"
        ]
        assert len(events) == 1
        assert events[0]["details"]["concept_entry_ids"] == ["canon_a"]
        assert events[0]["actor_type"] == "human"

    def test_detach_records_only_actually_removed(self):
        theme_id = _create_theme()
        themes.attach_concepts(theme_id, concept_entry_ids=["canon_a"])
        # Try to remove canon_a (attached) + canon_never (not attached)
        themes.detach_concepts(
            theme_id, concept_entry_ids=["canon_a", "canon_never"]
        )
        events = [
            e for e in _load_events() if e["event_type"] == "concept_detached"
        ]
        assert len(events) == 1
        assert events[0]["details"]["concept_entry_ids"] == ["canon_a"]
        # canon_never should NOT leak into the audit record
        assert "canon_never" not in events[0]["details"]["concept_entry_ids"]

    def test_detach_noop_emits_nothing(self):
        theme_id = _create_theme()
        before_theme = themes.get_theme(theme_id)
        before_updated_at = before_theme["updated_at"]

        themes.detach_concepts(theme_id, concept_entry_ids=["canon_never_there"])

        events = [
            e for e in _load_events() if e["event_type"] == "concept_detached"
        ]
        assert events == []

        after_theme = themes.get_theme(theme_id)
        assert after_theme["updated_at"] == before_updated_at

    def test_detach_auto_kwargs_propagate(self):
        theme_id = _create_theme()
        themes.attach_concepts(theme_id, concept_entry_ids=["canon_a"])
        themes.detach_concepts(
            theme_id,
            concept_entry_ids=["canon_a"],
            actor_type="auto",
            actor_id="auto_pipeline",
            run_id="auto_run_xyz",
            source="auto_url_pipeline",
        )
        events = [
            e for e in _load_events() if e["event_type"] == "concept_detached"
        ]
        assert len(events) == 1
        assert events[0]["actor_type"] == "auto"
        assert events[0]["run_id"] == "auto_run_xyz"
        assert events[0]["source"] == "auto_url_pipeline"
