"""Pydantic schemas for the global concept registry (Stage H)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegistrySourceLinkSchema(BaseModel):
    project_id: str
    concept_key: str
    project_name: str = ""
    linked_at: str = ""


class RegistryEntrySchema(BaseModel):
    entry_id: str
    canonical_name: str
    concept_type: str = "Concept"
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    # Description provenance — None when unknown. Values: "manual" |
    # "article_node_summary" | "legacy". Consumers use this to decide
    # whether a description is authoritative enough to trust without review.
    description_source: str | None = None
    description_source_project_id: str | None = None
    description_source_node_key: str | None = None
    description_updated_at: str | None = None
    # Explicit degraded flag — surfaced when the registry knows the current
    # description is a template stub or otherwise unreliable. Downstream
    # views show a warning icon instead of hiding the issue.
    description_degraded: bool = False
    source_links: list[RegistrySourceLinkSchema] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class RegistryEntryListSchema(BaseModel):
    entries: list[RegistryEntrySchema] = Field(default_factory=list)
    total: int = 0


class RegistrySearchResultSchema(BaseModel):
    results: list[RegistryEntrySchema] = Field(default_factory=list)
    query: str = ""
    total: int = 0


# -- Suggest from project --------------------------------------------------


class SuggestNewCandidateSchema(BaseModel):
    concept_key: str
    display_name: str
    concept_type: str = "Concept"


class SuggestExistingMatchSchema(BaseModel):
    concept_key: str
    display_name: str
    concept_type: str = "Concept"
    matched_entry_id: str
    matched_canonical_name: str


class SuggestAlreadyLinkedSchema(BaseModel):
    concept_key: str
    display_name: str
    concept_type: str = "Concept"


class SuggestCrossTypeMatchSchema(BaseModel):
    concept_key: str
    display_name: str
    concept_type: str = "Concept"
    matched_entry_id: str
    matched_canonical_name: str
    matched_concept_type: str = "Concept"


class ProjectSuggestResponseSchema(BaseModel):
    project_id: str
    project_name: str = ""
    total_accepted: int = 0
    new_candidates: list[SuggestNewCandidateSchema] = Field(default_factory=list)
    existing_matches: list[SuggestExistingMatchSchema] = Field(default_factory=list)
    already_linked: list[SuggestAlreadyLinkedSchema] = Field(default_factory=list)
    cross_type_matches: list[SuggestCrossTypeMatchSchema] = Field(default_factory=list)


# -- Project alignment view -------------------------------------------------


class AlignmentItemSchema(BaseModel):
    concept_key: str
    display_name: str
    concept_type: str = "Concept"
    status: str = "unlinked"  # linked | suggested | unlinked
    registry_entry_id: str | None = None
    registry_canonical_name: str | None = None
    suggested_entry_id: str | None = None
    suggested_canonical_name: str | None = None


class AlignmentSummarySchema(BaseModel):
    linked: int = 0
    suggested: int = 0
    unlinked: int = 0
    total: int = 0


class ProjectAlignmentSchema(BaseModel):
    project_id: str
    project_name: str = ""
    summary: AlignmentSummarySchema = Field(default_factory=AlignmentSummarySchema)
    alignments: list[AlignmentItemSchema] = Field(default_factory=list)
    registry_total: int = 0
