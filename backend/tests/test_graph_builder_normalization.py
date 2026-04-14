import asyncio
import json
import sys
import types
from types import SimpleNamespace

from graphiti_core.prompts.extract_edges import ExtractedEdges
from graphiti_core.prompts.extract_nodes import ExtractedEntities, SummarizedEntities
from graphiti_core.prompts.models import Message

from app.services.graph_builder import (
    GraphBuilderService,
    LocalEmbedder,
    MiniMaxLLMClient,
    PHASE1_SINGLE_CALL_TIMEOUT_SECONDS,
)


def make_client() -> MiniMaxLLMClient:
    return MiniMaxLLMClient.__new__(MiniMaxLLMClient)


def test_minimax_client_prefers_json_schema_for_local_base_url():
    class DemoSchema(ExtractedEntities):
        pass

    client = make_client()
    client._response_base_url = "http://127.0.0.1:1234/v1"

    response_format = client._build_response_format(DemoSchema)

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "DemoSchema"


def test_normalize_extracted_entities_maps_aliases_and_type_names():
    client = make_client()
    payload = {
        "nodes": [
            {"entity_name": "DuckDB", "entity_type": "Technology"},
            {"title": "可观测系统四层架构", "label": "Architecture"},
        ]
    }

    normalized = client._normalize_for_model(
        payload,
        ExtractedEntities,
        {"technology": 8, "architecture": 4},
        [],
    )
    validated = ExtractedEntities.model_validate(normalized)

    assert validated.model_dump() == {
        "extracted_entities": [
            {"name": "DuckDB", "entity_type_id": 8},
            {"name": "可观测系统四层架构", "entity_type_id": 4},
        ]
    }


def test_normalize_extracted_edges_wraps_single_item_and_builds_fact():
    client = make_client()
    entity_names = [
        "基于DuckDB的可观测插件方案",
        "Agent执行黑盒问题",
    ]
    payload = {
        "source_entity": {"name": "基于DuckDB的可观测插件方案"},
        "target_entity": "Agent执行黑盒问题",
        "relationship_type": "SOLVES",
    }

    normalized = client._normalize_for_model(payload, ExtractedEdges, {}, entity_names)
    validated = ExtractedEdges.model_validate(normalized)
    edge = validated.edges[0]

    assert edge.source_entity_name == "基于DuckDB的可观测插件方案"
    assert edge.target_entity_name == "Agent执行黑盒问题"
    assert edge.relation_type == "SOLVES"
    assert edge.fact == "基于DuckDB的可观测插件方案 SOLVES Agent执行黑盒问题"


def test_sanitize_model_payload_drops_invalid_edge_items():
    client = make_client()
    payload = {"edges": [{}, {"foo": "bar"}]}

    sanitized = client._sanitize_model_payload(payload, ExtractedEdges)
    validated = ExtractedEdges.model_validate(sanitized)

    assert validated.model_dump() == {"edges": []}


def test_parse_llm_json_repairs_truncated_payload_with_trailing_commas():
    client = make_client()
    raw = """```json
    {
      "edges": [
        {
          "source_entity_name": "DuckDB",
          "target_entity_name": "可观测问题",
          "relation_type": "SOLVES",
          "fact": "DuckDB solves observability",
        }
      ]
    """

    parsed = client._parse_llm_json(raw)
    validated = ExtractedEdges.model_validate(parsed)
    edge = validated.edges[0]

    assert edge.source_entity_name == "DuckDB"
    assert edge.target_entity_name == "可观测问题"
    assert edge.relation_type == "SOLVES"
    assert edge.fact == "DuckDB solves observability"


def test_parse_llm_json_prefers_first_balanced_fragment_over_trailing_text():
    client = make_client()
    raw = """先输出结果：
    {"edges":[{"source_entity_name":"DuckDB","target_entity_name":"可观测问题","relation_type":"SOLVES","fact":"DuckDB solves observability"}]}
    下面是解释：
    {"note":"ignore me"}
    """

    parsed = client._parse_llm_json(raw)
    validated = ExtractedEdges.model_validate(parsed)

    assert len(validated.edges) == 1
    assert validated.edges[0].target_entity_name == "可观测问题"


