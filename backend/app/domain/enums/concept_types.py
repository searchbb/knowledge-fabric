"""Concept type enum for Phase 2."""

from enum import Enum


class ConceptType(str, Enum):
    DOCUMENT = "document"
    CHUNK = "chunk"
    LOCAL_CONCEPT = "local_concept"
    CANONICAL_ENTITY = "canonical_entity"
    THEME = "theme"
