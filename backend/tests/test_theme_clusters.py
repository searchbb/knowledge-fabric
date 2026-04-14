"""Tests for Stage G theme cluster CRUD.

GPT test cases (2026-04-09):
1. Create cluster + attach 2 canonical concepts → success
2. Duplicate attach same concept → idempotent dedup
3. Merged concept ID auto-resolves to merge_to canonical
4. Detach concept, evidence/snippet preserved
5. Archive cluster, F2 concept registry not affected
6. Read cluster data through theme view endpoint
"""

from __future__ import annotations

from flask import Flask
import pytest

from app.api import theme_bp, concept_bp
from app.models.project import ProjectManager, ProjectStatus
from app.services.workspace import theme_view_service as theme_view_module


@pytest.fixture()
def cluster_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))

    monkeypatch.setattr(
        theme_view_module,
        "load_graph_data",
        lambda graph_id: {
            "graph_id": graph_id,
            "node_count": 3,
            "edge_count": 1,
            "nodes": [
                {"uuid": "n1", "name": "版本控制", "labels": ["Mechanism"]},
                {"uuid": "n2", "name": "GitHub", "labels": ["Technology"]},
                {"uuid": "n3", "name": "协作", "labels": ["Metric"]},
            ],
            "edges": [
                {"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n2", "name": "SUPPORTED_BY"},
            ],
        },
    )

    app = Flask(__name__)
    app.register_blueprint(theme_bp, url_prefix="/api/theme")
    app.register_blueprint(concept_bp, url_prefix="/api/concept")
    return app.test_client()


def _create_project():
    project = ProjectManager.create_project(name="Cluster Test")
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "cluster_graph"
    project.reading_structure = {"title": "Test", "group_titles": {"Mechanism": "机制"}}
    project.phase1_task_result = {"build_outcome": {"status": "completed", "warnings": []}}
    ProjectManager.save_project(project)
    return project.project_id


def test_create_cluster_and_attach_concepts(cluster_client):
    """GPT case 1: create cluster + attach 2 concepts."""
    pid = _create_project()

    # Create cluster
    create_resp = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters",
        json={"name": "协作工具链", "summary": "版本控制与平台协作"},
    )
    assert create_resp.status_code == 201
    cluster = create_resp.get_json()["data"]
    cid = cluster["id"]
    assert cluster["name"] == "协作工具链"
    assert cluster["concept_ids"] == []

    # Attach 2 concepts
    attach_resp = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters/{cid}/concepts:attach",
        json={"concept_ids": ["Mechanism:版本控制", "Technology:github"]},
    )
    assert attach_resp.status_code == 200
    assert sorted(attach_resp.get_json()["data"]["concept_ids"]) == [
        "Mechanism:版本控制",
        "Technology:github",
    ]


def test_duplicate_attach_is_idempotent(cluster_client):
    """GPT case 2: attach same concept twice → dedup."""
    pid = _create_project()

    create_resp = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters",
        json={"name": "去重测试"},
    )
    cid = create_resp.get_json()["data"]["id"]

    cluster_client.post(
        f"/api/theme/projects/{pid}/clusters/{cid}/concepts:attach",
        json={"concept_ids": ["Mechanism:版本控制"]},
    )
    attach2 = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters/{cid}/concepts:attach",
        json={"concept_ids": ["Mechanism:版本控制"]},
    )
    assert attach2.get_json()["data"]["concept_ids"].count("Mechanism:版本控制") == 1


def test_merged_concept_resolves_to_canonical(cluster_client):
    """GPT case 3: merged concept ID auto-resolves through F2 merge chain."""
    pid = _create_project()

    # Set up F2 merge: old_concept → canonical_concept
    project = ProjectManager.get_project(pid, include_legacy_phase1_backfill=False)
    project.concept_decisions = {
        "version": 1,
        "items": {
            "Mechanism:old_name": {"status": "merged", "merge_to": "Mechanism:版本控制"},
            "Mechanism:版本控制": {"status": "canonical", "canonical_name": "版本控制"},
        },
    }
    ProjectManager.save_project(project)

    create_resp = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters",
        json={"name": "归并测试"},
    )
    cid = create_resp.get_json()["data"]["id"]

    # Attach the OLD concept ID
    attach_resp = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters/{cid}/concepts:attach",
        json={"concept_ids": ["Mechanism:old_name"]},
    )
    # Should resolve to the canonical
    assert "Mechanism:版本控制" in attach_resp.get_json()["data"]["concept_ids"]


def test_detach_preserves_evidence(cluster_client):
    """GPT case 4: detach concept, evidence refs preserved."""
    pid = _create_project()

    create_resp = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters",
        json={"name": "证据测试"},
    )
    cid = create_resp.get_json()["data"]["id"]

    # Attach concept + evidence
    cluster_client.post(
        f"/api/theme/projects/{pid}/clusters/{cid}/concepts:attach",
        json={"concept_ids": ["Mechanism:版本控制", "Technology:github"]},
    )
    cluster_client.post(
        f"/api/theme/projects/{pid}/clusters/{cid}/evidence:attach",
        json={"evidence_refs": [{"ref_id": "ev1", "note": "重要证据"}]},
    )

    # Detach one concept
    detach_resp = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters/{cid}/concepts:detach",
        json={"concept_ids": ["Mechanism:版本控制"]},
    )
    data = detach_resp.get_json()["data"]
    assert "Mechanism:版本控制" not in data["concept_ids"]
    assert "Technology:github" in data["concept_ids"]
    assert len(data["evidence_refs"]) == 1  # evidence preserved


def test_archive_cluster_preserves_f2_registry(cluster_client):
    """GPT case 5: archiving cluster doesn't affect concept decisions."""
    pid = _create_project()

    # Set up a concept decision
    project = ProjectManager.get_project(pid, include_legacy_phase1_backfill=False)
    project.concept_decisions = {
        "version": 1,
        "items": {"Mechanism:版本控制": {"status": "canonical", "canonical_name": "版本控制"}},
    }
    ProjectManager.save_project(project)

    create_resp = cluster_client.post(
        f"/api/theme/projects/{pid}/clusters",
        json={"name": "归档测试"},
    )
    cid = create_resp.get_json()["data"]["id"]

    # Archive
    update_resp = cluster_client.put(
        f"/api/theme/projects/{pid}/clusters/{cid}",
        json={"status": "archived"},
    )
    assert update_resp.get_json()["data"]["status"] == "archived"

    # F2 concept decision still intact
    project = ProjectManager.get_project(pid, include_legacy_phase1_backfill=False)
    assert project.concept_decisions["items"]["Mechanism:版本控制"]["status"] == "canonical"


def test_clusters_appear_in_theme_view(cluster_client):
    """GPT case 6: clusters visible through the theme view endpoint."""
    pid = _create_project()

    cluster_client.post(
        f"/api/theme/projects/{pid}/clusters",
        json={"name": "视图测试"},
    )

    view_resp = cluster_client.get(f"/api/theme/projects/{pid}/view")
    data = view_resp.get_json()["data"]
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["name"] == "视图测试"