def test_parse_llm_json_repairs_missing_commas_between_fields():
    client = make_client()
    raw = """{
      "edges": [
        {
          "source_entity_name": "DuckDB"
          "target_entity_name": "可观测问题"
          "relation_type": "SOLVES"
          "fact": "DuckDB solves observability"
        }
      ]
    }"""

    parsed = client._parse_llm_json(raw)
    validated = ExtractedEdges.model_validate(parsed)

    assert len(validated.edges) == 1
    assert validated.edges[0].relation_type == "SOLVES"


def test_parse_llm_json_repairs_unescaped_quotes_inside_string_values():
    client = make_client()
    raw = """{
      "summaries": [
        {
          "name": "Prompt优化",
          "summary": "用于定位 "Done" 异常的分析方法"
        }
      ]
    }"""

    parsed = client._parse_llm_json(raw)
    validated = SummarizedEntities.model_validate(parsed)

    assert len(validated.summaries) == 1
    assert validated.summaries[0].name == "Prompt优化"
    assert validated.summaries[0].summary == '用于定位 "Done" 异常的分析方法'


def test_extract_entity_name_lookup_and_fuzzy_match_are_prompt_driven():
    client = make_client()
    messages = [
        Message(
            role="user",
            content="""
<ENTITIES>
[{"name": "基于DuckDB的可观测插件方案"}, {"name": "Agent执行黑盒问题"}]
</ENTITIES>
""",
        )
    ]

    entity_names = client._extract_entity_name_lookup(messages)
    normalized = client._normalize_for_model(
        {
            "relations": [
                {
                    "source_entity": "可观测插件方案",
                    "target_entity": "Agent黑盒问题",
                    "relationship_type": "SOLVES",
                }
            ]
        },
        ExtractedEdges,
        {},
        entity_names,
    )
    validated = ExtractedEdges.model_validate(normalized)
    edge = validated.edges[0]

    assert entity_names == ["基于DuckDB的可观测插件方案", "Agent执行黑盒问题"]
    assert edge.source_entity_name == "基于DuckDB的可观测插件方案"
    assert edge.target_entity_name == "Agent执行黑盒问题"


def test_normalize_summaries_coerces_nested_values_to_json_strings():
    client = make_client()
    payload = {
        "entity_summaries": {
            "entity_name": "DuckDB",
            "description": {
                "reason": "OLAP friendly",
                "advantages": ["local", "fast"],
            },
        }
    }

    normalized = client._normalize_for_model(payload, SummarizedEntities, {}, [])
    validated = SummarizedEntities.model_validate(normalized)
    summary = validated.summaries[0]

    assert summary.name == "DuckDB"
    assert json.loads(summary.summary) == {
        "advantages": ["local", "fast"],
        "reason": "OLAP friendly",
    }


def test_local_embedder_create_and_batch_return_expected_shapes(monkeypatch):
    class FakeSentenceTransformer:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def encode(self, input_data, normalize_embeddings=True):
            import numpy as np

            texts = [input_data] if isinstance(input_data, str) else list(input_data)
            rows = [[float(index + 1), float(len(text))] for index, text in enumerate(texts)]
            return np.array(rows)

        def get_sentence_embedding_dimension(self):
            return 2

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    embedder = LocalEmbedder("fake-model")

    single = run_async(embedder.create(["hello world"]))
    batch = run_async(embedder.create_batch(["hello world", "duckdb observability"]))

    assert single == [1.0, 11.0]
    assert batch == [[1.0, 11.0], [2.0, 20.0]]


