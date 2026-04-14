from __future__ import annotations

from dataclasses import dataclass
from flask import Flask
import pytest

from app.api import graph as graph_api
from app.models.project import ProjectManager, ProjectStatus
from app.models.task import TaskManager, TaskStatus
from app.services.workspace import legacy_phase1_snapshot as legacy_snapshot_module


@dataclass
class _FakeBuilder:
    graph_data: dict
    graph_id: str = "graph_local_1"
    diagnostics: dict | None = None
    def __post_init__(self):
        self.calls = []

    def create_graph(self, name: str) -> str:
        self.calls.append(("create_graph", name))
        return self.graph_id

    def set_ontology(self, graph_id: str, ontology: dict):
        self.calls.append(("set_ontology", graph_id, ontology))

    def ensure_phase1_storage_compatibility(self, graph_id: str):
        self.calls.append(("ensure_phase1_storage_compatibility", graph_id))
        return ["constraint_topic_name"]

    def add_text_batches(
        self,
        graph_id: str,
        chunks: list[str],
        batch_size: int = 3,
        progress_callback=None,
        cancel_check=None,
    ):
        self.calls.append(("add_text_batches", graph_id, list(chunks), batch_size))
        if cancel_check is not None and cancel_check():
            from app.services.graph_builder import BuildCancelledError

            raise BuildCancelledError(
                batch_index=1,
                total_batches=1,
                processed_chunks=0,
                total_chunks=len(chunks),
            )
        if progress_callback:
            progress_callback("mock batches", 1.0)
        return ["episode_1"]

    def _wait_for_episodes(self, episode_uuids, progress_callback=None, timeout: int = 600):
        self.calls.append(("_wait_for_episodes", list(episode_uuids), timeout))
        if progress_callback:
            progress_callback("mock wait", 1.0)

    async def prune_invalid_edges_async(self, graph_id: str):
        self.calls.append(("prune_invalid_edges_async", graph_id))
        return []

    def _run_async(self, awaitable):
        import asyncio

        self.calls.append(("_run_async",))
        return asyncio.run(awaitable)

    async def _get_client(self):
        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def run(self, *args, **kwargs):
                return None

        class _FakeDriver:
            def session(self):
                return _FakeSession()

        class _FakeClient:
            driver = _FakeDriver()

        return _FakeClient()

    def get_graph_data(self, graph_id: str) -> dict:
        self.calls.append(("get_graph_data", graph_id))
        return self.graph_data

    def get_build_diagnostics(self) -> dict:
        return self.diagnostics or {
            "chunk_count": 1,
            "processed_chunk_count": 1,
            "episode_count": 1,
            "soft_failed_chunk_count": 0,
            "soft_failed_chunks": [],
            "json_parse_repair_count": 0,
            "json_parse_retry_count": 0,
            "json_parse_failure_count": 0,
        }


class _InlineThread:
    def __init__(self, target=None, daemon=None, args=None, kwargs=None):
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}

    def start(self):
        if self.target:
            self.target(*self.args, **self.kwargs)


class _SuccessfulReadingExtractor:
    instances = []

    def __init__(self):
        self.last_result_meta = {"status": "generated", "reason": ""}
        self.__class__.instances.append(self)

    def extract(self, **kwargs):
        return {
            "title": "阅读主线",
            "summary": "摘要",
            "problem": {"title": "问题", "summary": ""},
            "solution": {"title": "方案", "summary": ""},
            "architecture": {"title": "结构", "summary": ""},
            "group_titles": {},
            "node_order_hints": {},
        }


class _FailingReadingExtractor:
    instances = []

    def __init__(self):
        self.__class__.instances.append(self)

    def extract(self, **kwargs):
        raise RuntimeError("reading failed")


