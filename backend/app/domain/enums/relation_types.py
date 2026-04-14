"""Relation type enum for Phase 2."""

from enum import Enum


class RelationType(str, Enum):
    MENTIONS = "mentions"
    ALIGNS_TO = "aligns_to"
    BELONGS_TO_THEME = "belongs_to_theme"
    RELATED_TO = "related_to"
    DERIVED_FROM = "derived_from"