def test_local_embedder_falls_back_to_deterministic_hash_vectors(monkeypatch):
    class FailingSentenceTransformer:
        def __init__(self, model_name: str, local_files_only: bool = False):
            raise OSError("model not cached")

    fake_module = types.SimpleNamespace(SentenceTransformer=FailingSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    embedder = LocalEmbedder("missing-model")

    single = run_async(embedder.create(["hello world"]))
    batch = run_async(embedder.create_batch(["hello world", "duckdb observability"]))

    assert len(single) == 384
    assert len(batch) == 2
    assert len(batch[0]) == 384
    assert single == batch[0]
    assert batch[0] != batch[1]


def test_is_edge_allowed_enforces_source_target_direction():
    builder = GraphBuilderService()
    builder._allowed_edge_pairs = {
        ("Solution", "HAS_EXAMPLE", "Example"),
        ("Architecture", "IMPLEMENTED_BY", "Layer"),
    }

    assert builder._is_edge_allowed("HAS_EXAMPLE", ["Solution", "Entity"], ["Example"]) is True
    assert builder._is_edge_allowed("HAS_EXAMPLE", ["Example"], ["Problem"]) is False
    assert builder._is_edge_allowed("IMPLEMENTED_BY", ["Architecture"], ["Layer"]) is True
    assert builder._is_edge_allowed("IMPLEMENTED_BY", ["Layer"], ["Architecture"]) is False


def test_build_display_graph_data_filters_unclassified_and_isolated_nodes():
    builder = GraphBuilderService()
    graph = builder._build_display_graph_data(
        "graph_1",
        nodes_data=[
            {"uuid": "n1", "name": "主题", "labels": ["Topic"], "summary": "", "attributes": {}, "created_at": None},
            {"uuid": "n2", "name": "问题", "labels": ["Problem"], "summary": "", "attributes": {}, "created_at": None},
            {"uuid": "n3", "name": "孤立技术", "labels": ["Technology"], "summary": "", "attributes": {}, "created_at": None},
            {"uuid": "n4", "name": "组织名", "labels": [], "summary": "", "attributes": {}, "created_at": None},
        ],
        edges_data=[
            {
                "uuid": "e1",
                "name": "SOLVES",
                "fact": "主题解决问题",
                "fact_type": "SOLVES",
                "source_node_uuid": "n1",
                "target_node_uuid": "n2",
                "source_node_name": "主题",
                "target_node_name": "问题",
                "attributes": {},
                "created_at": None,
                "valid_at": None,
                "invalid_at": None,
                "expired_at": None,
                "episodes": [],
            },
            {
                "uuid": "e2",
                "name": "HAS_TOPIC",
                "fact": "问题关联组织",
                "fact_type": "HAS_TOPIC",
                "source_node_uuid": "n2",
                "target_node_uuid": "n4",
                "source_node_name": "问题",
                "target_node_name": "组织名",
                "attributes": {},
                "created_at": None,
                "valid_at": None,
                "invalid_at": None,
                "expired_at": None,
                "episodes": [],
            },
        ],
    )

    # n4 (no labels) is dropped; n3 (isolated but labeled) is kept per current policy
    assert graph["node_count"] == 3
    assert graph["edge_count"] == 1
    assert [node["name"] for node in graph["nodes"]] == ["主题", "问题", "孤立技术"]
    assert [edge["uuid"] for edge in graph["edges"]] == ["e1"]


def test_build_display_graph_data_keeps_labeled_nodes_when_graph_has_no_edges():
    builder = GraphBuilderService()
    graph = builder._build_display_graph_data(
        "graph_2",
        nodes_data=[
            {"uuid": "n1", "name": "主题", "labels": ["Topic"], "summary": "", "attributes": {}, "created_at": None},
            {"uuid": "n2", "name": "无类型组织", "labels": [], "summary": "", "attributes": {}, "created_at": None},
        ],
        edges_data=[],
    )

    assert graph["node_count"] == 1
    assert graph["edge_count"] == 0
    assert graph["nodes"][0]["name"] == "主题"


def test_run_async_closes_client_and_resets_it():
    class FakeClient:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    builder = GraphBuilderService()
    fake_client = FakeClient()
    builder._client = fake_client

    result = builder._run_async(_return_value(42))

    assert result == 42
    assert fake_client.closed is True
    assert builder._client is None


def test_run_async_closes_graph_driver_and_resets_it():
    class FakeDriver:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    builder = GraphBuilderService()
    fake_driver = FakeDriver()
    builder._graph_driver = fake_driver

    result = builder._run_async(_return_value(7))

    assert result == 7
    assert fake_driver.closed is True
    assert builder._graph_driver is None


def test_ensure_phase1_storage_compatibility_drops_conflicting_name_constraints():
    class FakeDriver:
        def __init__(self):
            self.queries = []

        async def execute_query(self, query, **kwargs):
            self.queries.append((query, kwargs))
            if query.startswith("SHOW CONSTRAINTS"):
                return SimpleNamespace(
                    records=[
                        {
                            "name": "constraint_topic_name",
                            "type": "NODE_PROPERTY_UNIQUENESS",
                            "entityType": "NODE",
                            "labelsOrTypes": ["Topic"],
                            "properties": ["name"],
                        },
                        {
                            "name": "constraint_entity_id",
                            "type": "NODE_PROPERTY_UNIQUENESS",
                            "entityType": "NODE",
                            "labelsOrTypes": ["__Entity__"],
                            "properties": ["id"],
                        },
                    ]
                )
            return SimpleNamespace(records=[])

    class FakeClient:
        def __init__(self):
            self.driver = FakeDriver()

        async def close(self):
            return None

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._reset_build_stats(total_chunks=1)
    builder._phase1_entity_labels = {"Topic", "Problem"}

    dropped = run_async(builder.ensure_phase1_storage_compatibility_async("graph_1"))

    assert dropped == ["constraint_topic_name"]
    assert any("DROP CONSTRAINT `constraint_topic_name` IF EXISTS" in query for query, _ in builder._client.driver.queries)


def test_get_build_diagnostics_returns_chunk_and_json_parse_stats():
    builder = GraphBuilderService()
    builder._build_stats = {
        "chunk_count": 10,
        "processed_chunk_count": 8,
        "episode_count": 8,
        "soft_failed_chunk_count": 2,
        "soft_failed_chunks": [{"chunk_index": 3, "reason": "parse error"}],
        "dropped_constraints": ["constraint_topic_name"],
        "retry_count": 3,
        "rate_limit_hit_count": 2,
        "aborted_due_to_rate_limit": True,
        "aborted_chunk_index": 9,
        "abort_reason": "chunk_9 reached upstream rate limit after retries",
    }
    builder._llm_client = SimpleNamespace(
        json_parse_repair_count=4,
        json_parse_retry_count=2,
        json_parse_failure_count=1,
    )

    diagnostics = builder.get_build_diagnostics()

    assert diagnostics["chunk_count"] == 10
    assert diagnostics["soft_failed_chunk_count"] == 2
    assert diagnostics["dropped_constraints"] == ["constraint_topic_name"]
    assert diagnostics["json_parse_repair_count"] == 4
    assert diagnostics["json_parse_retry_count"] == 2
    assert diagnostics["json_parse_failure_count"] == 1
    assert diagnostics["retry_count"] == 3
    assert diagnostics["aborted_due_to_rate_limit"] is True


def test_add_text_batches_retries_rate_limit_then_succeeds(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = 0

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError("429 usage limit exceeded")
            return SimpleNamespace(
                episodes=[SimpleNamespace(uuid="episode_ok") for _ in raw_episodes]
            )

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)

    episode_ids = run_async(builder.add_text_batches_async("graph_1", ["chunk-a"]))
    diagnostics = builder.get_build_diagnostics()

    assert episode_ids == ["episode_ok"]
    assert builder._client.calls == 3
    assert sleep_calls == [2.0, 5.0]
    assert diagnostics["processed_chunk_count"] == 1
    assert diagnostics["retry_count"] == 2
    assert diagnostics["rate_limit_hit_count"] == 2
    assert diagnostics["aborted_due_to_rate_limit"] is False


def test_add_text_batches_raises_when_rate_limit_retries_are_exhausted(monkeypatch):
    """After exhausting retries on rate limit, the error should propagate -- no silent abort."""
    class FakeClient:
        def __init__(self):
            self.calls = 0

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.calls += 1
            raise RuntimeError("429 usage limit exceeded")

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)

    import pytest
    with pytest.raises(RuntimeError, match="429"):
        run_async(builder.add_text_batches_async("graph_2", ["chunk-a", "chunk-b"]))






