"""Resolve canonical concept source_links → article-graph node evidence.

For "theme → concept → bridging relation → source article" traceability we
need to pin every cross-concept relation endpoint to the actual sentence-
level evidence that lives in the source article's graph.

Each canonical concept carries ``source_links`` like::

    {"project_id": "proj_xxx", "concept_key": "Problem:知识线性传递",
     "project_name": "..."}

The source article's graph contains nodes with ``name`` and ``labels`` that
correspond to ``concept_key``. Each node also carries a ``summary`` — the
LLM-extracted support sentence — and a stable ``uuid``.

This module exposes a single helper :func:`resolve_source_evidence` that
walks every source_link of a canonical concept and returns the best-match
node's uuid + summary + deep-link metadata so downstream consumers
(cross_concept_discoverer, UI cards, migration scripts) can hand the user
both the article name *and* the specific supporting sentence.

Zero-fallback rule: if we cannot find a matching graph node we return a
``degraded=True`` ref with an explanatory ``degraded_reason`` instead of a
plausible-looking fake. Callers must propagate that flag to the UI.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from ...models.project import ProjectManager
from ..workspace.project_workspace_sources import load_graph_data

logger = logging.getLogger("mirofish.source_evidence_resolver")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_concept_key(concept_key: str) -> tuple[str, str]:
    """Split ``concept_key`` (e.g. ``Problem:知识线性传递``) into ``(label, name)``.

    The split is on the *first* colon only — entity names may contain colons.
    Returns ``("", concept_key)`` when the key has no colon, letting callers
    fall back to name-only matching.
    """
    if not concept_key:
        return "", ""
    idx = concept_key.find(":")
    if idx < 0:
        return "", concept_key.strip()
    return concept_key[:idx].strip(), concept_key[idx + 1 :].strip()


def _graph_cache_key(graph_id: str) -> str:
    return f"graph::{graph_id}"


class _GraphCache:
    """Per-call cache so one migration pass doesn't reload the same graph."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get_or_load(self, graph_id: str) -> dict[str, Any]:
        if not graph_id:
            return {}
        if graph_id not in self._store:
            try:
                self._store[graph_id] = load_graph_data(graph_id) or {}
            except Exception as exc:
                logger.warning("Failed to load graph %s: %s", graph_id, exc)
                self._store[graph_id] = {}
        return self._store[graph_id]


def _resolve_project_graph_id(project_id: str) -> str:
    """Map a project_id to its graph_id, or empty string if project is missing."""
    project = ProjectManager.get_project(project_id)
    if not project:
        return ""
    return getattr(project, "graph_id", "") or ""


def _normalize_for_match(value: str) -> str:
    """Project-wide concept_key normalizer matches the ingestion pipeline.

    ``concept_key`` is stored lowercase (``Topic:ai工作台``) but graph nodes
    keep original casing (``AI工作台``). We lowercase + strip both sides so
    the reverse lookup succeeds without breaking same-name disambiguation —
    the label check still separates ``Topic:agent`` from ``Solution:agent``.
    """
    return (value or "").strip().lower()


def _find_node(graph_data: dict[str, Any], label: str, name: str) -> dict[str, Any] | None:
    """Locate the node matching ``label`` and ``name`` inside ``graph_data``.

    Matching rules:

    * ``label`` check is case-sensitive because graph labels are a closed
      vocabulary (Problem/Solution/Technology/...) and case is stable.
    * ``name`` match is case-insensitive after stripping — ``concept_key``
      is stored lowercase while graph nodes keep original casing.
    * When both a case-sensitive and a case-insensitive candidate exist we
      prefer the strict match (keeps stable matching when two distinct
      names differ only by case).
    * We intentionally do not fall back to label-less name matching —
      that would collapse same-name disambiguation (TC-M5-b01).
    """
    if not graph_data:
        return None

    strict_hit: dict[str, Any] | None = None
    relaxed_hit: dict[str, Any] | None = None
    target_norm = _normalize_for_match(name)

    for node in graph_data.get("nodes") or []:
        raw_name = str(node.get("name") or "").strip()
        if not raw_name:
            continue
        labels = [str(l or "").strip() for l in (node.get("labels") or [])]
        if label and label not in labels:
            continue
        if raw_name == name:
            strict_hit = node
            break
        if _normalize_for_match(raw_name) == target_norm:
            relaxed_hit = relaxed_hit or node

    return strict_hit or relaxed_hit


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _resolve_project_group_titles(project_id: str) -> dict[str, str]:
    """Return the project's ``reading_structure.group_titles`` label→title map.

    Used to surface a human-readable section label (e.g. ``Problem`` →
    ``核心问题``) next to a source ref so the UI can show which part of the
    article the evidence lives in (necessary for the "不要缺失原文" goal).
    Empty dict when missing; callers gracefully fall back to raw label.
    """
    project = ProjectManager.get_project(project_id)
    if not project:
        return {}
    rs = dict(getattr(project, "reading_structure", None) or {})
    group_titles = rs.get("group_titles") or {}
    if not isinstance(group_titles, dict):
        return {}
    return {str(k): str(v) for k, v in group_titles.items() if v}


