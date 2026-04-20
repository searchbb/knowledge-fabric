"""Provenance fields on cross-concept relations (P4/step 1 of Discover V2).

For the discover pipeline to be auditable across retries and A/B cutovers,
every relation it creates needs to carry:

- ``run_id`` — the discover job's origin_run_id (or the job_id if absent).
  Lets us answer "which run introduced this relation?" without digging
  through evolution_log events.
- ``job_id`` — the specific DiscoverJob that produced it (None for manual
  creations). Lets us evaluate a single job's output, re-run and diff.

Previously ``create_relation`` accepted ``run_id`` but only forwarded it
to the evolution_log emitter; the stored entry itself had no provenance
pointer. These tests pin the new behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def isolated_relations(tmp_path: Path, monkeypatch):
    from app import config as config_module

    uploads = tmp_path / "uploads"
    (uploads / "projects").mkdir(parents=True)
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))
    return uploads / "projects" / "cross_concept_relations.json"


class TestRunIdPersisted:
    def test_run_id_is_stored_on_new_relation(self, isolated_relations):
        from app.services.registry.cross_concept_relations import create_relation

        rel = create_relation(
            source_entry_id="canon_a",
            target_entry_id="canon_b",
            relation_type="design_inspiration",
            reason="test",
            confidence=0.8,
            source="auto",
            run_id="auto_run_abc",
        )
        assert rel["run_id"] == "auto_run_abc"

        on_disk = json.loads(isolated_relations.read_text())
        saved = next(iter(on_disk["relations"].values()))
        assert saved["run_id"] == "auto_run_abc"

    def test_run_id_defaults_to_empty_string_when_absent(self, isolated_relations):
        from app.services.registry.cross_concept_relations import create_relation

        rel = create_relation(
            source_entry_id="canon_a",
            target_entry_id="canon_b",
            relation_type="design_inspiration",
            reason="manual entry, no run",
            source="manual",
        )
        # Empty-string is fine — distinguishes "no provenance" from
        # "not populated by the writer".
        assert rel["run_id"] == ""


class TestJobIdPersisted:
    def test_job_id_is_stored_when_provided(self, isolated_relations):
        from app.services.registry.cross_concept_relations import create_relation

        rel = create_relation(
            source_entry_id="canon_a",
            target_entry_id="canon_b",
            relation_type="problem_solution",
            reason="test",
            source="auto",
            run_id="auto_run_x",
            job_id="djob_abc123",
        )
        assert rel["job_id"] == "djob_abc123"

    def test_job_id_is_null_for_manual_creations(self, isolated_relations):
        from app.services.registry.cross_concept_relations import create_relation

        rel = create_relation(
            source_entry_id="canon_a",
            target_entry_id="canon_b",
            relation_type="design_inspiration",
            reason="human created",
            source="manual",
        )
        # Distinct from empty-string run_id: None means "never came
        # from a discover job" (e.g. human review).
        assert rel["job_id"] is None


class TestResurrectionKeepsProvenance:
    """When a soft-deleted relation is resurrected by a new discover run,
    the new run_id / job_id should overwrite the old provenance so the
    record reflects who most recently validated this relation."""

    def test_resurrected_relation_updates_run_id_and_job_id(self, isolated_relations):
        from app.services.registry.cross_concept_relations import (
            create_relation,
            soft_delete_relation,
        )

        rel = create_relation(
            source_entry_id="canon_a",
            target_entry_id="canon_b",
            relation_type="design_inspiration",
            reason="original",
            source="auto",
            run_id="first_run",
            job_id="djob_first",
        )
        soft_delete_relation(rel["relation_id"], actor_id="u")

        rel2 = create_relation(
            source_entry_id="canon_a",
            target_entry_id="canon_b",
            relation_type="design_inspiration",
            reason="revived",
            source="auto",
            run_id="second_run",
            job_id="djob_second",
        )
        assert rel2["relation_id"] == rel["relation_id"]  # same record
        assert rel2["run_id"] == "second_run"
        assert rel2["job_id"] == "djob_second"
