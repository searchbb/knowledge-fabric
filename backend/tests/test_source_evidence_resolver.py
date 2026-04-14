"""Tests for :mod:`app.services.registry.source_evidence_resolver`.

Covers the GPT-authored test cases from 2026-04-14 session:

* TC-M1-01 : source_text pulls the actual graph node ``summary``
* TC-M1-03 : degraded refs do not raise and carry a reason
* TC-M5-b01: same-name disambiguation respects ``label`` component of
  ``concept_key`` (Topic:agent != Solution:agent)
* TC-E02  : two different-case names in the same graph both resolve
* TC-E04  : multi-project source_links each produce their own ref
"""

from __future__ import annotations

from unittest.mock import patch

from app.services.registry import source_evidence_resolver as sev


def _graph(*nodes: tuple[str, list[str], str, str]) -> dict:
    """Build a minimal graph_data payload. Each node: (uuid, labels, name, summary)."""
    return {
        "nodes": [
            {"uuid": uuid, "labels": list(labels), "name": name, "summary": summary}
            for (uuid, labels, name, summary) in nodes
        ],
        "edges": [],
    }


def _patch_resolution(graph_map: dict[str, dict], project_graph_map: dict[str, str]):
    """Return a context manager that patches both lookup helpers."""
    def _fake_graph_id(project_id: str) -> str:
        return project_graph_map.get(project_id, "")

    class _FakeCache:
        def get_or_load(self, gid):
            return graph_map.get(gid, {})

    return (
        patch.object(sev, "_resolve_project_graph_id", side_effect=_fake_graph_id),
        patch.object(sev, "_GraphCache", _FakeCache),
    )


# ---------------------------------------------------------------------------
# TC-M1-01
# ---------------------------------------------------------------------------


def test_source_text_uses_graph_node_summary():
    """resolve_source_evidence returns the node's summary as source_text."""
    graph = _graph(
        ("node-1", ["Problem"], "知识线性传递", "传统的知识传递方式，知识被动给予..."),
    )
    entry = {
        "entry_id": "canon_a",
        "source_links": [
            {
                "project_id": "proj_s",
                "project_name": "SimWorld",
                "concept_key": "Problem:知识线性传递",
            }
        ],
    }
    patches = _patch_resolution({"g_s": graph}, {"proj_s": "g_s"})
    with patches[0], patches[1]:
        refs = sev.resolve_source_evidence(entry)

    assert len(refs) == 1
    assert refs[0]["source_node_uuid"] == "node-1"
    assert refs[0]["source_text"].startswith("传统的知识传递方式")
    assert refs[0]["degraded"] is False
    # The resolver must never reuse evidence_bridge text — there is no bridge
    # text in this entry, so we simply check it doesn't invent one.
    assert "quote" not in refs[0]


# ---------------------------------------------------------------------------
# TC-M1-03
# ---------------------------------------------------------------------------


def test_unresolvable_ref_is_degraded_with_reason():
    """When no graph node matches we return degraded=True with a reason."""
    graph = _graph(
        ("node-1", ["Problem"], "其他概念", "其他 summary"),
    )
    entry = {
        "entry_id": "canon_a",
        "source_links": [
            {
                "project_id": "proj_s",
                "project_name": "SimWorld",
                "concept_key": "Problem:知识线性传递",
            }
        ],
    }
    patches = _patch_resolution({"g_s": graph}, {"proj_s": "g_s"})
    with patches[0], patches[1]:
        refs = sev.resolve_source_evidence(entry)

    assert len(refs) == 1
    r = refs[0]
    assert r["degraded"] is True
    assert "no graph node matches" in r["degraded_reason"]
    assert r["source_text"] == ""


def test_missing_project_id_degrades_without_raising():
    entry = {
        "entry_id": "canon_a",
        "source_links": [{"project_id": "", "concept_key": "Problem:x"}],
    }
    patches = _patch_resolution({}, {})
    with patches[0], patches[1]:
        refs = sev.resolve_source_evidence(entry)
    assert refs[0]["degraded"] is True
    assert "project_id" in refs[0]["degraded_reason"]


# ---------------------------------------------------------------------------
# TC-M5-b01 — same-name disambiguation
# ---------------------------------------------------------------------------


