"""Pydantic schemas for the global concept registry (Stage H)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegistrySourceLinkSchema(BaseModel):
    project_id: str
    concept_key: str
    project_name: str = ""
    linked_at: str = ""


class RegistrySourceEvidenceRefSchema(BaseModel):
    entry_id: str = ""
    project_id: str = ""
    project_name: str = ""
    concept_key: str = ""
    source_node_uuid: str = ""
    source_text: str = ""
    source_excerpt: str = ""
    source_context: str = ""
    source_article_id: str = ""
    source_article_title: str = ""
    source_markdown_path: str = ""
    source_content_hash: str = ""
    source_material_slice_id: str = ""
    source_lead_id: str = ""
    group_label: str = ""
    group_title: str = ""
    degraded: bool = False
    degraded_reason: str = ""
    resolved_from: str = ""


class RegistryEntrySchema(BaseModel):
    entry_id: str
    concept_id: str | None = None
    canonical_name: str
    label: str | None = None
    concept_type: str = "Concept"
    asset_type: str | None = None
    aliases: list[str] = Field(default_factory=list)
    definition: str | None = None
    description: str = ""
    lifecycle_status: str | None = None
    quality_state: str | None = None
    review_state: str | None = None
    confidence: float | None = None
    created_from: str | None = None
    created_by: str | None = None
    source_article_id: str | None = None
    source_markdown_path: str | None = None
    source_content_hash: str | None = None
    source_quote: str | None = None
    source_excerpt: str | None = None
    source_context: str | None = None
    source_article_title: str | None = None
    digest_input_text: str | None = None
    digested_text: str | None = None
    related_existing_concepts: list[dict[str, Any]] = Field(default_factory=list)
    source_lead_id: str | None = None
    source_material_slice_id: str | None = None
    linked_topic_cluster_ids: list[str] = Field(default_factory=list)
    linked_research_project_ids: list[str] = Field(default_factory=list)
    linked_wiki_topic_ids: list[str] = Field(default_factory=list)
    graph_status: str | None = None
    material_graph_id: str | None = None
    graph_node_count: int | None = None
    graph_edge_count: int | None = None
    cross_article_link_count: int | None = None
    graphification_request_id: str | None = None
    graphification_request_ids: list[str] = Field(default_factory=list)
    version: int | None = None
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
    source_evidence_refs: list[RegistrySourceEvidenceRefSchema] = Field(default_factory=list)
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
