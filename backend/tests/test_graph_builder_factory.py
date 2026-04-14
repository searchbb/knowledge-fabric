import pytest

from app.services import graph_builder_factory


def test_get_graph_builder_provider_defaults_to_local(monkeypatch):
    monkeypatch.delenv("GRAPH_BUILDER_PROVIDER", raising=False)

    assert graph_builder_factory.get_graph_builder_provider() == "local"


def test_get_graph_builder_provider_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("GRAPH_BUILDER_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="GRAPH_BUILDER_PROVIDER"):
        graph_builder_factory.get_graph_builder_provider()


def test_validate_graph_builder_config_requires_zep_key_for_zep(monkeypatch):
    monkeypatch.setenv("GRAPH_BUILDER_PROVIDER", "zep")
    monkeypatch.setattr(graph_builder_factory.Config, "ZEP_API_KEY", None)

    assert graph_builder_factory.validate_graph_builder_config() == ["ZEP_API_KEY未配置"]


def test_validate_graph_builder_config_does_not_require_zep_key_for_local(monkeypatch):
    monkeypatch.setenv("GRAPH_BUILDER_PROVIDER", "local")
    monkeypatch.setattr(graph_builder_factory.Config, "ZEP_API_KEY", None)

    assert graph_builder_factory.validate_graph_builder_config() == []