def test_same_name_different_labels_resolve_distinctly():
    """A Topic:agent must NOT match a Solution:agent node and vice versa."""
    graph = _graph(
        ("node-topic", ["Topic"], "agent", "Topic summary for agent"),
        ("node-solution", ["Solution"], "agent", "Solution summary for agent"),
    )
    proj = {
        "entry_id": "canon_x",
        "source_links": [
            {
                "project_id": "proj_a",
                "project_name": "Article A",
                "concept_key": "Topic:agent",
            }
        ],
    }
    proj2 = {
        "entry_id": "canon_y",
        "source_links": [
            {
                "project_id": "proj_a",
                "project_name": "Article A",
                "concept_key": "Solution:agent",
            }
        ],
    }
    patches = _patch_resolution({"g_a": graph}, {"proj_a": "g_a"})
    with patches[0], patches[1]:
        refs1 = sev.resolve_source_evidence(proj)
        refs2 = sev.resolve_source_evidence(proj2)

    assert refs1[0]["source_node_uuid"] == "node-topic"
    assert refs1[0]["source_text"] == "Topic summary for agent"
    assert refs2[0]["source_node_uuid"] == "node-solution"
    assert refs2[0]["source_text"] == "Solution summary for agent"


# ---------------------------------------------------------------------------
# TC-E02 — case-insensitive name match but label still strict
# ---------------------------------------------------------------------------


def test_case_mismatch_between_concept_key_and_node_name_resolves():
    """concept_key is lowercased on ingest; graph nodes keep original case."""
    graph = _graph(
        ("node-1", ["Technology"], "LLM/VLM", "大语言模型与视觉语言模型"),
    )
    entry = {
        "entry_id": "canon_a",
        "source_links": [
            {
                "project_id": "proj_s",
                "project_name": "SimWorld",
                # stored lowercase by concept_normalization
                "concept_key": "Technology:llm/vlm",
            }
        ],
    }
    patches = _patch_resolution({"g_s": graph}, {"proj_s": "g_s"})
    with patches[0], patches[1]:
        refs = sev.resolve_source_evidence(entry)
    assert refs[0]["degraded"] is False
    assert refs[0]["source_node_uuid"] == "node-1"


# ---------------------------------------------------------------------------
# TC-E04 — multi-project source_links each produce a ref
# ---------------------------------------------------------------------------


def test_multi_project_source_links_produce_refs_per_project():
    graph_a = _graph(("node-a", ["Topic"], "智能体", "文章 A 对智能体的定义"))
    graph_b = _graph(("node-b", ["Topic"], "智能体", "文章 B 对智能体的定义"))

    entry = {
        "entry_id": "canon_a",
        "source_links": [
            {"project_id": "proj_a", "project_name": "A", "concept_key": "Topic:智能体"},
            {"project_id": "proj_b", "project_name": "B", "concept_key": "Topic:智能体"},
        ],
    }
    patches = _patch_resolution(
        {"g_a": graph_a, "g_b": graph_b},
        {"proj_a": "g_a", "proj_b": "g_b"},
    )
    with patches[0], patches[1]:
        refs = sev.resolve_source_evidence(entry, max_refs=5)

    assert len(refs) == 2
    project_names = {r["project_name"] for r in refs}
    assert project_names == {"A", "B"}
    node_uuids = {r["source_node_uuid"] for r in refs}
    assert node_uuids == {"node-a", "node-b"}
    # All refs resolved cleanly (no degraded).
    assert all(r["degraded"] is False for r in refs)


# ---------------------------------------------------------------------------
# concept_key parsing — edge cases
# ---------------------------------------------------------------------------


def test_parse_concept_key_handles_colon_in_name():
    label, name = sev._parse_concept_key("Topic:a:b:c")
    assert label == "Topic"
    assert name == "a:b:c"


def test_parse_concept_key_missing_label_returns_name_only():
    label, name = sev._parse_concept_key("JustAName")
    assert label == ""
    assert name == "JustAName"


def test_parse_concept_key_empty_returns_empty_tuple():
    assert sev._parse_concept_key("") == ("", "")


# ---------------------------------------------------------------------------
# build_evidence_refs_for_pair — sanity check used by cross_concept_discoverer
# ---------------------------------------------------------------------------


