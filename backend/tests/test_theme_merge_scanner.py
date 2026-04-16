"""Tests for the theme near-duplicate merge scanner (P1 M3).

Design: GPT consult d10c98cab0b64a56 (2026-04-16).
"""

from __future__ import annotations

from unittest.mock import patch

from app.services.auto.theme_merge_scanner import (
    AUTO_MERGE_THRESHOLD,
    REVIEW_THRESHOLD,
    MERGE_SCANNER_VERSION,
    _guardrails_pass,
    _lexical_similarity,
    _score_pair,
    _theme_passes_promotion_rules,
    promote_eligible_candidate_themes,
    scan_and_merge_candidates,
)


def _mk_theme(tid, name, status, member_ids, description=""):
    return {
        "theme_id": tid,
        "name": name,
        "status": status,
        "description": description,
        "concept_memberships": [
            {"entry_id": eid, "role": "member", "score": 0.9} for eid in member_ids
        ],
    }


def _mk_entry(eid, project_id):
    return {
        "entry_id": eid,
        "canonical_name": f"name-{eid}",
        "source_links": [{"project_id": project_id}],
    }


def test_score_pair_near_total_overlap_hits_auto_merge_band():
    """Near-total overlap + same name → auto-merge band, guardrails pass."""
    a = _mk_theme("t_a", "Multi-Agent Systems", "candidate",
                  ["e1", "e2", "e3", "e4", "e5"],
                  description="multi-agent collaboration patterns")
    b = _mk_theme("t_b", "Multi-Agent Systems", "candidate",
                  ["e1", "e2", "e3", "e4", "e5"],
                  description="multi-agent collaboration patterns")
    entries = {eid: _mk_entry(eid, "proj_shared") for eid in ["e1", "e2", "e3", "e4", "e5"]}

    score = _score_pair(a, b, entries)
    # Identical: concept_overlap=1.0, article_overlap=1.0, name=1.0, desc=1.0
    # → merge_score = 0.40 + 0.25 + 0.20 + 0.15 = 1.00
    assert score.concept_overlap == 1.0
    assert score.merge_score >= AUTO_MERGE_THRESHOLD

    ok, _ = _guardrails_pass(score)
    assert ok


def test_score_pair_partial_overlap_lands_in_mid_band():
    """~80% shared entries lands in the LLM-adjudication mid-band, not
    auto-merge — this is on purpose (GPT: conservative scoring)."""
    a = _mk_theme("t_a", "Multi-Agent Systems", "candidate",
                  ["e1", "e2", "e3", "e4", "e5"],
                  description="multi-agent architecture patterns")
    b = _mk_theme("t_b", "Multi-Agent Architecture", "candidate",
                  ["e1", "e2", "e3", "e4", "e6"],
                  description="multi-agent system architecture")
    entries = {eid: _mk_entry(eid, "proj_shared") for eid in ["e1", "e2", "e3", "e4", "e5", "e6"]}

    score = _score_pair(a, b, entries)
    assert REVIEW_THRESHOLD <= score.merge_score < AUTO_MERGE_THRESHOLD


def test_score_pair_disjoint_articles_scores_low():
    """Two articles in same broad domain but disjoint entries: low merge_score
    (this is the P1-1 test case — scoring alone won't merge them, LLM
    adjudication is needed).
    """
    a = _mk_theme("t_a", "Multi-Agent Collaboration Patterns", "candidate",
                  ["e1", "e2", "e3"],
                  description="patterns for multi-agent collaboration")
    b = _mk_theme("t_b", "Agent Engineering Architecture", "candidate",
                  ["e4", "e5", "e6"],
                  description="agent engineering skill evolution")
    entries = {
        "e1": _mk_entry("e1", "proj_a"),
        "e2": _mk_entry("e2", "proj_a"),
        "e3": _mk_entry("e3", "proj_a"),
        "e4": _mk_entry("e4", "proj_b"),
        "e5": _mk_entry("e5", "proj_b"),
        "e6": _mk_entry("e6", "proj_b"),
    }
    score = _score_pair(a, b, entries)
    assert score.concept_overlap == 0.0
    assert score.article_overlap == 0.0
    # Score driven only by name+desc lexical similarity → below REVIEW
    assert score.merge_score < REVIEW_THRESHOLD