def test_get_graph_data_async_uses_direct_driver_without_initializing_graphiti():
    class FakeDriver:
        def __init__(self):
            self.queries = []

        async def execute_query(self, query, **kwargs):
            self.queries.append((query, kwargs))
            if "MATCH (n:Entity)" in query:
                return SimpleNamespace(
                    records=[
                        {
                            "uuid": "n1",
                            "name": "主题",
                            "labels": ["Topic", "Entity"],
                            "summary": "摘要",
                            "created_at": None,
                        },
                        {
                            "uuid": "n2",
                            "name": "问题",
                            "labels": ["Problem", "Entity"],
                            "summary": "",
                            "created_at": None,
                        },
                    ]
                )
            return SimpleNamespace(
                records=[
                    {
                        "uuid": "e1",
                        "name": "HAS_PROBLEM",
                        "fact": "主题 指向 问题",
                        "source_node_uuid": "n1",
                        "target_node_uuid": "n2",
                        "source_node_name": "主题",
                        "target_node_name": "问题",
                        "created_at": None,
                        "valid_at": None,
                        "invalid_at": None,
                        "expired_at": None,
                    }
                ]
            )

    builder = GraphBuilderService()
    fake_driver = FakeDriver()

    async def fake_get_graph_driver():
        return fake_driver

    async def unexpected_get_client():
        raise AssertionError("get_graph_data_async should not initialize Graphiti client")

    builder._get_graph_driver = fake_get_graph_driver
    builder._get_client = unexpected_get_client

    graph = run_async(builder.get_graph_data_async("graph_readonly"))

    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1
    assert [node["name"] for node in graph["nodes"]] == ["主题", "问题"]
    assert graph["edges"][0]["name"] == "HAS_PROBLEM"
    assert len(fake_driver.queries) == 2


