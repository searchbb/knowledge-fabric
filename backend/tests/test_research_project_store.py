from __future__ import annotations

import json
import re

from app.models.project import ProjectManager
from app.models.research_project import ResearchProjectStore, ResearchProjectStatus


def test_create_research_project_persists_json(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")

    project = store.create({
        "title": "华为云 Agent-ready 企业软件栈战略研究",
        "background": "研究华为云在 Agent-ready 企业软件栈中的战略机会。",
        "audience": "华为云战略部二层领导",
        "goal": "形成战略判断、试点路径和汇报材料输入。",
    })

    assert re.match(r"^rp_[0-9a-f]{12}$", project.id)
    assert project.status == ResearchProjectStatus.DRAFT
    path = tmp_path / "research_projects" / f"{project.id}.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["title"] == "华为云 Agent-ready 企业软件栈战略研究"
    assert payload["evidence_items"] == []


def test_research_project_store_reads_after_reinitialization(tmp_path):
    root = tmp_path / "research_projects"
    created = ResearchProjectStore(root).create({"title": "Agent-ready strategy"})

    reloaded = ResearchProjectStore(root).get(created.id)

    assert reloaded is not None
    assert reloaded.id == created.id
    assert reloaded.title == "Agent-ready strategy"


def test_list_projects_sorts_by_updated_at(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    first = store.create({"title": "First"})
    second = store.create({"title": "Second"})

    store.update(first.id, {"goal": "updated later"})

    listed = store.list()
    assert [item.id for item in listed] == [first.id, second.id]


def test_update_refreshes_updated_at_and_keeps_created_at(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = store.create({"title": "Original"})
    old_created_at = project.created_at
    old_updated_at = project.updated_at

    updated = store.update(project.id, {"title": "Updated", "status": "active"})

    assert updated is not None
    assert updated.title == "Updated"
    assert updated.status == ResearchProjectStatus.ACTIVE
    assert updated.created_at == old_created_at
    assert updated.updated_at > old_updated_at


def test_missing_or_invalid_id_returns_none(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")

    assert store.get("rp_000000000000") is None
    assert store.get("../bad") is None


def test_research_project_store_does_not_use_article_project_manager(tmp_path, monkeypatch):
    article_projects_dir = tmp_path / "uploads" / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(article_projects_dir))

    store = ResearchProjectStore(tmp_path / "data" / "research_projects")
    store.create({"title": "Strategic research"})

    assert store.root_dir.exists()
    assert not article_projects_dir.exists()