def test_guardrails_reject_high_score_with_no_overlap():
    """Even a high merge_score must not auto-merge if overlap too weak."""
    a = _mk_theme("t_a", "Same Name", "candidate", ["e1"])
    b = _mk_theme("t_b", "Same Name", "candidate", ["e2"])
    entries = {"e1": _mk_entry("e1", "pA"), "e2": _mk_entry("e2", "pB")}
    score = _score_pair(a, b, entries)
    # Name identical → name_similarity=1.0; concept_overlap=0, article_overlap=0
    # merge_score = 0.20*1.0 + 0.15*0 = 0.20 (well below 0.88), but test the
    # guardrail semantics directly:
    score.merge_score = 0.99  # force into auto-merge band
    ok, reason = _guardrails_pass(score)
    assert not ok
    assert "overlap" in reason.lower()


def test_lexical_similarity_handles_cjk():
    """Name similarity should treat CJK substrings reasonably — not a hard
    spec, just sanity checks so a silent regex regression shows up."""
    sim = _lexical_similarity("多智能体协作与模式设计", "智能体工程与知识架构优化")
    # Shared characters: 智能体 (3 chars), 架构(1 char), 与(1 char) — non-trivial
    assert 0.2 < sim < 0.85


def test_scan_autoMerge_high_confidence_siblings():
    """Full flow: two high-overlap candidates get auto-merged, event emitted."""
    # t_a is the larger one → should win
    t_a = _mk_theme("t_a", "Multi-Agent", "candidate",
                    ["e1", "e2", "e3", "e4", "e5"],
                    description="multi-agent collaboration")
    t_b = _mk_theme("t_b", "Multi-Agent Systems", "candidate",
                    ["e1", "e2", "e3"],
                    description="multi-agent coordination")
    entries = [_mk_entry(eid, "proj_shared") for eid in ["e1", "e2", "e3", "e4", "e5"]]

    with (
        patch(
            "app.services.auto.theme_merge_scanner.themes.list_themes",
            return_value=[t_a, t_b],
        ),
        patch(
            "app.services.auto.theme_merge_scanner.registry.list_entries",
            return_value=entries,
        ),
        patch(
            "app.services.auto.theme_merge_scanner.themes.merge_themes",
            return_value={"theme_id": "t_a"},
        ) as mock_merge,
        patch(
            "app.services.auto.theme_merge_scanner.emit_event"
            if False else "app.services.registry.evolution_log.emit_event",
            return_value=None,
        ),
    ):
        result = scan_and_merge_candidates(enable_llm_adjudication=False)

    assert result["scanner_version"] == MERGE_SCANNER_VERSION
    assert result["scan_scope"]["candidate_theme_count"] == 2
    assert len(result["merged"]) == 1
    merged = result["merged"][0]
    # Winner should be the bigger one (5 members beats 3)
    assert merged["winner_theme_id"] == "t_a"
    assert merged["loser_theme_id"] == "t_b"
    mock_merge.assert_called_once_with(source_theme_id="t_b", target_theme_id="t_a")


