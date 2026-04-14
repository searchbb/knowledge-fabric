from app.services.extraction_benchmark import (
    GraphBenchmarkMetrics,
    build_zep_ontology_classes,
    compare_benchmark_runs,
    compare_run_summaries,
    summarize_graph_data,
)
from app.services.legacy_social_ontology_generator import LegacySocialOntologyGenerator


def test_summarize_graph_data_tracks_invalid_edges_and_backbone():
    ontology = {
        "entity_types": [
            {"name": "Topic", "attributes": []},
            {"name": "Problem", "attributes": []},
            {"name": "Solution", "attributes": []},
            {"name": "Architecture", "attributes": []},
        ],
        "edge_types": [
            {"name": "HAS_PROBLEM", "source_targets": [{"source": "Topic", "target": "Problem"}]},
            {"name": "SOLVES", "source_targets": [{"source": "Solution", "target": "Problem"}]},
            {"name": "IMPLEMENTED_BY", "source_targets": [{"source": "Solution", "target": "Architecture"}]},
        ],
    }
    graph_data = {
        "nodes": [
            {"uuid": "n1", "name": "OpenClaw Observability", "labels": ["Topic"]},
            {"uuid": "n2", "name": "Execution black box", "labels": ["Problem"]},
            {"uuid": "n3", "name": "Full-link observability", "labels": ["Solution"]},
            {"uuid": "n4", "name": "DuckDB-based pipeline", "labels": ["Architecture"]},
            {"uuid": "n5", "name": "Noise", "labels": ["UnexpectedType"]},
        ],
        "edges": [
            {"uuid": "e1", "name": "HAS_PROBLEM", "source_node_uuid": "n1", "target_node_uuid": "n2"},
            {"uuid": "e2", "name": "SOLVES", "source_node_uuid": "n3", "target_node_uuid": "n2"},
            {"uuid": "e3", "name": "IMPLEMENTED_BY", "source_node_uuid": "n3", "target_node_uuid": "n4"},
            {"uuid": "e4", "name": "HAS_PROBLEM", "source_node_uuid": "n3", "target_node_uuid": "n2"},
            {"uuid": "e5", "name": "SOLVES", "source_node_uuid": "missing", "target_node_uuid": "n2"},
        ],
    }

    metrics = summarize_graph_data(graph_data, ontology)

    assert metrics.node_count == 5
    assert metrics.edge_count == 5
    assert metrics.invalid_edge_count == 2
    assert metrics.orphan_edge_count == 1
    assert metrics.core_backbone_score == 3
    assert metrics.core_backbone_edges == {
        "HAS_PROBLEM": 1,
        "SOLVES": 1,
        "IMPLEMENTED_BY": 1,
    }
    assert metrics.unexpected_entity_types == ["UnexpectedType"]
    assert metrics.entity_type_coverage == 1.0
    assert metrics.edge_type_coverage == 1.0


def test_build_zep_ontology_classes_preserves_properties_and_source_targets():
    ontology = {
        "entity_types": [
            {
                "name": "Topic",
                "description": "技术主题",
                "attributes": [
                    {"name": "domain", "description": "所属领域"},
                    {"name": "name", "description": "保留字会改名"},
                ],
            }
        ],
        "edge_types": [
            {
                "name": "HAS_PROBLEM",
                "description": "主题包含问题",
                "source_targets": [{"source": "Topic", "target": "Problem"}],
                "attributes": [{"name": "reason", "description": "关系依据"}],
            }
        ],
    }

    entity_models, edge_models = build_zep_ontology_classes(ontology)

    topic_model = entity_models["Topic"]
    schema = topic_model.model_json_schema()
    assert "domain" in schema["properties"]
    assert "entity_name" in schema["properties"]

    edge_model, source_targets = edge_models["HAS_PROBLEM"]
    edge_schema = edge_model.model_json_schema()
    assert "reason" in edge_schema["properties"]
    assert len(source_targets) == 1
    assert source_targets[0].source == "Topic"
    assert source_targets[0].target == "Problem"


