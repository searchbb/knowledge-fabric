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


# ============== Stage 1.2: API integration tests ==============

def test_api_ontology_generate_accepts_domain(isolated_projects_dir, monkeypatch):
    """POST /api/graph/ontology/generate must accept 'domain' in form body
    and pass it to ProjectManager.create_project."""
    import io
    from datetime import datetime
    from app import create_app
    from app.models.project import Project, ProjectManager, ProjectStatus

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    captured_domain: list[str] = []

    def _spy_create(cls, *args, **kwargs):
        captured_domain.append(kwargs.get("domain", "MISSING"))
        return Project(
            project_id="proj_test00",
            name=kwargs.get("name", ""),
            status=ProjectStatus.CREATED,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            domain=kwargs.get("domain", "auto"),
        )

    monkeypatch.setattr(ProjectManager, "create_project", classmethod(_spy_create))

    # Mock save_file_to_project so no real disk I/O happens
    def _fake_save(cls, project_id, file_obj, filename, vault_relative_dir=None):
        return {
            "original_filename": filename,
            "size": 10,
            "source_backend": "local",
            "source_md_path": None,
            "vault_relative_dir": None,
            "path": "/tmp/fake.txt",
        }

    monkeypatch.setattr(ProjectManager, "save_file_to_project", classmethod(_fake_save))

    # Mock file text extraction
    import app.utils.file_parser as fp_mod
    import app.services.text_processor as tp_mod
    monkeypatch.setattr(fp_mod.FileParser, "extract_text", staticmethod(lambda path: "sample text"))
    monkeypatch.setattr(tp_mod.TextProcessor, "preprocess_text", staticmethod(lambda t: t))

    # Mock save_extracted_text and save_project to avoid real fs writes
    monkeypatch.setattr(ProjectManager, "save_extracted_text", classmethod(lambda cls, pid, txt: None))
    monkeypatch.setattr(ProjectManager, "save_project", classmethod(lambda cls, p: None))

    # Mock OntologyGenerator to avoid real LLM call
    import app.services.ontology_generator as ogm
    monkeypatch.setattr(
        ogm.OntologyGenerator,
        "generate",
        lambda self, **kw: {"entity_types": [], "edge_types": [], "analysis_summary": ""},
    )

    data = {
        "project_name": "test",
        "simulation_requirement": "test requirement",
        "domain": "methodology",
    }
    file_data = {"files": (io.BytesIO(b"hello world"), "test.txt")}

    resp = client.post(
        "/api/graph/ontology/generate",
        data={**data, **file_data},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.data
    assert captured_domain == ["methodology"]


def test_api_ontology_generate_rejects_invalid_domain(isolated_projects_dir):
    """Invalid domain must return 400 before any file processing."""
    import io
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    resp = client.post(
        "/api/graph/ontology/generate",
        data={
            "project_name": "test",
            "simulation_requirement": "test requirement",
            "domain": "news",  # invalid
            "files": (io.BytesIO(b"hello"), "test.txt"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
