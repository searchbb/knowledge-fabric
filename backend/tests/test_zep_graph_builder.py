from types import SimpleNamespace

import pytest

from app.services.zep_graph_builder import EpisodeHandle, ZepGraphBuilderService


class FakeGraphClient:
    def __init__(self):
        self.set_ontology_calls = []
        self.add_batch_calls = []
        self.episode = FakeEpisodeClient({})

    def set_ontology(self, **kwargs):
        self.set_ontology_calls.append(kwargs)

    def add_batch(self, **kwargs):
        self.add_batch_calls.append(kwargs)
        return [
            SimpleNamespace(uuid_="ep-1", task_id="task-1"),
            SimpleNamespace(uuid_="ep-2", task_id="task-2"),
        ]


class FakeEpisodeClient:
    def __init__(self, processed_map):
        self.processed_map = processed_map
        self.calls = []

    def get(self, uuid_):
        self.calls.append(uuid_)
        return SimpleNamespace(
            uuid_=uuid_,
            processed=self.processed_map.get(uuid_, False),
            task_id=None,
        )


class FakeTaskClient:
    def __init__(self, status_map):
        self.status_map = status_map
        self.calls = []

    def get(self, task_id):
        self.calls.append(task_id)
        return SimpleNamespace(status=self.status_map.get(task_id))


class FakeClient:
    def __init__(self):
        self.graph = FakeGraphClient()
        self.task = FakeTaskClient({})


def test_set_ontology_renames_reserved_attributes_for_zep():
    service = ZepGraphBuilderService.__new__(ZepGraphBuilderService)
    service.client = FakeClient()

    ontology = {
        "entity_types": [
            {
                "name": "Topic",
                "description": "topic",
                "attributes": [
                    {"name": "name", "description": "reserved"},
                    {"name": "domain", "description": "domain"},
                ],
            }
        ],
        "edge_types": [
            {
                "name": "HAS_PROBLEM",
                "description": "has problem",
                "attributes": [{"name": "name", "description": "reserved edge"}],
                "source_targets": [{"source": "Topic", "target": "Problem"}],
            }
        ],
    }

    service.set_ontology("graph_1", ontology)

    call = service.client.graph.set_ontology_calls[0]
    topic_model = call["entities"]["Topic"]
    edge_model, source_targets = call["edges"]["HAS_PROBLEM"]

    assert "entity_name" in topic_model.model_fields
    assert "domain" in topic_model.model_fields
    assert "edge_name" in edge_model.model_fields
    assert source_targets[0].source == "Topic"
    assert source_targets[0].target == "Problem"


def test_add_text_batches_uses_minimal_episode_payload():
    service = ZepGraphBuilderService.__new__(ZepGraphBuilderService)
    service.client = FakeClient()

    episode_ids = service.add_text_batches(
        graph_id="graph_1",
        chunks=["chunk a", "chunk b"],
        batch_size=2,
    )

    call = service.client.graph.add_batch_calls[0]
    episodes = call["episodes"]

    assert call["graph_id"] == "graph_1"
    assert episode_ids == [
        EpisodeHandle(uuid="ep-1", task_id="task-1"),
        EpisodeHandle(uuid="ep-2", task_id="task-2"),
    ]
    assert len(episodes) == 2
    assert episodes[0].data == "chunk a"
    assert episodes[0].type == "text"
    assert episodes[0].created_at is None
    assert episodes[0].source_description is None


def test_add_text_batches_updates_build_diagnostics(monkeypatch):
    service = ZepGraphBuilderService.__new__(ZepGraphBuilderService)
    service.client = FakeClient()
    monkeypatch.setattr("app.services.zep_graph_builder.time.sleep", lambda _: None)

    service.add_text_batches(
        graph_id="graph_1",
        chunks=["chunk a", "chunk b"],
        batch_size=2,
    )
    diagnostics = service.get_build_diagnostics()

    assert diagnostics["chunk_count"] == 2
    assert diagnostics["processed_chunk_count"] == 2
    assert diagnostics["episode_count"] == 2
    assert diagnostics["soft_failed_chunk_count"] == 0
    assert diagnostics["aborted_due_to_rate_limit"] is False


def test_wait_for_episodes_prefers_zep_task_status():
    service = ZepGraphBuilderService.__new__(ZepGraphBuilderService)
    service.client = SimpleNamespace(
        task=FakeTaskClient({"task-1": "succeeded"}),
        graph=SimpleNamespace(episode=FakeEpisodeClient({"ep-1": False})),
    )

    service._wait_for_episodes([EpisodeHandle(uuid="ep-1", task_id="task-1")], timeout=1)

    assert service.client.task.calls == ["task-1"]
    assert service.client.graph.episode.calls == []


def test_wait_for_episodes_raises_on_failed_task():
    service = ZepGraphBuilderService.__new__(ZepGraphBuilderService)
    service.client = SimpleNamespace(
        task=FakeTaskClient({"task-1": "failed"}),
        graph=SimpleNamespace(episode=FakeEpisodeClient({"ep-1": False})),
    )

    with pytest.raises(RuntimeError, match="处理失败"):
        service._wait_for_episodes([EpisodeHandle(uuid="ep-1", task_id="task-1")], timeout=1)

    diagnostics = service.get_build_diagnostics()
    assert diagnostics["soft_failed_chunk_count"] == 1
    assert diagnostics["soft_failed_chunks"] == [
        {"episode_uuid": "ep-1", "error_kind": "fatal", "reason": "failed"}
    ]
