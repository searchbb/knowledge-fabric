from __future__ import annotations

from app.repositories.neo4j.theme_repository import ThemeNeo4jRepository


def _normalize(query: str) -> str:
    return " ".join(query.split())


def test_sync_theme_places_on_create_before_set(monkeypatch):
    captured: dict[str, object] = {}
    repo = ThemeNeo4jRepository()

    def fake_exec_sync(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return None

    monkeypatch.setattr(repo, "exec_sync", fake_exec_sync)

    repo.sync_theme({"theme_id": "gtheme_test", "name": "Theme"})

    query = _normalize(str(captured["query"]))
    assert "MERGE (t:Theme {theme_id: $theme_id}) ON CREATE SET t.created_at = $created_at SET" in query


def test_sync_concept_places_on_create_before_set(monkeypatch):
    captured: dict[str, object] = {}
    repo = ThemeNeo4jRepository()

    def fake_exec_sync(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return None

    monkeypatch.setattr(repo, "exec_sync", fake_exec_sync)

    repo.sync_concept({"entry_id": "canon_test", "canonical_name": "Concept"})

    query = _normalize(str(captured["query"]))
    assert "MERGE (c:CanonicalConcept {entry_id: $entry_id}) ON CREATE SET c.created_at = $created_at SET" in query


def test_exec_inlines_params_before_query_execution(monkeypatch):
    class _FakeDriver:
        def __init__(self):
            self.calls = []
            self.closed = False

        async def execute_query(self, query, **kwargs):
            self.calls.append((query, kwargs))
            return "ok"

        def close(self):
            self.closed = True

    repo = ThemeNeo4jRepository()
    fake_driver = _FakeDriver()
    monkeypatch.setattr(repo, "_get_driver", lambda: fake_driver)

    result = repo.exec_sync(
        "MERGE (t:Theme {theme_id: $theme_id}) RETURN t",
        {"theme_id": "gtheme_test"},
    )

    assert result == "ok"
    assert fake_driver.calls[0][1] == {}
    assert "gtheme_test" in fake_driver.calls[0][0]
    assert "$theme_id" not in fake_driver.calls[0][0]
    assert fake_driver.closed is True