def test_build_evidence_refs_for_pair_produces_one_ref_per_side():
    graph = _graph(
        ("node-1", ["Problem"], "知识线性传递", "Problem summary"),
        ("node-2", ["Solution"], "上下文路由器", "Solution summary"),
    )
    src = {
        "entry_id": "canon_src",
        "source_links": [
            {"project_id": "proj_s", "project_name": "SimWorld",
             "concept_key": "Problem:知识线性传递"},
        ],
    }
    tgt = {
        "entry_id": "canon_tgt",
        "source_links": [
            {"project_id": "proj_s", "project_name": "SimWorld",
             "concept_key": "Solution:上下文路由器"},
        ],
    }
    patches = _patch_resolution({"g_s": graph}, {"proj_s": "g_s"})
    with patches[0], patches[1]:
        refs = sev.build_evidence_refs_for_pair(source_entry=src, target_entry=tgt)
    assert len(refs) == 2
    assert {r["entry_id"] for r in refs} == {"canon_src", "canon_tgt"}
    assert {r["source_text"] for r in refs} == {"Problem summary", "Solution summary"}


# ---------------------------------------------------------------------------
# New field: group_title / group_label (M3 improvement 2026-04-14)
# ---------------------------------------------------------------------------


def test_group_title_is_populated_from_reading_structure():
    """evidence_refs expose the human-readable section from reading_structure."""
    graph = _graph(
        ("node-1", ["Problem"], "知识线性传递", "Problem summary"),
    )
    entry = {
        "entry_id": "canon_a",
        "source_links": [
            {"project_id": "proj_s", "project_name": "SimWorld",
             "concept_key": "Problem:知识线性传递"},
        ],
    }
    with patch.object(sev, "_resolve_project_graph_id", return_value="g_s"), \
         patch.object(sev, "_GraphCache", lambda: type("C", (), {"get_or_load": lambda self, gid: graph})()), \
         patch.object(sev, "_resolve_project_group_titles", return_value={"Problem": "核心问题"}):
        refs = sev.resolve_source_evidence(entry)

    assert refs[0]["group_label"] == "Problem"
    assert refs[0]["group_title"] == "核心问题"


def test_suggestion_relevance_demotes_trivial_quantitative_evidence():
    """GPT must-fix round 2: pure number/date Evidence/Example demote to low."""
    from app.services.registry.global_theme_registry import _classify_suggestion_relevance

    assert _classify_suggestion_relevance({"concept_type": "Evidence", "canonical_name": "100万行代码"}) == "low"
    assert _classify_suggestion_relevance({"concept_type": "Example", "canonical_name": "2020 年夏天正式上线"}) == "low"
    assert _classify_suggestion_relevance({"concept_type": "Metric", "canonical_name": "93% 代码贡献率"}) == "low"
    # Substantive evidence stays high (long description name even with digits)
    assert _classify_suggestion_relevance({"concept_type": "Evidence", "canonical_name": "DeepSeek-Prover-V2的决策反复横跳，标准差几乎和均值一样大"}) == "high"
    # Non-evidence types never demote regardless of digits
    assert _classify_suggestion_relevance({"concept_type": "Problem", "canonical_name": "3 层上下文架构"}) == "high"
    # No digits → always high
    assert _classify_suggestion_relevance({"concept_type": "Evidence", "canonical_name": "代码片段示例"}) == "high"


def test_group_title_is_empty_when_reading_structure_missing():
    """Missing reading_structure → group_title defaults to empty string."""
    graph = _graph(
        ("node-1", ["Problem"], "x", "summary"),
    )
    entry = {
        "entry_id": "canon_a",
        "source_links": [
            {"project_id": "proj_s", "project_name": "p", "concept_key": "Problem:x"},
        ],
    }
    with patch.object(sev, "_resolve_project_graph_id", return_value="g_s"), \
         patch.object(sev, "_GraphCache", lambda: type("C", (), {"get_or_load": lambda self, gid: graph})()), \
         patch.object(sev, "_resolve_project_group_titles", return_value={}):
        refs = sev.resolve_source_evidence(entry)

    assert refs[0]["group_label"] == "Problem"  # still set from node.labels
    assert refs[0]["group_title"] == ""  # no mapping available
