"""Review status enum for Phase 2."""

from enum import Enum


class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
