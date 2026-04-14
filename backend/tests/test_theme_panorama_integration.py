"""Integration tests for ``/api/registry/themes/{id}/panorama``.

Covers GPT-authored test cases:

* TC-C01  : totals add up; bridge/core/peripheral sum equals concept_count
* TC-C02  : bridge concepts surface source_links back to their article
* TC-M1-02: evidence_refs on active xrels carry source_text/source_node_uuid
            (no legacy ``quote == evidence_bridge`` leftover)
* TC-M3-01: panorama returns ``role`` for every concept so UI can split
            bridge into confirmed vs candidate
* TC-M4-01: ``description_degraded`` is surfaced for every concept

These tests hit the live Flask app via ``app.test_client()`` and rely on
the JSON-backed registries already present in the dev data directory.
If the environment is empty (no themes), tests are skipped rather than
failing so CI without fixtures stays green.
"""

from __future__ import annotations

import os
from typing import Any

import pytest


def _http_get(client, path: str) -> dict[str, Any]:
    resp = client.get(path)
    assert resp.status_code == 200, f"GET {path} -> {resp.status_code} {resp.data[:300]}"
    payload = resp.get_json()
    assert payload and payload.get("success") is True, payload
    return payload["data"]


@pytest.fixture(scope="module")
def client():
    # Import late so Flask picks up the current config (env vars, etc.)
    from run import create_app

    app = create_app()
    app.testing = True
    return app.test_client()


@pytest.fixture(scope="module")
def sample_theme_id(client):
    data = _http_get(client, "/api/registry/themes")
    themes = data.get("themes", [])
    if not themes:
        pytest.skip("no themes in registry; integration test requires seeded data")
    # Prefer a theme with both concepts AND cross relations so all assertions
    # have real data to check against.
    best = None
    best_score = -1
    for theme in themes:
        try:
            pano = _http_get(client, f"/api/registry/themes/{theme['theme_id']}/panorama")
        except AssertionError:
            continue
        score = pano["stats"]["concept_count"] + pano["stats"]["relation_count"]
        if score > best_score:
            best_score = score
            best = theme["theme_id"]
    if not best:
        pytest.skip("no theme with concepts found")
    return best


# ---------------------------------------------------------------------------
# TC-C01
# ---------------------------------------------------------------------------


def test_panorama_totals_add_up(client, sample_theme_id):
    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    stats = pano["stats"]
    groups = pano["grouped_concepts"]

    assert stats["concept_count"] >= 0
    total_grouped = (
        len(groups["bridge"]) + len(groups["core"]) + len(groups["peripheral"])
    )
    assert total_grouped == stats["concept_count"], (
        "bridge + core + peripheral must equal concept_count — no silent drop"
    )

    assert len(pano["bridge_relations"]) == stats["relation_count"]

    # articles set on the panorama matches the union of source_links projects
    # across all memberships.
    article_set_from_concepts: set[str] = set()
    for group in (groups["bridge"], groups["core"], groups["peripheral"]):
        for c in group:
            for link in c.get("source_links") or []:
                name = link.get("project_name") or link.get("project_id")
                if name:
                    article_set_from_concepts.add(name)
    assert set(pano["articles"]) == article_set_from_concepts


# ---------------------------------------------------------------------------
# TC-C02 — bridge concept retains traceability back to the article
# ---------------------------------------------------------------------------


def test_bridge_concepts_have_source_links_to_articles(client, sample_theme_id):
    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    if not pano["grouped_concepts"]["bridge"]:
        pytest.skip("theme has no bridge concepts")
    for c in pano["grouped_concepts"]["bridge"]:
        assert c["source_links"], f"bridge concept {c['entry_id']} missing source_links"
        for link in c["source_links"]:
            assert link.get("project_id")
            assert link.get("concept_key")


# ---------------------------------------------------------------------------
# TC-M1-02 — active xrels have resolved evidence_refs, not legacy shape
# ---------------------------------------------------------------------------


def test_active_cross_relations_have_resolved_evidence_refs(client, sample_theme_id):
    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    bridges = pano["bridge_relations"]
    if not bridges:
        pytest.skip("no bridge relations in this theme")

    for rel in bridges:
        refs = rel.get("evidence_refs") or []
        assert refs, f"relation {rel['relation_id']} has no evidence_refs"
        for ref in refs:
            # The new schema exposes source_text (may be empty when degraded)
            # and always flags degraded explicitly. A refs entry that still
            # carries only the legacy ``quote`` field means the migration
            # script was never run.
            keys = set(ref.keys())
            has_new_shape = {"source_text", "degraded"}.issubset(keys)
            assert has_new_shape, (
                f"evidence_ref in {rel['relation_id']} is legacy shape: {ref}"
            )
            # When not degraded, source_text MUST differ from the
            # evidence_bridge — that was the original bug.
            if ref.get("degraded") is False:
                assert ref.get("source_text"), ref
                assert ref["source_text"] != rel.get("evidence_bridge", "")