def test_add_text_batches_calls_add_episode_bulk():
    """Verifies that the bulk path is called and episode UUIDs are returned."""
    class FakeClient:
        def __init__(self):
            self.bulk_called = False

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.bulk_called = True
            return SimpleNamespace(
                episodes=[SimpleNamespace(uuid="ep1"), SimpleNamespace(uuid="ep2")]
            )

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    episode_ids = run_async(builder.add_text_batches_async("g1", ["chunk-a", "chunk-b"]))

    assert builder._client.bulk_called is True
    assert episode_ids == ["ep1", "ep2"]


def test_add_text_batches_splits_bulk_calls_by_batch_size():
    class FakeClient:
        def __init__(self):
            self.calls = []

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.calls.append([episode.content for episode in raw_episodes])
            call_index = len(self.calls)
            return SimpleNamespace(
                episodes=[
                    SimpleNamespace(uuid=f"ep{call_index}_{i}")
                    for i, _ in enumerate(raw_episodes, start=1)
                ]
            )

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    episode_ids = run_async(
        builder.add_text_batches_async("g_batch", ["a", "b", "c", "d", "e"], batch_size=2)
    )
    diagnostics = builder.get_build_diagnostics()

    assert builder._client.calls == [["a", "b"], ["c", "d"], ["e"]]
    assert episode_ids == ["ep1_1", "ep1_2", "ep2_1", "ep2_2", "ep3_1"]
    assert diagnostics["processed_chunk_count"] == 5
    assert diagnostics["episode_count"] == 5