def test_scan_dry_run_does_not_merge():
    # Identical themes (name+desc+entries) → merge_score = 1.0 auto-merge band
    t_a = _mk_theme("t_a", "Theme X", "candidate",
                    ["e1", "e2", "e3"], description="desc")
    t_b = _mk_theme("t_b", "Theme X", "candidate",
                    ["e1", "e2", "e3"], description="desc")
    entries = [_mk_entry(e, "p") for e in ["e1", "e2", "e3"]]
    with (
        patch(
            "app.services.auto.theme_merge_scanner.themes.list_themes",
            return_value=[t_a, t_b],
        ),
        patch(
            "app.services.auto.theme_merge_scanner.registry.list_entries",
            return_value=entries,
        ),
        patch(
            "app.services.auto.theme_merge_scanner.themes.merge_themes",
        ) as mock_merge,
    ):
        result = scan_and_merge_candidates(
            dry_run=True, enable_llm_adjudication=False
        )

    assert result["dry_run"] is True
    mock_merge.assert_not_called()
    # dry_run still logs what WOULD have happened (as "would_merge")
    would_merge = [a for a in result["actions"] if a["action"] == "would_merge"]
    assert len(would_merge) == 1


def test_scan_sibling_candidates_trigger_llm_adjudication_and_merge_on_MERGE():
    """P1-1 case: two same-domain candidates with no shared entries.
    merge_score < 0.72 but lexical hint triggers LLM → MERGE → merged."""
    t_a = _mk_theme("t_a", "多智能体协作与模式设计", "candidate",
                    ["e1", "e2", "e3"],
                    description="探讨多个AI智能体协作模式")
    t_b = _mk_theme("t_b", "智能体工程与知识架构优化", "candidate",
                    ["e4", "e5", "e6"],
                    description="探讨AI智能体工程架构优化")
    entries = [
        _mk_entry("e1", "proj_a"), _mk_entry("e2", "proj_a"), _mk_entry("e3", "proj_a"),
        _mk_entry("e4", "proj_b"), _mk_entry("e5", "proj_b"), _mk_entry("e6", "proj_b"),
    ]

    def fake_llm_verdict(*args, **kwargs):
        return {"verdict": "MERGE", "reason": "same domain siblings"}

    with (
        patch(
            "app.services.auto.theme_merge_scanner.themes.list_themes",
            return_value=[t_a, t_b],
        ),
        patch(
            "app.services.auto.theme_merge_scanner.registry.list_entries",
            return_value=entries,
        ),
        patch(
            "app.services.auto.theme_merge_scanner._adjudicate_via_llm",
            side_effect=fake_llm_verdict,
        ),
        patch(
            "app.services.auto.theme_merge_scanner.themes.merge_themes",
            return_value={"theme_id": "t_a"},
        ) as mock_merge,
    ):
        result = scan_and_merge_candidates()

    assert result["llm_calls_used"] == 1
    assert len(result["merged"]) == 1
    assert result["merged"][0]["action_reason"] == "llm_merge_same_domain_siblings"
    mock_merge.assert_called_once()


def test_scan_llm_UNCERTAIN_queues_for_review_not_merge():
    t_a = _mk_theme("t_a", "Similar Theme A", "candidate", ["e1"], description="x")
    t_b = _mk_theme("t_b", "Similar Theme B", "candidate", ["e2"], description="y")
    entries = [_mk_entry("e1", "p"), _mk_entry("e2", "q")]

    with (
        patch(
            "app.services.auto.theme_merge_scanner.themes.list_themes",
            return_value=[t_a, t_b],
        ),
        patch(
            "app.services.auto.theme_merge_scanner.registry.list_entries",
            return_value=entries,
        ),
        patch(
            "app.services.auto.theme_merge_scanner._adjudicate_via_llm",
            return_value={"verdict": "UNCERTAIN", "reason": "not enough signal"},
        ),
        patch(
            "app.services.auto.theme_merge_scanner.themes.merge_themes",
        ) as mock_merge,
    ):
        result = scan_and_merge_candidates()

    mock_merge.assert_not_called()
    assert len(result["review_queue"]) == 1
    assert result["review_queue"][0]["llm_reason"] == "not enough signal"