# ---------------------------------------------------------------------------
# TC-M3-01 — every concept carries a role the UI can split on
# ---------------------------------------------------------------------------


def test_every_concept_has_role_field(client, sample_theme_id):
    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    for group in (pano["grouped_concepts"]["bridge"], pano["grouped_concepts"]["core"], pano["grouped_concepts"]["peripheral"]):
        for c in group:
            assert c.get("role") in {"member", "candidate"}, c


# ---------------------------------------------------------------------------
# TC-M4-01 — description_degraded is a bool on every concept
# ---------------------------------------------------------------------------


def test_description_degraded_field_present(client, sample_theme_id):
    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    for group in pano["grouped_concepts"].values():
        for c in group:
            assert "description_degraded" in c, c
            assert isinstance(c["description_degraded"], bool)


# ---------------------------------------------------------------------------
# TC-M5-d01 — panorama reflects deletions (bridge_score recomputation)
# ---------------------------------------------------------------------------


def test_panorama_surfaces_orphan_suggestions(client, sample_theme_id):
    """suggested_memberships carries concepts from shared articles not yet attached."""
    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    suggestions = pano.get("suggested_memberships")
    assert isinstance(suggestions, list)
    # Every suggestion must include overlap evidence — we never fabricate suggestions.
    for s in suggestions:
        assert s.get("entry_id")
        assert s.get("canonical_name")
        assert s.get("shared_articles"), s
        for link in s["shared_articles"]:
            assert link.get("project_id")


def test_panorama_surfaces_silent_failures_dict(client, sample_theme_id):
    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    silent = pano.get("silent_failures") or {}
    for key in (
        "concepts_missing_source_links",
        "descriptions_degraded",
        "xrels_with_no_readable_source",
        "xrels_with_partial_source",
        "bridge_without_xrels",
    ):
        assert key in silent, silent
        assert isinstance(silent[key], int)


def test_evidence_refs_carry_group_title_when_reading_structure_defines_it(client, sample_theme_id):
    """TC-M3-improvement: group_title comes from the source article's reading_structure."""
    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    if not pano["bridge_relations"]:
        pytest.skip("no bridge relations in theme")

    # At least one ref in the theme should have a non-empty group_title,
    # because dev data carries reading_structure.group_titles for most articles.
    saw_title = False
    for rel in pano["bridge_relations"]:
        for ref in rel.get("evidence_refs") or []:
            # field always present (empty when unmapped)
            assert "group_label" in ref
            assert "group_title" in ref
            if ref.get("group_title"):
                saw_title = True
    assert saw_title, (
        "expected at least one evidence_ref to resolve a reading_structure "
        "group_title; run scripts/migrate_xrel_evidence_refs.py if data is stale"
    )


def test_panorama_refreshes_after_relation_deletion(client, sample_theme_id):
    """Delete the lowest-confidence xrel and confirm it disappears from the
    panorama response. We never delete high-confidence relations — the test
    restores whatever it touched afterwards by re-creating the same record.
    """
    from app.services.registry.cross_concept_relations import (
        _load_relations,
        _save_relations,
        create_relation,
        soft_delete_relation,
    )

    pano = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
    if not pano["bridge_relations"]:
        pytest.skip("no bridge relations")

    victim = min(pano["bridge_relations"], key=lambda r: r.get("confidence", 0))
    rel_id = victim["relation_id"]
    before_count = pano["stats"]["relation_count"]
    victim_entry_ids = {victim["source_entry_id"], victim["target_entry_id"]}

    # Snapshot original fields so we can re-insert on teardown.
    snapshot = dict(victim)

    try:
        soft_delete_relation(rel_id)
        pano_after = _http_get(client, f"/api/registry/themes/{sample_theme_id}/panorama")
        assert pano_after["stats"]["relation_count"] == before_count - 1
        assert all(
            r["relation_id"] != rel_id for r in pano_after["bridge_relations"]
        )
        # bridge_score recomputation: for every affected entry, new score <= old score
        def _score_for(data, eid):
            for c in data["grouped_concepts"]["bridge"] + data["grouped_concepts"]["core"] + data["grouped_concepts"]["peripheral"]:
                if c["entry_id"] == eid:
                    return c.get("bridge_score", 0)
            return 0
        for eid in victim_entry_ids:
            assert _score_for(pano_after, eid) <= _score_for(pano, eid)
    finally:
        # Restore the relation in place (resurrection path handles dedupe).
        # The exact JSON shape is required; we write directly to the store
        # to guarantee fields like relation_id/created_at are preserved.
        store = _load_relations()
        store["relations"][rel_id] = snapshot
        _save_relations(store)