class _NoopQualityGate:
    def __init__(self):
        self.last_summary_backfill_meta = {
            "requested": 0,
            "completed": 0,
            "missing": [],
        }

    def assess(self, graph_data, ontology, document_text):
        return type(
            "_Assessment",
            (),
            {
                "should_supplement": False,
                "missing_types": [],
            },
        )()

    def supplement(self, *, missing_types, document_text, ontology, existing_nodes):
        return type(
            "_Supplement",
            (),
            {
                "new_nodes": [],
                "new_edges": [],
            },
        )()

    @staticmethod
    def find_near_duplicates(graph_data, threshold=0.70):
        return []

    def backfill_summaries(self, *, graph_data, document_text):
        return {}


class _PartialSummaryGate:
    def __init__(self):
        self.last_summary_backfill_meta = {
            "requested": 2,
            "completed": 1,
            "missing": ["节点B"],
        }

    def assess(self, graph_data, ontology, document_text):
        return type(
            "_Assessment",
            (),
            {
                "should_supplement": False,
                "missing_types": [],
            },
        )()

    def supplement(self, *, missing_types, document_text, ontology, existing_nodes):
        return type(
            "_Supplement",
            (),
            {
                "new_nodes": [],
                "new_edges": [],
            },
        )()

    @staticmethod
    def find_near_duplicates(graph_data, threshold=0.70):
        return []

    def backfill_summaries(self, *, graph_data, document_text):
        return {"节点A": "节点A摘要"}


@pytest.fixture(autouse=True)
def _stub_quality_gate(monkeypatch):
    import app.services.graph_quality_gate as quality_gate_module

    monkeypatch.setattr(quality_gate_module, "GraphQualityGate", _NoopQualityGate)


