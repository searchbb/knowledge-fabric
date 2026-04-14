"""Pydantic schemas for the global theme registry (Stage J)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GlobalThemeClusterLinkSchema(BaseModel):
    project_id: str
    cluster_id: str
    cluster_name: str = ""
    linked_at: str = ""


class ConceptMembershipSchema(BaseModel):
    entry_id: str
    role: str = "member"
    score: float = 1.0
    source: str = ""
    assigned_at: str = ""


class GlobalThemeSchema(BaseModel):
    theme_id: str
    name: str
    slug: str = ""
    description: str = ""
    status: str = "active"
    source: str = "user"
    keywords: list[str] = Field(default_factory=list)
    concept_entry_ids: list[str] = Field(default_factory=list)
    concept_memberships: list[ConceptMembershipSchema] = Field(default_factory=list)
    source_project_clusters: list[GlobalThemeClusterLinkSchema] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class GlobalThemeListSchema(BaseModel):
    themes: list[GlobalThemeSchema] = Field(default_factory=list)
    total: int = 0


class ThemeSuggestNewSchema(BaseModel):
    cluster_id: str
    cluster_name: str
    concept_count: int = 0


class ThemeSuggestMatchSchema(BaseModel):
    cluster_id: str
    cluster_name: str
    matched_theme_id: str
    matched_theme_name: str


class ThemeSuggestLinkedSchema(BaseModel):
    cluster_id: str
    cluster_name: str


class ThemeSuggestResponseSchema(BaseModel):
    project_id: str
    project_name: str = ""
    total_clusters: int = 0
    new_candidates: list[ThemeSuggestNewSchema] = Field(default_factory=list)
    existing_matches: list[ThemeSuggestMatchSchema] = Field(default_factory=list)
    already_linked: list[ThemeSuggestLinkedSchema] = Field(default_factory=list)
