"""Document-layer models for the Phase 2 scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DocumentRecord:
    document_id: str
    project_id: str
    title: str
    source_path: str = ""
    source_url: str = ""
    chunk_ids: list[str] = field(default_factory=list)
