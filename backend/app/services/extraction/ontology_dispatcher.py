"""Ontology dispatcher (v3 Stage 2 part 2).

Routes a project's `domain` field to the correct ontology generator.
For `domain=auto`, delegates to DomainClassifier (Stage 4). When the
classifier's confidence is below the safe threshold, falls back to tech.
"""
from __future__ import annotations

from typing import Optional

from ..ontology_generator import OntologyGenerator
from ..methodology_ontology_generator import MethodologyOntologyGenerator


# Fallback threshold for auto-classified domains. If the classifier's
# confidence is below this, we route to 'tech' as the safe default.
# Rationale: existing system is tech-shaped; methodology misrouted to tech
# produces wrong-schema output but doesn't crash, while tech misrouted to
# methodology loses Technology/Metric/Evidence dimensions entirely.
AUTO_FALLBACK_CONFIDENCE_THRESHOLD = 0.65


def get_ontology_generator(domain: str):
    """Return an ontology generator instance for the given domain.

    `domain` must be 'tech' or 'methodology' — for 'auto', call
    resolve_project_domain() first to get a concrete value.
    """
    if domain == "tech":
        return OntologyGenerator()
    if domain == "methodology":
        return MethodologyOntologyGenerator()
    if domain == "auto":
        raise ValueError(
            "get_ontology_generator cannot handle 'auto' directly; "
            "call resolve_project_domain() first to resolve it to tech/methodology"
        )
    raise ValueError(f"unknown domain {domain!r}")


def resolve_project_domain(
    project: dict, article_text: Optional[str] = None
) -> str:
    """Resolve project.domain to a concrete 'tech' or 'methodology'.

    Rules:
    - Missing 'domain' key or 'domain'='tech' → 'tech'
    - 'domain'='methodology' → 'methodology'
    - 'domain'='auto' AND article_text provided → run DomainClassifier
    - 'domain'='auto' AND article_text is None → fallback 'tech'
    """
    domain = project.get("domain", "tech")

    if domain == "tech":
        return "tech"
    if domain == "methodology":
        return "methodology"
    if domain == "auto":
        if article_text is None:
            return "tech"
        from ..domain_classifier import DomainClassifier
        result = DomainClassifier().classify(title="", text=article_text)
        confidence = float(result.get("confidence", 0) or 0)
        primary = result.get("primary", "tech")
        if primary in {"tech", "methodology"} and confidence >= AUTO_FALLBACK_CONFIDENCE_THRESHOLD:
            return primary
        return "tech"

    raise ValueError(f"unknown project.domain {domain!r}")
