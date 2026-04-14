"""Backfill empty registry descriptions from article graph node summaries.

Scans all canonical concepts with empty descriptions, looks up their
source_links to find article graph nodes, and fills the best summary.

Rules:
- Only fills entries with empty/blank description
- Never overwrites description_source="manual"
- Records description_source metadata for audit
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from . import global_concept_registry as registry

logger = logging.getLogger("mirofish.backfill_descriptions")


_LEGACY_DEGRADED_PREFIXES = ("关联节点：", "关联节点:")


def _is_degraded_description(entry: dict[str, Any]) -> bool:
    """Match the same rule used by the panorama endpoint so UI + backfill agree.

    We *always* flag descriptions whose text matches a legacy template
    (``关联节点：…``) — even when ``description_source`` is
    ``article_node_summary``. Earlier runs of the backfill wrote that source
    tag while pulling template text from ``ConceptViewService.sampleEvidence``
    (see ``concept_view_service.py:43``), so the source tag alone is not a
    reliable "authoritative" marker for that prefix.
    """
    if entry.get("description_degraded") is True:
        return True
    desc = (entry.get("description") or "").strip()
    if not desc:
        return True
    if any(desc.startswith(p) for p in _LEGACY_DEGRADED_PREFIXES):
        return True
    # Otherwise, manual descriptions are authoritative.
    if entry.get("description_source") == "manual":
        return False
    return False


def backfill_all(*, dry_run: bool = False, overwrite_degraded: bool = False) -> dict[str, Any]:
    """Backfill empty/degraded descriptions from article graph summaries.

    Parameters
    ----------
    dry_run : when True, log actions without writing back.
    overwrite_degraded : when True, replace descriptions we classify as
        degraded (empty, template-prefix, explicitly flagged) even though
        they contain text. Manual descriptions are always preserved.
    """
    entries = registry.list_entries()

    # Cache concept views per project to avoid repeated API calls
    _view_cache: dict[str, list[dict]] = {}

    filled = 0
    skipped_has_desc = 0
    skipped_manual = 0
    skipped_no_summary = 0
    errors: list[str] = []

    for entry in entries:
        entry_id = entry["entry_id"]
        current_desc = (entry.get("description") or "").strip()

        # Skip if already has manual description
        if entry.get("description_source") == "manual":
            skipped_manual += 1
            continue

        # Skip if the existing description is authoritative AND we're not
        # trying to overwrite degraded ones.
        if current_desc:
            if overwrite_degraded and _is_degraded_description(entry):
                pass  # fall through and try to replace it
            else:
                skipped_has_desc += 1
                continue

        # Try to get summary from source article graphs
        best_summary = _find_best_summary(entry, _view_cache)

        if not best_summary:
            skipped_no_summary += 1
            continue

        if dry_run:
            preview = (best_summary.get("text") or "")[:60]
            logger.info("Would fill %s: %s", entry_id, preview)
            filled += 1
            continue

        # Write back to registry
        try:
            registry.update_entry(
                entry_id,
                description=best_summary["text"],
            )
            # Also update metadata fields directly in the JSON
            _update_description_metadata(entry_id, best_summary)
            filled += 1
        except Exception as exc:
            errors.append(f"{entry_id}: {exc}")

    return {
        "filled": filled,
        "skipped_has_desc": skipped_has_desc,
        "skipped_manual": skipped_manual,
        "skipped_no_summary": skipped_no_summary,
        "errors": errors,
        "dry_run": dry_run,
    }


def _get_project_concepts(project_id: str, cache: dict) -> list[dict]:
    """Get concept candidates for a project, with caching."""
    if project_id in cache:
        return cache[project_id]
    try:
        from ..workspace.concept_view_service import ConceptViewService
        view = ConceptViewService().build_project_view(project_id)
        concepts = view.get("candidateConcepts", [])
        cache[project_id] = concepts
        return concepts
    except Exception as exc:
        logger.warning("Failed to get concept view for %s: %s", project_id, exc)
        cache[project_id] = []
        return []


_LEGACY_EVIDENCE_PREFIXES = ("关联节点：", "关联节点:")


def _find_best_summary(
    entry: dict[str, Any],
    view_cache: dict,
) -> dict[str, Any] | None:
    """Find the best summary from source article graphs.

    Strategy:
    1. Prefer the article graph node's ``summary`` via
       :func:`resolve_source_evidence` — this is the phase-1 LLM output, the
       actual article evidence.
    2. Fall back to ``ConceptViewService.sampleEvidence`` only when the
       resolver returned nothing useful **and** the candidate text does not
       match a known legacy template prefix (``关联节点：…``). This
       prevents old stub evidence from seeping back into descriptions.
    """
    canonical_name = entry.get("canonical_name", "")
    source_links = entry.get("source_links", [])

    if not source_links:
        return None

    from .source_evidence_resolver import resolve_source_evidence

    refs = resolve_source_evidence(entry, max_refs=len(source_links))
    candidates: list[dict[str, Any]] = []
    for ref in refs:
        text = (ref.get("source_text") or "").strip()
        if not text or ref.get("degraded"):
            continue
        if any(text.startswith(p) for p in _LEGACY_EVIDENCE_PREFIXES):
            continue
        score = min(len(text), 200) / 200.0
        if canonical_name and canonical_name.lower() in text.lower():
            score += 0.3
        candidates.append({
            "text": text[:300],
            "project_id": ref.get("project_id", ""),
            "concept_key": ref.get("concept_key", ""),
            "score": score,
        })

    # Legacy fallback path — keeps backward compatibility for concepts whose
    # graph node was already pruned but whose ConceptViewService view still
    # surfaces real evidence. Skips template-prefixed candidates.
    if not candidates:
        for link in source_links:
            project_id = link.get("project_id", "")
            concept_key = link.get("concept_key", "")
            if not project_id or not concept_key:
                continue
            all_concepts = _get_project_concepts(project_id, view_cache)
            target = next((c for c in all_concepts if c.get("key") == concept_key), None)
            if not target:
                continue
            for ev in target.get("sampleEvidence", []):
                text = (ev if isinstance(ev, str) else str(ev)).strip()
                if not text or len(text) <= 10:
                    continue
                if any(text.startswith(p) for p in _LEGACY_EVIDENCE_PREFIXES):
                    continue
                score = min(len(text), 200) / 200.0
                if canonical_name and canonical_name.lower() in text.lower():
                    score += 0.3
                candidates.append({
                    "text": text[:300],
                    "project_id": project_id,
                    "concept_key": concept_key,
                    "score": score,
                })

    if not candidates:
        return None

    candidates.sort(key=lambda c: -c["score"])
    return candidates[0]


def _update_description_metadata(entry_id: str, summary: dict[str, Any]) -> None:
    """Update description source metadata directly in registry JSON."""
    store = registry._load_registry()
    entry = store["entries"].get(entry_id)
    if not entry:
        return

    entry["description_source"] = "article_node_summary"
    entry["description_source_project_id"] = summary.get("project_id", "")
    entry["description_source_node_key"] = summary.get("concept_key", "")
    entry["description_updated_at"] = datetime.now().isoformat()

    store["entries"][entry_id] = entry
    registry._save_registry(store)
