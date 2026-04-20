"""Tests for the ``load_existing_dedupe_keys`` batch helper.

Added in P1.5 of the Discover V2 plan. Stage 1 candidate recall was
issuing thousands of ``has_dedupe_key`` calls per discover run, each
re-reading the relations JSON and full-scanning it. The batch helper
returns a single set so the caller can turn that into O(1) membership
checks after one read. These tests lock in:

- the batch helper returns the same keys ``has_dedupe_key`` would say
  yes to (so callers can swap without changing semantics),
- ``active_only=True`` filters out deleted relations (matching
  ``has_dedupe_key``'s flag),
- disk I/O actually drops when the batch helper replaces the per-call
  check (this is the point of the optimisation — without this test a
  regression could re-introduce the old N×O(disk) pattern silently).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def isolated_relations(tmp_path: Path, monkeypatch):
    """Point ``Config.UPLOAD_FOLDER`` at a scratch dir so the test
    doesn't touch the real ``data/projects/cross_concept_relations.json``.
    """
    from app import config as config_module

    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))
    (uploads / "projects").mkdir()
    return uploads / "projects" / "cross_concept_relations.json"


def _seed(relations_file: Path, rels: list[dict]):
    """Write a ``cross_concept_relations.json`` with the given rel list."""
    payload = {"version": 1, "relations": {r["relation_id"]: r for r in rels}}
    relations_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def _rel(source: str, rtype: str, target: str, *, status: str = "active") -> dict:
    return {
        "relation_id": f"crel_{source}_{rtype}_{target}",
        "source_entry_id": source,
        "target_entry_id": target,
        "relation_type": rtype,
        "dedupe_key": f"{source}|{rtype}|{target}",
        "status": status,
    }


class TestLoadExistingDedupeKeys:
    def test_empty_store_returns_empty_set(self, isolated_relations):
        from app.services.registry.cross_concept_relations import (
            load_existing_dedupe_keys,
        )

        # No file on disk is legit — just means no relations yet.
        assert load_existing_dedupe_keys() == set()

    def test_returns_every_dedupe_key_by_default(self, isolated_relations):
        _seed(
            isolated_relations,
            [
                _rel("canon_a", "design_inspiration", "canon_b"),
                _rel("canon_b", "problem_solution", "canon_c"),
                _rel("canon_a", "contrast_reference", "canon_d", status="deleted"),
            ],
        )
        from app.services.registry.cross_concept_relations import (
            load_existing_dedupe_keys,
        )

        keys = load_existing_dedupe_keys()
        # Default includes deleted — matches has_dedupe_key's default.
        assert keys == {
            "canon_a|design_inspiration|canon_b",
            "canon_b|problem_solution|canon_c",
            "canon_a|contrast_reference|canon_d",
        }

    def test_active_only_excludes_deleted(self, isolated_relations):
        _seed(
            isolated_relations,
            [
                _rel("canon_a", "design_inspiration", "canon_b"),
                _rel("canon_a", "contrast_reference", "canon_d", status="deleted"),
            ],
        )
        from app.services.registry.cross_concept_relations import (
            load_existing_dedupe_keys,
        )

        keys = load_existing_dedupe_keys(active_only=True)
        assert keys == {"canon_a|design_inspiration|canon_b"}

    def test_agrees_with_has_dedupe_key_per_row(self, isolated_relations):
        """For every key in the batch result, the per-key API agrees — and
        vice versa. Guarantees we can swap the two without drift.
        """
        rels = [
            _rel("a", "design_inspiration", "b"),
            _rel("a", "problem_solution", "c"),
            _rel("b", "pattern_reuse", "c", status="deleted"),
        ]
        _seed(isolated_relations, rels)
        from app.services.registry.cross_concept_relations import (
            has_dedupe_key,
            load_existing_dedupe_keys,
        )

        batch_default = load_existing_dedupe_keys()
        for r in rels:
            assert has_dedupe_key(r["dedupe_key"]) is (r["dedupe_key"] in batch_default)

        batch_active = load_existing_dedupe_keys(active_only=True)
        for r in rels:
            assert (
                has_dedupe_key(r["dedupe_key"], active_only=True)
                is (r["dedupe_key"] in batch_active)
            )


class TestDiskReadCountRegression:
    """The whole point of this helper is ONE disk read. If someone
    refactors the internals and loses that property, the optimisation
    silently regresses. Pin it here.
    """

    def test_batch_helper_reads_relations_file_once(self, isolated_relations):
        _seed(
            isolated_relations,
            [_rel(f"a{i}", "design_inspiration", f"b{i}") for i in range(10)],
        )
        from app.services.registry import cross_concept_relations as mod

        with patch.object(
            mod, "_load_relations", wraps=mod._load_relations
        ) as spy:
            mod.load_existing_dedupe_keys()
        assert spy.call_count == 1

    def test_per_key_api_reads_file_every_call(self, isolated_relations):
        """Sanity: confirm has_dedupe_key IS the expensive one. This test
        exists so the 'batch helper saves N disk reads' story is grounded
        in measurable behaviour, not folklore."""
        _seed(
            isolated_relations,
            [_rel("a", "design_inspiration", "b")],
        )
        from app.services.registry import cross_concept_relations as mod

        with patch.object(
            mod, "_load_relations", wraps=mod._load_relations
        ) as spy:
            for i in range(5):
                mod.has_dedupe_key(f"canon_x|rt|canon_y{i}")
        assert spy.call_count == 5
