"""Resolution decision enum for Phase 2."""

from enum import Enum


class ResolutionDecision(str, Enum):
    MERGE = "merge"
    CREATE_NEW = "create_new"
    CHILD_OF = "child_of"
    RELATED = "related"
    SKIP = "skip"
