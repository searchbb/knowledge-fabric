"""Dry-run replay of proj_39a354d2c50e against v3 AutoThemeProposer.

Runs with a real LLM call so we can see how the new null-first prompt
changes LLM behavior, but mocks attach_concepts / create_theme so nothing
writes to the real theme registry or evolution log.

Usage (from backend/ dir with the worktree venv):
    python scripts/replay_proj_39a354d2c50e.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

# Make `app.*` importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.auto.theme_proposer import AutoThemeProposer, PROPOSER_VERSION

# Real data lives in the main repo uploads dir (shared across worktrees via
# absolute path — worktrees don't clone uploads/).
UPLOADS_ROOT = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/uploads/projects")
PROJECT_ID = "proj_39a354d2c50e"


def load_concepts() -> list[dict]:
    """Read the 20 accepted canonical concepts from project.json. Fabricate
    canonical ids that match the evolution_log record so the LLM prompt sees
    real-looking inputs."""
    project = json.loads((UPLOADS_ROOT / PROJECT_ID / "project.json").read_text())
    items = project["concept_decisions"]["items"]

    # concept_decisions keys look like "Solution:模型外显"; split type/name.
    concepts = []
    for key, item in items.items():
        if item.get("status") != "accepted":
            continue
        concept_type = key.split(":", 1)[0]
        name = item["canonical_name"]
        concepts.append({
            "entry_id": f"canon_replay_{len(concepts):02d}",  # synthetic id
            "canonical_name": name,
            "concept_type": concept_type,
        })
    return concepts


def load_active_themes() -> list[dict]:
    """Read the real global themes (status=active) that were visible to the
    v2 run, so the LLM sees the same menu."""
    themes_path = UPLOADS_ROOT / "global_themes.json"
    data = json.loads(themes_path.read_text())
    themes_dict = data.get("themes", {})
    return [
        t for t in themes_dict.values()
        if t.get("status") == "active"
    ]


def fmt_conf(c: float) -> str:
    return f"{c:.2f}"


def main() -> None:
    concepts = load_concepts()
    active_themes = load_active_themes()

    print(f"=== v3 replay · {PROJECT_ID} (得到精选) ===")
    print(f"proposer_version: {PROPOSER_VERSION}")
    print(f"{len(concepts)} concepts loaded, {len(active_themes)} active themes")
    print()
    print("Concepts:")
    for c in concepts:
        print(f"  [{c['concept_type']:10s}] {c['canonical_name']}")
    print()
    print("Themes in scope:")
    for t in active_themes:
        print(f"  - {t['theme_id']}: {t['name']}")
    print()

    # Mock registry + write sinks so we don't corrupt production data.
    # - registry.list_entries → return synthetic entries matching our concepts
    # - themes.list_themes → return real active themes
    # - themes.attach_concepts → log the call, don't write
    # - themes.create_theme (inside _propose_new_theme_candidate) → fake
    fake_entries = [
        {"entry_id": c["entry_id"], "canonical_name": c["canonical_name"],
         "concept_type": c["concept_type"]}
        for c in concepts
    ]

    attach_log: list[dict] = []
    def _mock_attach(theme_id, entry_ids, *, role, score, **kw):
        attach_log.append({
            "theme_id": theme_id,
            "entry_ids": list(entry_ids),
            "role": role,
            "score": score,
        })
        return None

    created_themes: list[dict] = []
    def _mock_create_theme(*, name, description="", status="active",
                           source="user", keywords=None):
        t = {
            "theme_id": f"gtheme_REPLAY_{len(created_themes):02d}",
            "name": name, "description": description,
            "status": status, "source": source,
            "keywords": keywords or [],
            "concept_memberships": [],
        }
        created_themes.append(t)
        return t

    proposer = AutoThemeProposer()

    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None: (
            active_themes if status in (None, "active") else []
        ),
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts",
        side_effect=_mock_attach,
    ), patch(
        "app.services.auto.theme_proposer.themes.create_theme",
        side_effect=_mock_create_theme,
    ):
        result = proposer.process(
            project_id=PROJECT_ID,
            project_name="得到精选",
            new_canonical_ids=[c["entry_id"] for c in concepts],
            run_id="replay_v3_dryrun",
            article_title="得到精选",
        )

    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"action: {result.action}")
    print(f"reason: {result.reason}")
    print()

    audit = result.audit
    print("Audit signals:")
    keys_of_interest = [
        "article_level_ood", "max_confidence",
        "member_count", "candidate_count",
        "effective_orphan_count", "orphan_ratio", "core_orphan_count",
        "ood_max_confidence_cutoff", "classification_source",
        "decision", "llm_error",
    ]
    for k in keys_of_interest:
        if k in audit:
            print(f"  {k}: {audit[k]}")
    print()

    name_by_id = {c["entry_id"]: c["canonical_name"] for c in concepts}
    theme_name_by_id = {t["theme_id"]: t["name"] for t in active_themes}

    # Show LLM assignments (what the LLM itself said this time)
    if result.assignments:
        print(f"LLM assignments ({len(result.assignments)}):")
        for a in result.assignments:
            role = a.get("role", "?")
            conf = a.get("confidence", 0)
            tid = a.get("theme_id", "")
            tname = theme_name_by_id.get(tid, tid)
            cid = a.get("entry_id", "")
            cname = name_by_id.get(cid, cid)
            print(f"  [{role:9s} {fmt_conf(conf)}] {cname:40s} → {tname}")
            reason = a.get("reason", "")
            if reason:
                print(f"             reason: {reason}")
    else:
        print("LLM assignments: (empty — article-level OOD path)")
    print()

    # Show what WOULD have been attached
    if attach_log:
        print(f"Would attach ({len(attach_log)} calls):")
        for att in attach_log:
            tname = theme_name_by_id.get(att["theme_id"], att["theme_id"])
            for eid in att["entry_ids"]:
                cname = name_by_id.get(eid, eid)
                print(f"  {cname} → {tname} (role={att['role']}, score={fmt_conf(att['score'])})")
    else:
        print("Would attach: (nothing — OOD path skipped attaches)")
    print()

    # Show new theme proposal, if any
    if result.new_candidate_theme:
        nt = result.new_candidate_theme
        print("NEW THEME proposed:")
        print(f"  theme_id: {nt.get('theme_id')}")
        print(f"  name: {nt.get('name')}")
        print(f"  description: {nt.get('description', '')}")
        print(f"  attached_count: {nt.get('attached_count', '?')}")
    else:
        print("NEW THEME: none")
    print()

    # v2 baseline for comparison (from the audit stored in evolution_log)
    print("=" * 60)
    print("v2 baseline (historical, from evolution_log auto_run_98dcb3ac45):")
    print("  action: classified")
    print("  member_count: 0")
    print("  candidate_count: 16 (silent absorb into 4 AI/tech themes)")
    print("  orphan_count: 4")
    print("  orphan_ratio: 4/20 = 0.20 (below 0.6 → no new theme)")
    print("  new_theme_proposed: NO")


if __name__ == "__main__":
    main()