def test_scan_valid_split_llm_KEEP_SEPARATE_respected():
    """Regression for the real E2E case (GPT verdict consult, 2026-04-16):

    Two themes share an article (article_overlap=1.0) and some lexical
    name-token overlap, so the LLM adjudication path fires. But the LLM
    returns KEEP_SEPARATE because they are genuinely distinct sub-domains
    (协作模式 vs 工程实现). Scanner MUST respect this and not merge —
    otherwise we'd over-merge the real-world cases GPT warned about.
    """
    # Same shape as the real 2 themes after M1 (article 2's concepts partly
    # flowed into theme A, but most spawned theme B).
    t_a = _mk_theme(
        "t_a", "多智能体协作与模式设计", "candidate",
        ["e_a1", "e_a2", "e_a3", "e_a4", "e_a5", "e_a6", "e_a7"],
        description="探讨多个AI智能体如何通过共享状态、消息总线等架构模式协作",
    )
    t_b = _mk_theme(
        "t_b", "智能体工程与知识架构优化", "candidate",
        ["e_b1", "e_b2", "e_b3"],
        description="探讨AI代理系统的工程化设计与技能进化",
    )
    # Article overlap: t_a entries mostly from proj_1, but e_a7 from proj_2.
    # t_b entries all from proj_2 → shared_articles = {proj_2}, article_overlap=1.0.
    entries = [
        *[_mk_entry(f"e_a{i}", "proj_1") for i in range(1, 7)],
        _mk_entry("e_a7", "proj_2"),
        _mk_entry("e_b1", "proj_2"),
        _mk_entry("e_b2", "proj_2"),
        _mk_entry("e_b3", "proj_2"),
    ]

    with (
        patch(
            "app.services.auto.theme_merge_scanner.themes.list_themes",
            return_value=[t_a, t_b],
        ),
        patch(
            "app.services.auto.theme_merge_scanner.registry.list_entries",
            return_value=entries,
        ),
        patch(
            "app.services.auto.theme_merge_scanner._adjudicate_via_llm",
            return_value={
                "verdict": "KEEP_SEPARATE",
                "reason": "A 聚焦协作模式，B 聚焦工程实现，两者属于不同子域且有清晰边界",
            },
        ) as mock_llm,
        patch(
            "app.services.auto.theme_merge_scanner.themes.merge_themes",
        ) as mock_merge,
    ):
        result = scan_and_merge_candidates()

    # LLM was asked — because name_token_overlap or article_overlap triggered
    # the hint path even with merge_score well below 0.72.
    mock_llm.assert_called_once()
    # But scanner did NOT merge, and did NOT queue for review.
    mock_merge.assert_not_called()
    assert len(result["merged"]) == 0
    assert len(result["review_queue"]) == 0
    # Action should be "keep_separate" with the LLM reason preserved.
    actions = [a for a in result["actions"] if a["action"] == "keep_separate"]
    assert len(actions) == 1
    assert "不同子域" in actions[0]["reason"]


def test_scan_active_active_pair_not_eligible():
    """Two active themes: merge only via explicit human action. Scanner skips."""
    t_a = _mk_theme("t_a", "A", "active", ["e1"])
    t_b = _mk_theme("t_b", "A", "active", ["e2"])
    entries = [_mk_entry("e1", "p"), _mk_entry("e2", "q")]

    with (
        patch(
            "app.services.auto.theme_merge_scanner.themes.list_themes",
            return_value=[t_a, t_b],
        ),
        patch(
            "app.services.auto.theme_merge_scanner.registry.list_entries",
            return_value=entries,
        ),
    ):
        result = scan_and_merge_candidates(enable_llm_adjudication=False)

    assert result["scan_scope"]["eligible_pair_count"] == 0
    assert result["merged"] == []


# ---------------------------------------------------------------------------
# M2: candidate→active auto-promotion rules
# ---------------------------------------------------------------------------


def test_promotion_rule_A_distinct_articles_2_members_6():
    """Rule A: distinct_articles >= 2 AND member_count >= 6."""
    theme = _mk_theme("t", "Stable", "candidate",
                      [f"e{i}" for i in range(1, 7)])  # 6 members
    entries = {
        **{f"e{i}": _mk_entry(f"e{i}", "proj_a") for i in range(1, 4)},
        **{f"e{i}": _mk_entry(f"e{i}", "proj_b") for i in range(4, 7)},
    }
    ok, reason = _theme_passes_promotion_rules(theme, entries)
    assert ok
    assert "Rule A" in reason


