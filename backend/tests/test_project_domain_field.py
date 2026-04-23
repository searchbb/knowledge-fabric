"""Tests for project.domain field (v3 domain-scoped ontology, Stage 1).

Field spec (per GPT consult 2026-04-23):
- field name: domain
- enum: tech | methodology | auto
- default: auto
- legacy projects missing the field: runtime-treated as 'tech' (NOT backfilled)
"""
from __future__ import annotations

import json
import os

import pytest

from app.models.project import Project, ProjectManager, ProjectStatus


@pytest.fixture
def isolated_projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path))
    yield tmp_path


def test_new_project_defaults_domain_to_auto(isolated_projects_dir):
    """create_project() without explicit domain must default to 'auto'."""
    p = ProjectManager.create_project(name="test")
    assert p.domain == "auto"
    meta_path = os.path.join(
        isolated_projects_dir, p.project_id, "project.json"
    )
    data = json.loads(open(meta_path).read())
    assert data["domain"] == "auto"


def test_create_project_accepts_explicit_domain(isolated_projects_dir):
    """Callers can pass domain=tech or domain=methodology at creation."""
    p = ProjectManager.create_project(name="test", domain="methodology")
    assert p.domain == "methodology"
    meta_path = os.path.join(
        isolated_projects_dir, p.project_id, "project.json"
    )
    assert json.loads(open(meta_path).read())["domain"] == "methodology"


def test_create_project_rejects_invalid_domain(isolated_projects_dir):
    """Unknown domain values must raise at creation (fail-fast)."""
    with pytest.raises(ValueError, match="invalid domain"):
        ProjectManager.create_project(name="test", domain="news")


def test_legacy_project_without_domain_field_defaults_to_tech(isolated_projects_dir):
    """Reading a project.json that predates this feature must default to 'tech'
    at runtime, NOT 'auto' — preserves v2 behavior for frozen legacy data."""
    project_id = "proj_legacy00test"
    proj_dir = os.path.join(isolated_projects_dir, project_id)
    os.makedirs(os.path.join(proj_dir, "files"), exist_ok=True)
    legacy_data = {
        "project_id": project_id,
        "name": "legacy",
        "status": "created",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        # NOTE: no "domain" key
    }
    with open(os.path.join(proj_dir, "project.json"), "w") as f:
        json.dump(legacy_data, f)

    loaded = ProjectManager.get_project(project_id)
    assert loaded is not None
    assert loaded.domain == "tech"


def test_reading_legacy_does_not_rewrite_domain_to_disk(isolated_projects_dir):
    """Loading a legacy project must NOT backfill 'domain' into the on-disk
    JSON (GPT: 'don't rewrite old JSON — keep compat and freeze-not-migrate')."""
    project_id = "proj_legacy00keep"
    proj_dir = os.path.join(isolated_projects_dir, project_id)
    os.makedirs(os.path.join(proj_dir, "files"), exist_ok=True)
    legacy_data = {
        "project_id": project_id,
        "name": "legacy",
        "status": "created",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    meta_path = os.path.join(proj_dir, "project.json")
    with open(meta_path, "w") as f:
        json.dump(legacy_data, f)

    ProjectManager.get_project(project_id)
    data_after = json.loads(open(meta_path).read())
    assert "domain" not in data_after
