"""Tests for theme registry domain partitioning (v3 Stage 3).

Per GPT consult 2026-04-23:
- Each theme gets a 'domain' field at creation
- list_themes(domain=None) returns all (backward compat)
- list_themes(domain='tech') returns tech themes only; excludes unknown/methodology
- list_themes(domain='unknown') returns legacy themes lacking the field
- Old themes (pre-v3) have no 'domain' field → treated as 'unknown' at runtime
- New themes MUST provide domain at creation (fail-fast)
"""
from __future__ import annotations

import json

import pytest

from app.services.registry import global_theme_registry as reg


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Route the theme store to a per-test tmp file.

    The module computes the path via _themes_path() at call time; there is no
    simple module-level path constant to monkeypatch.  We patch the function
    itself to return our tmp path, which also makes _load_themes and
    _save_themes use it automatically.
    """
    store_path = tmp_path / "global_themes.json"
    store_path.write_text(json.dumps({"themes": {}}))

    monkeypatch.setattr(reg, "_themes_path", lambda: str(store_path))

    # Clear any cached store (in case _load_themes is cached elsewhere)
    loader = getattr(reg, "_load_themes", None)
    if loader is not None and hasattr(loader, "cache_clear"):
        loader.cache_clear()
    yield store_path


def test_create_theme_persists_domain_field(isolated_store):
    t = reg.create_theme(
        name="Tech Theme", status="active", source="test", domain="tech",
    )
    assert t["domain"] == "tech"
    data = json.loads(isolated_store.read_text())
    stored = data["themes"][t["theme_id"]]
    assert stored["domain"] == "tech"


def test_create_theme_without_domain_raises(isolated_store):
    """Per GPT: 新写入 theme 必须带 domain → raise for omission."""
    with pytest.raises(ValueError, match="domain is required"):
        reg.create_theme(name="X", status="active", source="test")


def test_create_theme_rejects_invalid_domain(isolated_store):
    with pytest.raises(ValueError, match="invalid domain"):
        reg.create_theme(name="X", status="active", source="test", domain="news")


def test_list_themes_no_domain_filter_returns_all(isolated_store):
    reg.create_theme(name="t1", status="active", source="s", domain="tech")
    reg.create_theme(name="m1", status="active", source="s", domain="methodology")
    themes = reg.list_themes()
    assert len(themes) == 2


def test_list_themes_filter_by_tech_excludes_methodology(isolated_store):
    reg.create_theme(name="t1", status="active", source="s", domain="tech")
    reg.create_theme(name="m1", status="active", source="s", domain="methodology")
    tech_themes = reg.list_themes(domain="tech")
    names = {t["name"] for t in tech_themes}
    assert names == {"t1"}


def test_list_themes_filter_by_methodology_excludes_tech(isolated_store):
    reg.create_theme(name="t1", status="active", source="s", domain="tech")
    reg.create_theme(name="m1", status="active", source="s", domain="methodology")
    m_themes = reg.list_themes(domain="methodology")
    assert {t["name"] for t in m_themes} == {"m1"}


def test_list_themes_status_and_domain_both_apply(isolated_store):
    reg.create_theme(name="t_active", status="active", source="s", domain="tech")
    reg.create_theme(name="t_cand", status="candidate", source="s", domain="tech")
    reg.create_theme(name="m_active", status="active", source="s", domain="methodology")
    got = reg.list_themes(status="active", domain="tech")
    assert {t["name"] for t in got} == {"t_active"}


def test_legacy_theme_without_domain_treated_as_unknown(isolated_store):
    """Themes written before v3 have no 'domain' field. Runtime must treat
    them as 'unknown' and EXCLUDE from typed domain queries by default."""
    legacy_data = {
        "themes": {
            "gtheme_legacy001": {
                "theme_id": "gtheme_legacy001",
                "name": "legacy",
                "status": "active",
                "source": "user",
                "keywords": [],
                "concept_memberships": [],
                # NO domain field
            }
        }
    }
    isolated_store.write_text(json.dumps(legacy_data))

    all_themes = reg.list_themes()
    assert len(all_themes) == 1

    tech_themes = reg.list_themes(domain="tech")
    assert tech_themes == []

    m_themes = reg.list_themes(domain="methodology")
    assert m_themes == []

    unknown = reg.list_themes(domain="unknown")
    assert len(unknown) == 1
    assert unknown[0]["name"] == "legacy"
