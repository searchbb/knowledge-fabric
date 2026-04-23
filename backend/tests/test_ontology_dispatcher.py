"""Tests for ontology dispatcher (v3 Stage 2 part 2).

Dispatcher routes domain -> appropriate OntologyGenerator. Also resolves
'auto' by calling DomainClassifier (Stage 4 — xfail until then).
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from app.services.extraction.ontology_dispatcher import (
    get_ontology_generator,
    resolve_project_domain,
)
from app.services.ontology_generator import OntologyGenerator
from app.services.methodology_ontology_generator import MethodologyOntologyGenerator


def test_get_ontology_generator_tech_returns_OntologyGenerator():
    gen = get_ontology_generator("tech")
    assert isinstance(gen, OntologyGenerator)


def test_get_ontology_generator_methodology_returns_MethodologyOntologyGenerator():
    gen = get_ontology_generator("methodology")
    assert isinstance(gen, MethodologyOntologyGenerator)


def test_get_ontology_generator_rejects_invalid_domain():
    with pytest.raises(ValueError, match="unknown domain"):
        get_ontology_generator("news")


def test_get_ontology_generator_rejects_auto_directly():
    """'auto' must be resolved via resolve_project_domain first."""
    with pytest.raises(ValueError, match="auto"):
        get_ontology_generator("auto")


def test_resolve_domain_passes_through_explicit_tech():
    """If project.domain is 'tech', return 'tech' without calling classifier."""
    resolved = resolve_project_domain({"domain": "tech"}, article_text="some text")
    assert resolved == "tech"


def test_resolve_domain_passes_through_explicit_methodology():
    resolved = resolve_project_domain({"domain": "methodology"}, article_text="t")
    assert resolved == "methodology"


def test_resolve_domain_auto_without_text_falls_back_to_tech():
    """If article_text is None (classifier can't run), auto fallbacks to tech."""
    resolved = resolve_project_domain({"domain": "auto"}, article_text=None)
    assert resolved == "tech"


def test_resolve_domain_missing_field_treats_as_tech():
    """Legacy project dict without 'domain' key → tech."""
    resolved = resolve_project_domain({}, article_text=None)
    assert resolved == "tech"


def test_resolve_domain_auto_with_text_invokes_classifier():
    """When text is provided, 'auto' delegates to DomainClassifier."""
    with patch(
        "app.services.extraction.ontology_dispatcher.DomainClassifier"
    ) as mock_cls:
        mock_cls.return_value.classify.return_value = {
            "primary": "methodology",
            "confidence": 0.82,
            "secondary": "tech",
            "secondary_confidence": 0.3,
            "reason": "test",
        }
        resolved = resolve_project_domain(
            {"domain": "auto"}, article_text="some article content"
        )
    assert resolved == "methodology"
