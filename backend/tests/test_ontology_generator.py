import pytest
from app.services.ontology_generator import OntologyGenerator


class _RateLimitedLLMClient:
    def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        raise RuntimeError("429 usage limit exceeded")


class _FatalLLMClient:
    def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        raise RuntimeError("authentication failed")


class _MalformedJsonLLMClient:
    def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        raise ValueError("LLM返回的JSON格式无效: {\"entity_types\": [")


class _MisnestedOntologyLLMClient:
    def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        return {
            "entity_types": [
                {
                    "name": "Example",
                    "description": "案例",
                    "attributes": [
                        {"name": "scenario", "type": "text", "description": "场景"},
                        "写周报、翻天气",
                    ],
                    "analysis_summary": "从错位字段里恢复的摘要",
                    "edge_types": [
                        {
                            "name": "HAS_EXAMPLE",
                            "description": "案例验证",
                            "source_targets": [
                                {"source": "Solution", "target": "Example"},
                            ],
                            "attributes": [],
                        },
                        {
                            "name": "SOLVES",
                            "description": "解决问题",
                            "source_targets": [
                                {"source": "Solution", "target": "Problem"},
                            ],
                            "attributes": [],
                        },
                    ],
                    "examples": ["真实案例"],
                },
                {
                    "name": "Solution",
                    "description": "方案",
                    "attributes": [{"name": "approach", "type": "text", "description": "方法"}],
                    "examples": ["自动化闭环"],
                },
                {
                    "name": "Problem",
                    "description": "问题",
                    "attributes": [{"name": "severity", "type": "text", "description": "严重度"}],
                    "examples": ["人工维护成本高"],
                },
                {
                    "name": "Topic",
                    "description": "主题",
                    "attributes": [{"name": "domain", "type": "text", "description": "领域"}],
                    "examples": ["Agent 自动化"],
                },
                {
                    "name": "Technology",
                    "description": "技术",
                    "attributes": [{"name": "category", "type": "text", "description": "类别"}],
                    "examples": ["Hermes"],
                },
            ],
            "edge_types": [],
            "analysis_summary": "",
        }


def test_ontology_generator_raises_on_rate_limit():
    """Rate limit errors should propagate, not be swallowed by fallback."""
    generator = OntologyGenerator(llm_client=_RateLimitedLLMClient())

    with pytest.raises(RuntimeError, match="429"):
        generator.generate(
            document_texts=["# CLI 工具演进\n\n## 背景\n\n## 架构方案\n\n## 效果"],
            simulation_requirement="为知识工作台第一阶段生成本体",
        )


def test_ontology_generator_raises_on_malformed_json():
    """Malformed JSON errors should propagate, not be swallowed by fallback."""
    generator = OntologyGenerator(llm_client=_MalformedJsonLLMClient())

    with pytest.raises(ValueError, match="JSON格式无效"):
        generator.generate(
            document_texts=["# CLI 工具演进\n\n## 背景\n\n## 架构方案\n\n## 效果"],
            simulation_requirement="为知识工作台第一阶段生成本体",
        )


def test_ontology_generator_raises_on_fatal_errors():
    """Fatal errors (auth, etc.) should propagate."""
    generator = OntologyGenerator(llm_client=_FatalLLMClient())

    with pytest.raises(RuntimeError, match="authentication failed"):
        generator.generate(
            document_texts=["# 示例文章"],
            simulation_requirement="生成本体",
        )


def test_ontology_generator_recovers_misnested_edge_types_and_sanitizes_attributes():
    generator = OntologyGenerator(llm_client=_MisnestedOntologyLLMClient())

    result = generator.generate(
        document_texts=["# Hermes\n\n## 问题\n\n## 方案"],
        simulation_requirement="生成本体",
    )

    assert result["analysis_summary"] == "从错位字段里恢复的摘要"
    assert [edge["name"] for edge in result["edge_types"]] == ["SOLVES", "HAS_EXAMPLE"]
    example = next(entity for entity in result["entity_types"] if entity["name"] == "Example")
    assert example["attributes"] == [
        {"name": "scenario", "type": "text", "description": "场景"}
    ]
    assert "edge_types" not in example
    assert "analysis_summary" not in example