def test_promotion_rule_B_distinct_articles_3_members_4():
    """Rule B: distinct_articles >= 3 AND member_count >= 4."""
    theme = _mk_theme("t", "Smaller but broad", "candidate",
                      ["e1", "e2", "e3", "e4"])
    entries = {
        "e1": _mk_entry("e1", "proj_a"),
        "e2": _mk_entry("e2", "proj_b"),
        "e3": _mk_entry("e3", "proj_c"),
        "e4": _mk_entry("e4", "proj_a"),
    }
    ok, reason = _theme_passes_promotion_rules(theme, entries)
    assert ok
    assert "Rule B" in reason


def test_promotion_rule_rejects_single_article_big_theme():
    """Critical: a 20-member theme from ONE article must NOT promote — a big
    solo article doesn't indicate cross-article stability (GPT rule)."""
    theme = _mk_theme("t", "Big solo", "candidate",
                      [f"e{i}" for i in range(20)])
    entries = {f"e{i}": _mk_entry(f"e{i}", "proj_only") for i in range(20)}
    ok, _ = _theme_passes_promotion_rules(theme, entries)
    assert not ok


def test_promote_eligible_candidate_themes_full_flow():
    eligible = _mk_theme("t_ok", "Stable candidate", "candidate",
                         [f"e{i}" for i in range(6)])
    too_small = _mk_theme("t_small", "Tiny", "candidate", ["a", "b"])
    already_active = _mk_theme("t_active", "Active already", "active",
                               [f"e{i}" for i in range(10)])
    entries = [
        *[_mk_entry(f"e{i}", "proj_a") for i in range(3)],
        *[_mk_entry(f"e{i}", "proj_b") for i in range(3, 6)],
        _mk_entry("a", "proj_solo"),
        _mk_entry("b", "proj_solo"),
    ]

    with (
        patch(
            "app.services.auto.theme_merge_scanner.themes.list_themes",
            return_value=[eligible, too_small, already_active],
        ),
        patch(
            "app.services.auto.theme_merge_scanner.registry.list_entries",
            return_value=entries,
        ),
        patch(
            "app.services.auto.theme_merge_scanner.themes.set_theme_status",
            return_value={"theme_id": "t_ok", "status": "active"},
        ) as mock_set_status,
    ):
        result = promote_eligible_candidate_themes()

    assert result["candidate_theme_count"] == 2  # the already-active is not a candidate
    promoted_ids = [p["theme_id"] for p in result["promoted"] if p.get("action") == "promoted"]
    assert promoted_ids == ["t_ok"]
    mock_set_status.assert_called_once_with("t_ok", "active")


def test_promote_eligible_dry_run_emits_would_promote_only():
    eligible = _mk_theme("t_ok", "Stable candidate", "candidate",
                         [f"e{i}" for i in range(6)])
    entries = [
        *[_mk_entry(f"e{i}", "proj_a") for i in range(3)],
        *[_mk_entry(f"e{i}", "proj_b") for i in range(3, 6)],
    ]

    with (
        patch(
            "app.services.auto.theme_merge_scanner.themes.list_themes",
            return_value=[eligible],
        ),
        patch(
            "app.services.auto.theme_merge_scanner.registry.list_entries",
            return_value=entries,
        ),
        patch(
            "app.services.auto.theme_merge_scanner.themes.set_theme_status",
        ) as mock_set_status,
    ):
        result = promote_eligible_candidate_themes(dry_run=True)

    mock_set_status.assert_not_called()
    assert result["dry_run"] is True
    would = [p for p in result["promoted"] if p.get("action") == "would_promote"]
    assert len(would) == 1