def test_build_graph_allows_local_provider_without_zep_key(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    builder = _FakeBuilder(
        graph_data={
            "graph_id": "graph_local_1",
            "nodes": [{"uuid": "n1", "name": "DuckDB", "labels": ["Technology"], "summary": "DuckDB 是列式分析数据库"}],
            "edges": [],
            "node_count": 1,
            "edge_count": 0,
        }
    )

    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _SuccessfulReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["chunk-a"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)
    monkeypatch.setattr(graph_api.Config, "ZEP_API_KEY", None)

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 200
    assert response["success"] is True

    task = TaskManager().get_task(response["data"]["task_id"])
    stored = ProjectManager.get_project(project.project_id)

    assert task is not None
    assert task.status == TaskStatus.COMPLETED
    assert stored is not None
    assert stored.status == ProjectStatus.GRAPH_COMPLETED
    assert stored.graph_id == "graph_local_1"
    assert stored.reading_structure["title"] == "阅读主线"
    assert stored.phase1_task_result is not None
    assert stored.phase1_task_result["provider"] == "local"
    assert stored.phase1_task_result["build_outcome"]["status"] == "completed"
    assert any(call[0] == "ensure_phase1_storage_compatibility" for call in builder.calls)
    assert any(call[0] == "prune_invalid_edges_async" for call in builder.calls)
    assert any(call[0] == "get_graph_data" for call in builder.calls)
    assert task.result["diagnostics"]["dropped_constraints"] == ["constraint_topic_name"]
    assert task.result["build_outcome"]["status"] == "completed"
    assert task.result["reading_structure_status"]["status"] == "generated"


def test_build_graph_requires_zep_key_when_provider_is_zep(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)

    monkeypatch.setenv("GRAPH_BUILDER_PROVIDER", "zep")
    monkeypatch.setattr(graph_api.Config, "ZEP_API_KEY", None)

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 500
    assert response["success"] is False
    assert "ZEP_API_KEY未配置" in response["error"]


def test_build_graph_keeps_graph_when_reading_structure_fails(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    builder = _FakeBuilder(
        graph_data={
            "graph_id": "graph_local_2",
            "nodes": [{"uuid": "n1", "name": "OpenClaw", "labels": ["Topic"], "summary": "OpenClaw 是文章主题"}],
            "edges": [{"uuid": "e1", "name": "SOLVES", "source_node_uuid": "n1", "target_node_uuid": "n1"}],
            "node_count": 1,
            "edge_count": 1,
        },
        graph_id="graph_local_2",
    )

    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _FailingReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["chunk-a"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 200
    assert response["success"] is True

    task = TaskManager().get_task(response["data"]["task_id"])
    stored = ProjectManager.get_project(project.project_id)

    assert task is not None
    assert task.status == TaskStatus.COMPLETED
    assert stored is not None
    assert stored.status == ProjectStatus.GRAPH_COMPLETED
    assert stored.graph_id == "graph_local_2"
    assert stored.reading_structure is None
    assert stored.phase1_task_result is not None
    assert stored.phase1_task_result["reading_structure_status"]["status"] == "failed"
    assert task.result["build_outcome"]["status"] == "completed_with_warnings"
    assert task.result["reading_structure_status"]["status"] == "failed"


def test_build_graph_fails_when_graph_data_is_empty(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    builder = _FakeBuilder(
        graph_data={
            "graph_id": "graph_empty",
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
        },
        graph_id="graph_empty",
    )

    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _SuccessfulReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["chunk-a"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 200
    assert response["success"] is True

    task = TaskManager().get_task(response["data"]["task_id"])
    stored = ProjectManager.get_project(project.project_id)

    assert task is not None
    assert task.status == TaskStatus.FAILED
    assert "未产出任何节点或关系" in task.message
    assert stored is not None
    assert stored.status == ProjectStatus.FAILED
    assert stored.phase1_task_result is not None
    assert stored.phase1_task_result["build_outcome"]["status"] == "failed"


def test_build_graph_surfaces_partial_summary_backfill_as_warning(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    builder = _FakeBuilder(
        graph_data={
            "graph_id": "graph_summary_partial",
            "nodes": [
                {"uuid": "n1", "name": "节点A", "labels": ["Problem"], "summary": ""},
                {"uuid": "n2", "name": "节点B", "labels": ["Solution"], "summary": ""},
            ],
            "edges": [{"uuid": "e1", "name": "RELATES_TO", "source_node_uuid": "n1", "target_node_uuid": "n2"}],
            "node_count": 2,
            "edge_count": 1,
        },
        graph_id="graph_summary_partial",
    )

    def _get_graph_data(graph_id: str):
        builder.calls.append(("get_graph_data", graph_id))
        return {
            "graph_id": "graph_summary_partial",
            "nodes": [
                {"uuid": "n1", "name": "节点A", "labels": ["Problem"], "summary": "节点A摘要"},
                {"uuid": "n2", "name": "节点B", "labels": ["Solution"], "summary": ""},
            ],
            "edges": [{"uuid": "e1", "name": "RELATES_TO", "source_node_uuid": "n1", "target_node_uuid": "n2"}],
            "node_count": 2,
            "edge_count": 1,
        }

    monkeypatch.setattr(builder, "get_graph_data", _get_graph_data)
    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _SuccessfulReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["chunk-a"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)

    import app.services.graph_quality_gate as quality_gate_module

    monkeypatch.setattr(quality_gate_module, "GraphQualityGate", _PartialSummaryGate)

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 200
    assert response["success"] is True

    task = TaskManager().get_task(response["data"]["task_id"])
    assert task is not None
    assert task.status == TaskStatus.COMPLETED
    assert task.result["build_outcome"]["status"] == "completed_with_warnings"
    assert "summary 回填未覆盖 1/2 个节点" in task.result["build_outcome"]["warnings"]
    assert task.result["diagnostics"]["summary_backfill_requested"] == 2
    assert task.result["diagnostics"]["summary_backfill_completed"] == 1
    assert task.result["diagnostics"]["summary_backfill_missing"] == ["节点B"]


def test_build_graph_skips_reading_structure_when_summary_coverage_is_too_low(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    builder = _FakeBuilder(
        graph_data={
            "graph_id": "graph_summary_sparse",
            "nodes": [
                {"uuid": "n1", "name": "节点A", "labels": ["Topic"], "summary": "节点A摘要"},
                {"uuid": "n2", "name": "节点B", "labels": ["Problem"], "summary": ""},
                {"uuid": "n3", "name": "节点C", "labels": ["Solution"], "summary": ""},
                {"uuid": "n4", "name": "节点D", "labels": ["Evidence"], "summary": ""},
            ],
            "edges": [
                {"uuid": "e1", "name": "HAS_PROBLEM", "source_node_uuid": "n1", "target_node_uuid": "n2"},
                {"uuid": "e2", "name": "SOLVES", "source_node_uuid": "n3", "target_node_uuid": "n2"},
            ],
            "node_count": 4,
            "edge_count": 2,
        },
        graph_id="graph_summary_sparse",
    )

    _SuccessfulReadingExtractor.instances = []
    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _SuccessfulReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["chunk-a"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 200
    assert response["success"] is True

    task = TaskManager().get_task(response["data"]["task_id"])
    stored = ProjectManager.get_project(project.project_id)

    assert task is not None
    assert task.status == TaskStatus.COMPLETED
    assert task.result["build_outcome"]["status"] == "completed_with_warnings"
    assert "summary 覆盖率过低 1/4" in task.result["build_outcome"]["warnings"]
    assert task.result["reading_structure_status"]["status"] == "skipped"
    assert "summary 覆盖率不足" in task.result["reading_structure_status"]["reason"]
    assert stored is not None
    assert stored.reading_structure is None
    assert _SuccessfulReadingExtractor.instances == []


def test_build_graph_fails_when_rate_limit_abort_is_reported(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    builder = _FakeBuilder(
        graph_data={
            "graph_id": "graph_partial",
            "nodes": [{"uuid": "n1", "name": "Topic", "labels": ["Topic"]}],
            "edges": [],
            "node_count": 1,
            "edge_count": 0,
        },
        graph_id="graph_partial",
        diagnostics={
            "chunk_count": 4,
            "processed_chunk_count": 2,
            "episode_count": 2,
            "soft_failed_chunk_count": 1,
            "soft_failed_chunks": [{"chunk_index": 3, "error_kind": "rate_limit", "reason": "429"}],
            "json_parse_repair_count": 0,
            "json_parse_retry_count": 0,
            "json_parse_failure_count": 0,
            "retry_count": 2,
            "rate_limit_hit_count": 2,
            "aborted_due_to_rate_limit": True,
            "aborted_chunk_index": 3,
            "abort_reason": "chunk_3 reached upstream rate limit after retries",
        },
    )

    _SuccessfulReadingExtractor.instances = []
    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _SuccessfulReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["a", "b", "c", "d"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 200
    assert response["success"] is True

    task = TaskManager().get_task(response["data"]["task_id"])
    stored = ProjectManager.get_project(project.project_id)

    assert task is not None
    assert task.status == TaskStatus.FAILED
    assert "触发上游限额" in task.message
    assert task.result["build_outcome"]["status"] == "failed"
    assert task.result["reading_structure_status"]["status"] == "skipped"
    assert stored is not None
    assert stored.status == ProjectStatus.FAILED
    assert stored.phase1_task_result is not None
    assert stored.phase1_task_result["build_outcome"]["status"] == "failed"
    assert _SuccessfulReadingExtractor.instances == []


def test_build_graph_fails_when_all_chunks_rate_limited(tmp_path, monkeypatch):
    """When all chunks fail due to rate limiting, the task should FAIL with a clear error -- no fallback."""
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    builder = _FakeBuilder(
        graph_data={
            "graph_id": "graph_rate_limited",
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
        },
        graph_id="graph_rate_limited",
        diagnostics={
            "chunk_count": 4,
            "processed_chunk_count": 0,
            "episode_count": 0,
            "soft_failed_chunk_count": 1,
            "soft_failed_chunks": [{"chunk_index": 1, "error_kind": "rate_limit", "reason": "429"}],
            "json_parse_repair_count": 0,
            "json_parse_retry_count": 0,
            "json_parse_failure_count": 0,
            "retry_count": 2,
            "rate_limit_hit_count": 3,
            "aborted_due_to_rate_limit": True,
            "aborted_chunk_index": 1,
            "abort_reason": "chunk_1 reached upstream rate limit after retries",
        },
    )

    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _SuccessfulReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["a", "b", "c", "d"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 200
    assert response["success"] is True

    task = TaskManager().get_task(response["data"]["task_id"])
    stored = ProjectManager.get_project(project.project_id)

    assert task is not None
    assert task.status == TaskStatus.FAILED
    assert stored is not None
    assert stored.status == ProjectStatus.FAILED
    assert stored.phase1_task_result is not None
    assert stored.phase1_task_result["build_outcome"]["status"] == "failed"


def test_build_graph_force_rebuild_overwrites_previous_graph_state(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "old_graph"
    project.graph_build_task_id = "old_task"
    project.phase1_task_result = {"provider": "legacy", "build_outcome": {"status": "completed"}}
    project.reading_structure = {"title": "旧阅读骨架"}
    ProjectManager.save_project(project)

    builder = _FakeBuilder(
        graph_data={
            "graph_id": "graph_force_new",
            "nodes": [{"uuid": "n1", "name": "新方案", "labels": ["Solution"], "summary": "新方案摘要"}],
            "edges": [],
            "node_count": 1,
            "edge_count": 0,
        },
        graph_id="graph_force_new",
    )

    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _SuccessfulReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["chunk-a"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)

    response, status = _call_build_graph(app, {"project_id": project.project_id, "force": True})

    assert status == 200
    assert response["success"] is True

    task = TaskManager().get_task(response["data"]["task_id"])
    stored = ProjectManager.get_project(project.project_id)

    assert task is not None
    assert task.status == TaskStatus.COMPLETED
    assert stored is not None
    assert stored.graph_id == "graph_force_new"
    assert stored.reading_structure["title"] == "阅读主线"
    assert stored.graph_build_task_id == response["data"]["task_id"]
    assert stored.phase1_task_result is not None
    assert stored.phase1_task_result["provider"] == "local"


def test_phase1_contract_is_exposed_consistently_across_routes(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    builder = _FakeBuilder(
        graph_data={
            "graph_id": "mirofish_contract_1",
            "nodes": [{"uuid": "n1", "name": "知识工作台", "labels": ["Topic"], "summary": "知识工作台摘要"}],
            "edges": [],
            "node_count": 1,
            "edge_count": 0,
        },
        graph_id="mirofish_contract_1",
    )

    monkeypatch.setattr(graph_api, "get_graph_builder_provider", lambda: "local")
    monkeypatch.setattr(graph_api, "validate_graph_builder_config", lambda provider=None: [])
    monkeypatch.setattr(graph_api, "get_graph_builder", lambda provider=None: builder)
    monkeypatch.setattr(graph_api, "ReadingStructureExtractor", _SuccessfulReadingExtractor)
    monkeypatch.setattr(graph_api.TextProcessor, "split_text", lambda text, chunk_size, overlap: ["chunk-a"])
    monkeypatch.setattr(graph_api.threading, "Thread", _InlineThread)
    monkeypatch.setattr(
        graph_api,
        "load_graph_data_by_backend",
        lambda graph_id, *, backend="local": builder.get_graph_data(graph_id),
    )

    response, status = _call_build_graph(app, {"project_id": project.project_id})

    assert status == 200
    assert response["success"] is True
    task_id = response["data"]["task_id"]

    with app.app_context():
        with app.test_request_context(f"/api/graph/task/{task_id}", method="GET"):
            task_response = graph_api.get_task(task_id)
        with app.test_request_context(f"/api/graph/project/{project.project_id}", method="GET"):
            project_response = graph_api.get_project(project.project_id)
        with app.test_request_context("/api/graph/data/mirofish_contract_1", method="GET"):
            graph_response = graph_api.get_graph_data("mirofish_contract_1")

    task_payload = task_response.get_json()
    project_payload = project_response.get_json()
    graph_payload = graph_response.get_json()
    result = task_payload["data"]["result"]

    assert task_payload["success"] is True
    assert result["contract_version"] == "phase1.v1"
    assert result["phase"] == "knowledge_workbench_phase1"
    assert result["provider"] == "local"
    assert result["diagnostics"]["provider"] == "local"
    assert result["diagnostics"]["chunk_count"] == 1
    assert result["artifacts"]["graph"] == {
        "graph_id": "mirofish_contract_1",
        "node_count": 1,
        "edge_count": 0,
        "build_status": "completed",
    }
    assert result["artifacts"]["reading_structure"]["status"] == "generated"

    assert project_payload["success"] is True
    assert project_payload["data"]["reading_structure"]["title"] == "阅读主线"
    assert project_payload["data"]["phase1_task_result"]["provider"] == "local"
    assert project_payload["data"]["phase1_task_result"]["build_outcome"]["status"] == "completed"
    assert graph_payload["success"] is True
    assert graph_payload["data"]["graph_id"] == "mirofish_contract_1"


def test_reset_project_clears_persisted_phase1_snapshot(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "graph_reset"
    project.graph_build_task_id = "task_reset"
    project.phase1_task_result = {
        "provider": "local",
        "build_outcome": {
            "status": "completed_with_warnings",
        },
    }
    project.reading_structure = {"title": "旧骨架"}
    ProjectManager.save_project(project)

    with app.app_context():
        with app.test_request_context(f"/api/graph/project/{project.project_id}/reset", method="POST"):
            response = graph_api.reset_project(project.project_id)

    payload = response.get_json()
    stored = ProjectManager.get_project(project.project_id)

    assert payload["success"] is True
    assert stored is not None
    assert stored.phase1_task_result is None
    assert stored.graph_id is None
    assert stored.reading_structure is None


def test_get_project_backfills_legacy_phase1_snapshot_without_persisting_it(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "legacy_graph"
    project.graph_build_task_id = "legacy_task"
    project.phase1_task_result = None
    project.reading_structure = {"title": "旧项目阅读骨架"}
    ProjectManager.save_project(project)

    with app.app_context():
        with app.test_request_context(f"/api/graph/project/{project.project_id}", method="GET"):
            response = graph_api.get_project(project.project_id)

    payload = response.get_json()
    stored_after = ProjectManager.get_project(project.project_id)
    raw_stored = ProjectManager.get_project(project.project_id, include_legacy_phase1_backfill=False)

    assert payload["success"] is True
    assert payload["data"]["phase1_task_result"]["provider"] == "unknown"
    assert payload["data"]["phase1_task_result"]["build_outcome"]["status"] == "completed"
    assert payload["data"]["phase1_task_result"]["build_outcome"]["success_ratio"] is None
    assert payload["data"]["phase1_task_result"]["reading_structure_status"]["status"] == "generated"
    assert payload["data"]["phase1_task_result"]["diagnostics"]["snapshot_source"] == "legacy_project_backfill"
    assert stored_after is not None
    assert stored_after.phase1_task_result["provider"] == "unknown"
    assert raw_stored is not None
    assert raw_stored.phase1_task_result is None


def test_get_project_backfills_failed_legacy_phase1_snapshot(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    project.status = ProjectStatus.FAILED
    project.graph_id = None
    project.graph_build_task_id = "legacy_failed_task"
    project.phase1_task_result = None
    project.reading_structure = None
    project.error = "旧流程构建失败"
    ProjectManager.save_project(project)

    with app.app_context():
        with app.test_request_context(f"/api/graph/project/{project.project_id}", method="GET"):
            response = graph_api.get_project(project.project_id)

    payload = response.get_json()

    assert payload["success"] is True
    assert payload["data"]["phase1_task_result"]["provider"] == "unknown"
    assert payload["data"]["phase1_task_result"]["build_outcome"]["status"] == "failed"
    assert payload["data"]["phase1_task_result"]["reading_structure_status"]["status"] == "skipped"
    assert payload["data"]["phase1_task_result"]["diagnostics"]["legacy_backfill"] is True


def test_get_project_recovers_orphaned_graph_building_project_with_graph_data(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    project.status = ProjectStatus.GRAPH_BUILDING
    project.graph_id = "orphan_graph"
    project.graph_build_task_id = "orphan_task"
    project.phase1_task_result = None
    project.reading_structure = None
    ProjectManager.save_project(project)

    monkeypatch.setattr(
        "app.services.graph_access_service.load_graph_data_by_backend",
        lambda graph_id, *, backend="local": {
            "graph_id": graph_id,
            "nodes": [
                {"uuid": "n1", "name": "Data Agent", "labels": ["Topic"], "summary": "主题摘要"},
                {"uuid": "n2", "name": "本体论", "labels": ["Solution"], "summary": "方案摘要"},
            ],
            "edges": [
                {"uuid": "e1", "name": "HAS_TOPIC", "source_node_uuid": "n2", "target_node_uuid": "n1"},
            ],
            "node_count": 2,
            "edge_count": 1,
        },
    )

    with app.app_context():
        with app.test_request_context(f"/api/graph/project/{project.project_id}", method="GET"):
            response = graph_api.get_project(project.project_id)

    payload = response.get_json()
    raw_stored = ProjectManager.get_project(project.project_id, include_legacy_phase1_backfill=False)

    assert payload["success"] is True
    assert payload["data"]["status"] == "graph_completed"
    assert payload["data"]["graph_build_task_id"] is None
    assert payload["data"]["phase1_task_result"]["provider"] == "recovered"
    assert payload["data"]["phase1_task_result"]["build_outcome"]["status"] == "completed_with_warnings"
    assert payload["data"]["phase1_task_result"]["diagnostics"]["snapshot_source"] == "orphaned_graph_build_recovery"
    assert raw_stored is not None
    assert raw_stored.status == ProjectStatus.GRAPH_COMPLETED
    assert raw_stored.graph_build_task_id is None
    assert raw_stored.phase1_task_result is not None


def test_get_project_recovers_orphaned_graph_building_project_without_graph_data(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)
    project.status = ProjectStatus.GRAPH_BUILDING
    project.graph_id = "orphan_graph_empty"
    project.graph_build_task_id = "orphan_task_missing"
    project.phase1_task_result = None
    ProjectManager.save_project(project)

    monkeypatch.setattr(
        "app.services.graph_access_service.load_graph_data_by_backend",
        lambda graph_id, *, backend="local": {
            "graph_id": graph_id,
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
        },
    )

    with app.app_context():
        with app.test_request_context(f"/api/graph/project/{project.project_id}", method="GET"):
            response = graph_api.get_project(project.project_id)

    payload = response.get_json()
    raw_stored = ProjectManager.get_project(project.project_id, include_legacy_phase1_backfill=False)

    assert payload["success"] is True
    assert payload["data"]["status"] == "failed"
    assert payload["data"]["graph_build_task_id"] is None
    assert payload["data"]["error"]
    assert payload["data"]["phase1_task_result"]["provider"] == "recovered"
    assert payload["data"]["phase1_task_result"]["build_outcome"]["status"] == "failed"
    assert payload["data"]["phase1_task_result"]["diagnostics"]["snapshot_source"] == "orphaned_graph_build_recovery"
    assert raw_stored is not None
    assert raw_stored.status == ProjectStatus.FAILED
    assert raw_stored.graph_build_task_id is None
    assert raw_stored.phase1_task_result is not None


def test_backfill_legacy_phase1_snapshots_persists_without_touching_updated_at(tmp_path, monkeypatch):
    project = _prepare_project(tmp_path, monkeypatch)
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "legacy_graph_persisted"
    project.phase1_task_result = None
    project.reading_structure = {"title": "旧项目阅读骨架"}
    ProjectManager.save_project(project)
    expected_updated_at = project.updated_at

    result = legacy_snapshot_module.backfill_legacy_phase1_snapshots(
        project_ids=[project.project_id],
        persist=True,
    )
    raw_stored = ProjectManager.get_project(project.project_id, include_legacy_phase1_backfill=False)

    assert result["persisted"] is True
    assert result["summary"]["eligible"] == 1
    assert raw_stored is not None
    assert raw_stored.phase1_task_result is not None
    assert raw_stored.phase1_task_result["provider"] == "unknown"
    assert raw_stored.phase1_task_result["diagnostics"]["snapshot_source"] == "legacy_project_backfill"
    assert raw_stored.updated_at == expected_updated_at


def test_get_graph_data_prefers_local_builder_for_mirofish_graph_ids(monkeypatch):
    app = Flask(__name__)

    def _fake_loader(graph_id: str, *, backend: str = "local"):
        assert backend == "local"
        return {"graph_id": graph_id, "nodes": [], "edges": [], "node_count": 0, "edge_count": 0}

    monkeypatch.setattr(graph_api, "load_graph_data_by_backend", _fake_loader)

    with app.app_context():
        with app.test_request_context("/api/graph/data/mirofish_local_1", method="GET"):
            response = graph_api.get_graph_data("mirofish_local_1")

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["backend"] == "local"
    assert payload["data"]["graph_id"] == "mirofish_local_1"


def test_get_graph_data_supports_explicit_legacy_zep_backend(monkeypatch):
    app = Flask(__name__)

    def _fake_loader(graph_id: str, *, backend: str = "local"):
        return {
            "graph_id": graph_id,
            "nodes": [{"uuid": "n1", "name": "Legacy"}],
            "edges": [],
            "node_count": 1,
            "edge_count": 0,
            "backend_used": backend,
        }

    monkeypatch.setattr(graph_api, "load_graph_data_by_backend", _fake_loader)

    with app.app_context():
        with app.test_request_context("/api/graph/data/legacy_graph?backend=legacy_zep", method="GET"):
            response = graph_api.get_graph_data("legacy_graph")

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["backend"] == "legacy_zep"
    assert payload["data"]["backend_used"] == "legacy_zep"


def test_get_graph_data_rejects_invalid_backend():
    app = Flask(__name__)

    with app.app_context():
        with app.test_request_context("/api/graph/data/graph_1?backend=unknown", method="GET"):
            response, status = graph_api.get_graph_data("graph_1")

    payload = response.get_json()
    assert status == 400
    assert payload["success"] is False
    assert "不支持的图谱后端" in payload["error"]


def test_get_project_text_returns_extracted_text(tmp_path, monkeypatch):
    app = Flask(__name__)
    project = _prepare_project(tmp_path, monkeypatch)

    with app.app_context():
        with app.test_request_context(f"/api/graph/project/{project.project_id}/text", method="GET"):
            response = graph_api.get_project_text(project.project_id)

    payload = response.get_json()

    assert payload["success"] is True
    assert payload["data"]["project_id"] == project.project_id
    assert payload["data"]["char_count"] == len("DuckDB 解决可观测问题。")
    assert payload["data"]["text"] == "DuckDB 解决可观测问题。"


def _prepare_project(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    TaskManager()._tasks.clear()

    project = ProjectManager.create_project("Test Project")
    project.status = ProjectStatus.ONTOLOGY_GENERATED
    project.ontology = {
        "entity_types": [{"name": "Topic", "attributes": []}],
        "edge_types": [{"name": "RELATES_TO", "source_targets": [{"source": "Topic", "target": "Topic"}]}],
    }
    project.analysis_summary = "文章摘要"
    ProjectManager.save_project(project)
    ProjectManager.save_extracted_text(project.project_id, "DuckDB 解决可观测问题。")
    return project


def _call_build_graph(app: Flask, payload: dict):
    with app.app_context():
        with app.test_request_context("/api/graph/build", method="POST", json=payload):
            result = graph_api.build_graph()

    if isinstance(result, tuple):
        response, status = result
    else:
        response = result
        status = response.status_code
    return response.get_json(), status


def test_list_tasks_route_returns_serialized_tasks(tmp_path, monkeypatch):
    app = Flask(__name__)
    _prepare_project(tmp_path, monkeypatch)
    task_id = TaskManager().create_task("构建图谱: test")

    with app.app_context():
        with app.test_request_context("/api/graph/tasks", method="GET"):
            response = graph_api.list_tasks()

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["data"][0]["task_id"] == task_id