def test_add_text_batches_falls_back_to_single_chunk_submission_after_bulk_retries(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.bulk_calls = 0
            self.single_calls = []

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.bulk_calls += 1
            raise TimeoutError("bulk timeout")

        async def add_episode(self, **kwargs):
            self.single_calls.append(kwargs["episode_body"])
            return SimpleNamespace(episode=SimpleNamespace(uuid=f"single_{len(self.single_calls)}"))

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)

    episode_ids = run_async(
        builder.add_text_batches_async("g_single", ["a", "b"], batch_size=2)
    )
    diagnostics = builder.get_build_diagnostics()

    assert builder._client.bulk_calls == 3
    assert builder._client.single_calls == ["a", "b"]
    assert episode_ids == ["single_1", "single_2"]
    assert sleep_calls == [2.0, 5.0]
    assert diagnostics["processed_chunk_count"] == 2
    assert diagnostics["episode_count"] == 2


def test_add_chunk_with_retries_retries_after_single_chunk_timeout(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = 0

        async def add_episode(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(episode=SimpleNamespace(uuid=f"single_{self.calls}"))

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._reset_build_stats(total_chunks=1)

    wait_for_calls = []
    real_wait_for = asyncio.wait_for

    async def fake_wait_for(coro, timeout):
        wait_for_calls.append(timeout)
        if len(wait_for_calls) == 1:
            coro.close()
            raise asyncio.TimeoutError()
        return await real_wait_for(coro, timeout)

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.graph_builder.asyncio.wait_for", fake_wait_for)
    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)

    episode_ids = run_async(
        builder._add_chunk_with_retries(
            client=builder._client,
            chunk="chunk body",
            chunk_num=1,
            total_chunks=1,
            graph_id="g_timeout",
            source_description="text_import",
            extra_kwargs={},
            progress_callback=None,
        )
    )

    assert episode_ids == ["single_1"]
    assert builder._client.calls == 1
    assert wait_for_calls == [
        PHASE1_SINGLE_CALL_TIMEOUT_SECONDS,
        PHASE1_SINGLE_CALL_TIMEOUT_SECONDS,
    ]
    assert sleep_calls == [2.0]


def test_with_timeout_context_adds_readable_message_for_blank_timeout():
    builder = GraphBuilderService()

    wrapped = builder._with_timeout_context(
        TimeoutError(),
        context="文本块 1/7",
        timeout_seconds=60,
    )

    assert isinstance(wrapped, TimeoutError)
    assert str(wrapped) == "文本块 1/7 请求超时（>60s）"


def test_add_chunk_with_retries_splits_chunk_after_timeout_retries(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = []

        async def add_episode(self, **kwargs):
            body = kwargs["episode_body"]
            self.calls.append(body)
            if body == "chunk body":
                raise TimeoutError("Request timed out.")
            return SimpleNamespace(episode=SimpleNamespace(uuid=f"id_{len(self.calls)}"))

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._reset_build_stats(total_chunks=1)

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        builder,
        "_split_chunk_for_retry",
        lambda chunk: ["sub chunk 1", "sub chunk 2"] if chunk == "chunk body" else [],
    )

    episode_ids = run_async(
        builder._add_chunk_with_retries(
            client=builder._client,
            chunk="chunk body",
            chunk_num=1,
            total_chunks=1,
            graph_id="g_split",
            source_description="text_import",
            extra_kwargs={},
            progress_callback=None,
        )
    )

    diagnostics = builder.get_build_diagnostics()

    assert episode_ids == ["id_4", "id_5"]
    assert builder._client.calls == [
        "chunk body",
        "chunk body",
        "chunk body",
        "sub chunk 1",
        "sub chunk 2",
    ]
    assert sleep_calls == [2.0, 5.0]
    assert diagnostics["adaptive_split_count"] == 1
    assert diagnostics["adaptive_subchunk_count"] == 2


def test_add_chunk_with_retries_splits_chunk_after_context_overflow(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = []

        async def add_episode(self, **kwargs):
            body = kwargs["episode_body"]
            self.calls.append(body)
            if body == "chunk body":
                raise RuntimeError("400 Context size has been exceeded.")
            return SimpleNamespace(episode=SimpleNamespace(uuid=f"id_{len(self.calls)}"))

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._reset_build_stats(total_chunks=1)

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        builder,
        "_split_chunk_for_retry",
        lambda chunk: ["sub chunk 1", "sub chunk 2"] if chunk == "chunk body" else [],
    )

    episode_ids = run_async(
        builder._add_chunk_with_retries(
            client=builder._client,
            chunk="chunk body",
            chunk_num=1,
            total_chunks=1,
            graph_id="g_context_split",
            source_description="text_import",
            extra_kwargs={},
            progress_callback=None,
        )
    )

    diagnostics = builder.get_build_diagnostics()

    assert episode_ids == ["id_2", "id_3"]
    assert builder._client.calls == ["chunk body", "sub chunk 1", "sub chunk 2"]
    assert diagnostics["adaptive_split_count"] == 1
    assert diagnostics["adaptive_subchunk_count"] == 2


def test_raw_episode_construction_is_correct():
    """Verifies that RawEpisode fields are populated correctly from chunks."""
    captured_episodes = []

    class FakeClient:
        async def add_episode_bulk(self, raw_episodes, **kwargs):
            captured_episodes.extend(raw_episodes)
            return SimpleNamespace(
                episodes=[SimpleNamespace(uuid=f"ep{i}") for i in range(len(raw_episodes))]
            )

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    run_async(builder.add_text_batches_async("g2", ["hello world", "second chunk"]))

    assert len(captured_episodes) == 2
    ep0 = captured_episodes[0]
    assert ep0.name == "chunk_1"
    assert ep0.content == "hello world"
    assert "g2" in ep0.source_description
    ep1 = captured_episodes[1]
    assert ep1.name == "chunk_2"
    assert ep1.content == "second chunk"


def test_add_text_batches_bulk_passes_ontology_params():
    """Verifies entity_types, edge_types, edge_type_map, custom_extraction_instructions are forwarded."""
    captured_kwargs = {}

    class FakeClient:
        async def add_episode_bulk(self, raw_episodes, **kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                episodes=[SimpleNamespace(uuid="ep1")]
            )

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {"Topic": object}
    builder._graphiti_edge_types = {"SOLVES": object}
    builder._graphiti_edge_type_map = {("Topic", "Problem"): ["SOLVES"]}
    builder._custom_extraction_instructions = "Extract cognitive elements."

    run_async(builder.add_text_batches_async("g3", ["chunk"]))

    assert captured_kwargs["group_id"] == "g3"
    assert captured_kwargs["entity_types"] == {"Topic": object}
    assert captured_kwargs["edge_types"] == {"SOLVES": object}
    assert captured_kwargs["edge_type_map"] == {("Topic", "Problem"): ["SOLVES"]}
    assert captured_kwargs["custom_extraction_instructions"] == "Extract cognitive elements."


def test_add_text_batches_bulk_retries_on_rate_limit(monkeypatch):
    """First call hits 429, second succeeds."""
    class FakeClient:
        def __init__(self):
            self.calls = 0

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("429 usage limit exceeded")
            return SimpleNamespace(
                episodes=[SimpleNamespace(uuid="ep_ok")]
            )

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)

    episode_ids = run_async(builder.add_text_batches_async("g4", ["chunk"]))
    diagnostics = builder.get_build_diagnostics()

    assert episode_ids == ["ep_ok"]
    assert builder._client.calls == 2
    assert sleep_calls == [2.0]
    assert diagnostics["retry_count"] == 1
    assert diagnostics["rate_limit_hit_count"] == 1