def build_source_ref(
    *,
    entry_id: str,
    link: dict[str, Any],
    graph_cache: _GraphCache | None = None,
) -> dict[str, Any]:
    """Return an evidence ref for a single ``source_link`` of a canonical concept.

    Shape::

        {
          "entry_id": canonical entry id,
          "project_id": ..., "project_name": ..., "concept_key": ...,
          "source_node_uuid": graph node uuid or "",
          "source_text": the node's summary (= LLM-extracted article support) or "",
          "group_label": node label (e.g. "Problem") — empty when unknown,
          "group_title": human-readable section from reading_structure — empty when unmapped,
          "degraded": True when no node/summary was available,
          "degraded_reason": human-readable explanation (only when degraded)
        }
    """
    cache = graph_cache or _GraphCache()

    project_id = str(link.get("project_id") or "").strip()
    project_name = str(link.get("project_name") or "").strip()
    concept_key = str(link.get("concept_key") or "").strip()
    label, name = _parse_concept_key(concept_key)

    ref: dict[str, Any] = {
        "entry_id": entry_id,
        "project_id": project_id,
        "project_name": project_name,
        "concept_key": concept_key,
        "source_node_uuid": "",
        "source_text": "",
        "group_label": label,
        "group_title": "",
        "degraded": False,
    }

    if not project_id:
        ref["degraded"] = True
        ref["degraded_reason"] = "missing project_id on source_link"
        return ref

    # Fill group_title from reading_structure even if we later degrade on the
    # node lookup — knowing "this was a Problem-section concept" is still
    # useful context for the user.
    group_titles = _resolve_project_group_titles(project_id)
    if label and group_titles.get(label):
        ref["group_title"] = group_titles[label]

    graph_id = _resolve_project_graph_id(project_id)
    if not graph_id:
        ref["degraded"] = True
        ref["degraded_reason"] = f"project {project_id} has no graph_id"
        return ref

    graph_data = cache.get_or_load(graph_id)
    if not graph_data or not (graph_data.get("nodes") or []):
        ref["degraded"] = True
        ref["degraded_reason"] = f"graph {graph_id} is empty or unloadable"
        return ref

    node = _find_node(graph_data, label, name)
    if not node:
        ref["degraded"] = True
        ref["degraded_reason"] = (
            f"no graph node matches label={label!r} name={name!r} in {graph_id}"
        )
        return ref

    summary = str(node.get("summary") or "").strip()
    ref["source_node_uuid"] = str(node.get("uuid") or "")
    ref["source_text"] = summary
    # Prefer the node's own label when we can read the graph — that's
    # authoritative vs. the concept_key prefix which might have drifted.
    node_labels = [str(l or "").strip() for l in (node.get("labels") or []) if l]
    if node_labels:
        ref["group_label"] = node_labels[0]
        if group_titles.get(node_labels[0]):
            ref["group_title"] = group_titles[node_labels[0]]
    if not summary:
        ref["degraded"] = True
        ref["degraded_reason"] = "matched node has empty summary"
    return ref


def resolve_source_evidence(
    entry: dict[str, Any],
    *,
    max_refs: int = 3,
    graph_cache: _GraphCache | None = None,
) -> list[dict[str, Any]]:
    """Return evidence refs for a canonical concept, best-first.

    Parameters
    ----------
    entry : canonical concept dict (must include ``entry_id`` and ``source_links``)
    max_refs : maximum refs to return (default 3). Canonical concepts that
        appear in multiple articles still surface evidence per article.
    graph_cache : optional cache shared across calls (use in migrations).
    """
    cache = graph_cache or _GraphCache()
    entry_id = entry.get("entry_id", "")
    links = entry.get("source_links") or []
    refs: list[dict[str, Any]] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        refs.append(build_source_ref(entry_id=entry_id, link=link, graph_cache=cache))
        if len(refs) >= max_refs:
            break
    # Put non-degraded refs first, then degraded (keeps UI scan order useful)
    refs.sort(key=lambda r: (1 if r.get("degraded") else 0, -len(r.get("source_text") or "")))
    return refs


def build_evidence_refs_for_pair(
    *,
    source_entry: dict[str, Any],
    target_entry: dict[str, Any],
    graph_cache: _GraphCache | None = None,
) -> list[dict[str, Any]]:
    """Return the best available evidence refs for both endpoints of a xrel.

    One ref per endpoint, source-first. Callers can concatenate with a
    separate ``evidence_bridge`` (LLM-authored connective text) without
    duplicating content.
    """
    cache = graph_cache or _GraphCache()
    refs: list[dict[str, Any]] = []
    for side in (source_entry, target_entry):
        if not isinstance(side, dict):
            continue
        side_refs = resolve_source_evidence(side, max_refs=1, graph_cache=cache)
        if side_refs:
            refs.append(side_refs[0])
    return refs


__all__ = [
    "_GraphCache",
    "build_evidence_refs_for_pair",
    "build_source_ref",
    "resolve_source_evidence",
]