def test_compare_benchmark_runs_returns_delta_view():
    local = GraphBenchmarkMetrics(
        node_count=40,
        edge_count=16,
        entity_type_counts={},
        edge_type_counts={},
        unexpected_entity_types=[],
        unexpected_edge_types=[],
        orphan_edge_count=0,
        invalid_edge_count=1,
        invalid_edge_rate=0.0625,
        entity_type_coverage=0.8,
        edge_type_coverage=0.5,
        core_backbone_edges={"HAS_PROBLEM": 1, "SOLVES": 1, "IMPLEMENTED_BY": 1},
        core_backbone_score=3,
    )
    zep = GraphBenchmarkMetrics(
        node_count=50,
        edge_count=20,
        entity_type_counts={},
        edge_type_counts={},
        unexpected_entity_types=[],
        unexpected_edge_types=[],
        orphan_edge_count=0,
        invalid_edge_count=4,
        invalid_edge_rate=0.2,
        entity_type_coverage=0.9,
        edge_type_coverage=0.6,
        core_backbone_edges={"HAS_PROBLEM": 1, "SOLVES": 0, "IMPLEMENTED_BY": 1},
        core_backbone_score=2,
    )

    comparison = compare_benchmark_runs(local, zep)

    assert comparison["node_count_ratio_vs_zep"] == 0.8
    assert comparison["edge_count_ratio_vs_zep"] == 0.8
    assert comparison["entity_type_coverage_delta"] == -0.1
    assert comparison["edge_type_coverage_delta"] == -0.1
    assert comparison["invalid_edge_rate_delta"] == -0.1375
    assert comparison["core_backbone_score_delta"] == 1


def test_compare_benchmark_runs_handles_missing_metrics():
    comparison = compare_benchmark_runs(None, None)

    assert comparison["status"] == "incomplete"
    assert comparison["local_available"] is False
    assert comparison["zep_available"] is False


def test_compare_run_summaries_handles_failed_run():
    left = type("Run", (), {})()
    left.profile = "zep_legacy_baseline"
    left.provider = "zep_control"
    left.status = "ok"
    left.duration_seconds = 12.5
    left.error = None
    left.metrics = GraphBenchmarkMetrics(
        node_count=12,
        edge_count=5,
        entity_type_counts={},
        edge_type_counts={},
        unexpected_entity_types=[],
        unexpected_edge_types=[],
        orphan_edge_count=0,
        invalid_edge_count=0,
        invalid_edge_rate=0.0,
        entity_type_coverage=1.0,
        edge_type_coverage=1.0,
        core_backbone_edges={},
        core_backbone_score=0,
    )

    right = type("Run", (), {})()
    right.profile = "zep_technical_control"
    right.provider = "zep_control"
    right.status = "failed"
    right.duration_seconds = 0.0
    right.error = "invalid json"
    right.metrics = None

    comparison = compare_run_summaries(left, right)

    assert comparison["status"] == "incomplete"
    assert comparison["left_profile"] == "zep_legacy_baseline"
    assert comparison["right_status"] == "failed"
    assert comparison["left_node_count"] == 12
    assert comparison["right_node_count"] is None


def test_legacy_social_ontology_generator_adds_person_and_organization_fallbacks():
    generator = LegacySocialOntologyGenerator.__new__(LegacySocialOntologyGenerator)
    result = generator._validate_and_process(
        {
            "entity_types": [
                {"name": "Student", "description": "student", "attributes": [], "examples": []},
                {"name": "University", "description": "university", "attributes": [], "examples": []},
            ],
            "edge_types": [],
            "analysis_summary": "",
        }
    )

    names = [entity["name"] for entity in result["entity_types"]]
    assert "Person" in names
    assert "Organization" in names