def test_add_text_batches_bulk_raises_when_retries_exhausted(monkeypatch):
    """Always 429 -- should raise after exhausting retries."""
    class FakeClient:
        def __init__(self):
            self.calls = 0

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.calls += 1
            raise RuntimeError("429 usage limit exceeded")

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)

    import pytest
    with pytest.raises(RuntimeError, match="429"):
        run_async(builder.add_text_batches_async("g5", ["chunk"]))


def test_add_text_batches_bulk_single_chunk_timeout_falls_back_to_single(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.bulk_calls = 0
            self.single_calls = 0

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.bulk_calls += 1
            raise TimeoutError()

        async def add_episode(self, **kwargs):
            self.single_calls += 1
            return SimpleNamespace(uuid="ep_single_ok")

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)

    episode_ids = run_async(builder.add_text_batches_async("g_single_timeout", ["chunk"]))
    diagnostics = builder.get_build_diagnostics()

    assert episode_ids == ["ep_single_ok"]
    assert builder._client.bulk_calls == 3
    assert builder._client.single_calls == 1
    assert diagnostics["retry_count"] == 2
    assert diagnostics["processed_chunk_count"] == 1


def test_add_text_batches_bulk_context_overflow_falls_back_to_single(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.bulk_calls = 0
            self.single_calls = 0

        async def add_episode_bulk(self, raw_episodes, **kwargs):
            self.bulk_calls += 1
            raise RuntimeError("400 Context size has been exceeded.")

        async def add_episode(self, **kwargs):
            self.single_calls += 1
            return SimpleNamespace(uuid="ep_single_context_ok")

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("app.services.graph_builder.asyncio.sleep", fake_sleep)

    episode_ids = run_async(builder.add_text_batches_async("g_single_context", ["chunk"]))
    diagnostics = builder.get_build_diagnostics()

    assert episode_ids == ["ep_single_context_ok"]
    assert builder._client.bulk_calls == 1
    assert builder._client.single_calls == 1
    assert diagnostics["retry_count"] == 0
    assert diagnostics["processed_chunk_count"] == 1


def test_add_text_batches_bulk_progress_callback():
    """Progress callback is called at start and end."""
    class FakeClient:
        async def add_episode_bulk(self, raw_episodes, **kwargs):
            return SimpleNamespace(
                episodes=[SimpleNamespace(uuid="ep1")]
            )

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    callback_calls = []

    def progress_cb(message, progress):
        callback_calls.append((message, progress))

    run_async(builder.add_text_batches_async("g6", ["chunk"], progress_callback=progress_cb))

    assert len(callback_calls) >= 2
    # First call is at start (progress 0.0), last call is completion (progress 1.0)
    assert callback_calls[0][1] == 0.0
    assert callback_calls[-1][1] == 1.0


def test_add_text_batches_bulk_updates_build_stats():
    """Diagnostics reflect correct counts after bulk processing."""
    class FakeClient:
        async def add_episode_bulk(self, raw_episodes, **kwargs):
            return SimpleNamespace(
                episodes=[
                    SimpleNamespace(uuid="ep1"),
                    SimpleNamespace(uuid="ep2"),
                    SimpleNamespace(uuid="ep3"),
                ]
            )

    builder = GraphBuilderService()
    builder._client = FakeClient()
    builder._graphiti_entity_types = {}
    builder._graphiti_edge_types = {}
    builder._graphiti_edge_type_map = {}
    builder._custom_extraction_instructions = ""

    episode_ids = run_async(builder.add_text_batches_async("g7", ["a", "b", "c"]))
    diagnostics = builder.get_build_diagnostics()

    assert episode_ids == ["ep1", "ep2", "ep3"]
    assert diagnostics["chunk_count"] == 3
    assert diagnostics["processed_chunk_count"] == 3
    assert diagnostics["episode_count"] == 3
    assert diagnostics["retry_count"] == 0
    assert diagnostics["rate_limit_hit_count"] == 0
    assert diagnostics["aborted_due_to_rate_limit"] is False


def run_async(awaitable):
    import asyncio

    return asyncio.run(awaitable)


async def _return_value(value):
    return value
