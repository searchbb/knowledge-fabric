from app.models.project import Project, ProjectStatus
from app.services.reading_structure_extractor import (
    DEFAULT_GROUP_TITLES,
    ReadingStructureExtractor,
)


class FakeLLMClient:
    def __init__(self, payload):
        self.payload = payload

    def chat_json(self, messages, temperature=0.2, max_tokens=1600):
        return self.payload


def test_reading_structure_extractor_normalizes_titles_and_fills_group_defaults():
    extractor = ReadingStructureExtractor(
        llm_client=FakeLLMClient(
            {
                "title": "  Agent 创业护城河判断  ",
                "summary": "  讨论 harness 与 environment 的价值分工。 ",
                "problem": {"title": "确定性鸿沟", "summary": " 商业世界要确定性结果。 "},
                "solution": {"title": "做深 Harness 控制层", "summary": " 先构建控制平面。 "},
                "architecture": {"title": "三阶段演进路径", "summary": " 从模型到环境。 "},
                "group_titles": {
                    "Technology": "关键技术",
                    "Metric": "评估信号",
                },
            }
        )
    )

    result = extractor.extract(
        project_name="Harness vs Environment 创业护城河",
        document_text="示例正文",
        analysis_summary="示例摘要",
        ontology={},
        graph_data={"nodes": [], "edges": []},
        simulation_requirement="示例需求",
    )

    assert result["title"] == "Agent 创业护城河判断"
    assert result["summary"] == "讨论 harness 与 environment 的价值分工。"
    assert result["problem"]["title"] == "确定性鸿沟"
    assert result["solution"]["title"] == "做深 Harness 控制层"
    assert result["architecture"]["title"] == "三阶段演进路径"
    assert result["group_titles"]["Technology"] == "关键技术"
    assert result["group_titles"]["Metric"] == "评估信号"
    assert result["group_titles"]["Layer"] == DEFAULT_GROUP_TITLES["Layer"]
    assert result["node_order_hints"] == {}


def test_reading_structure_extractor_raises_when_llm_fails():
    import pytest

    class FailingLLMClient:
        def chat_json(self, messages, temperature=0.2, max_tokens=1600):
            raise RuntimeError("boom")

    extractor = ReadingStructureExtractor(llm_client=FailingLLMClient())
    with pytest.raises(RuntimeError, match="boom"):
        extractor.extract(
            project_name="新文章项目",
            document_text="CLI 再次成为 Agent 的执行界面。",
            analysis_summary="一段摘要",
            ontology={},
            graph_data={"nodes": [], "edges": []},
            simulation_requirement="示例需求",
        )


def test_reading_structure_extractor_uses_generic_titles_for_missing_llm_stages():
    extractor = ReadingStructureExtractor(
        llm_client=FakeLLMClient(
            {
                "title": "CLI 文章",
                "summary": "解释 CLI 的回归。",
                "problem": {"title": "核心问题", "summary": ""},
                "solution": {"title": "核心方案", "summary": ""},
                "architecture": {"title": "结构路径", "summary": ""},
                "group_titles": {},
            }
        )
    )

    result = extractor.extract(
        project_name="CLI 项目",
        document_text="先讨论自动化断层，再介绍控制面方案，最后展开协议桥接。",
        analysis_summary="示例摘要",
        ontology={},
        graph_data={"nodes": [], "edges": []},
        simulation_requirement="示例需求",
    )

    assert result["title"] == "CLI 文章"
    assert result["problem"]["title"] == "核心问题"
    assert result["solution"]["title"] == "核心方案"
    assert result["architecture"]["title"] == "结构路径"
    assert result["group_titles"] == DEFAULT_GROUP_TITLES


def test_reading_structure_extractor_builds_node_order_hints_from_document_text():
    extractor = ReadingStructureExtractor(
        llm_client=FakeLLMClient(
            {
                "title": "文章主线",
                "summary": "摘要",
                "problem": {"title": "问题", "summary": ""},
                "solution": {"title": "方案", "summary": ""},
                "architecture": {"title": "结构", "summary": ""},
                "group_titles": {},
            }
        )
    )

    result = extractor.extract(
        project_name="OpenClaw 项目",
        document_text="先介绍 OpenClaw，再谈 Hook 机制，最后比较 DuckDB 与 SQLite。",
        analysis_summary="示例摘要",
        ontology={},
        graph_data={
            "nodes": [
                {"uuid": "n1", "name": "DuckDB"},
                {"uuid": "n2", "name": "OpenClaw"},
                {"uuid": "n3", "name": "Hook 机制"},
                {"uuid": "n4", "name": "SQLite"},
            ],
            "edges": [],
        },
        simulation_requirement="示例需求",
    )

    assert result["node_order_hints"] == {
        "n2": 0,
        "n3": 1,
        "n1": 2,
        "n4": 3,
    }


def test_build_graph_digest_prefers_connected_labeled_nodes():
    extractor = ReadingStructureExtractor(llm_client=FakeLLMClient({}))

    digest = extractor._build_graph_digest(
        {
            "nodes": [
                {"uuid": "n1", "name": "主问题", "labels": ["Problem"]},
                {"uuid": "n2", "name": "主方案", "labels": ["Solution"]},
                {"uuid": "n3", "name": "孤立技术", "labels": ["Technology"]},
                {"uuid": "n4", "name": "组织名", "labels": []},
            ],
            "edges": [
                {
                    "uuid": "e1",
                    "name": "SOLVES",
                    "fact_type": "SOLVES",
                    "source_node_uuid": "n2",
                    "target_node_uuid": "n1",
                }
            ],
            "node_count": 4,
            "edge_count": 1,
        }
    )

    assert "backbone_Problem: 主问题" in digest
    assert "backbone_Solution: 主方案" in digest
    assert "孤立技术" not in digest
    assert "组织名" not in digest


def test_build_graph_digest_adds_backbone_fallback_when_core_chain_is_sparse():
    extractor = ReadingStructureExtractor(llm_client=FakeLLMClient({}))

    digest = extractor._build_graph_digest(
        {
            "nodes": [
                {"uuid": "n1", "name": "关键机制", "labels": ["Mechanism"]},
                {"uuid": "n2", "name": "技术底座", "labels": ["Technology"]},
            ],
            "edges": [
                {
                    "uuid": "e1",
                    "name": "USES_TECHNOLOGY",
                    "fact_type": "USES_TECHNOLOGY",
                    "source_node_uuid": "n1",
                    "target_node_uuid": "n2",
                }
            ],
            "node_count": 2,
            "edge_count": 1,
        }
    )

    assert "backbone_fallback: 关键机制、技术底座" in digest


def test_project_roundtrip_preserves_reading_structure():
    project = Project(
        project_id="proj_test",
        name="Test",
        status=ProjectStatus.GRAPH_COMPLETED,
        created_at="2026-04-03T00:00:00",
        updated_at="2026-04-03T00:00:00",
        ontology_metadata={"generation_mode": "fallback"},
        reading_structure={
            "title": "文章主线",
            "problem": {"title": "核心问题", "summary": ""},
        },
    )

    restored = Project.from_dict(project.to_dict())

    assert restored.reading_structure == {
        "title": "文章主线",
        "problem": {"title": "核心问题", "summary": ""},
    }
    assert restored.ontology_metadata == {"generation_mode": "fallback"}
