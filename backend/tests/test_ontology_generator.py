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
