"""Global (cross-project) theme registry — Hub-and-Spoke model.

2026-04-12 redesign: themes are global knowledge-domain hubs that concepts
from multiple articles converge on. Each theme has `concept_memberships`
with per-concept role (member/candidate) and confidence score.

JSON is source of truth. Neo4j is fire-and-forget mirror.

Storage: ``<PROJECTS_DIR>/global_themes.json``
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid as uuid_mod
from datetime import datetime
from typing import Any

from ...config import Config

logger = logging.getLogger("mirofish.theme_registry")

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

_THEMES_FILENAME = "global_themes.json"

# Cap on entries kept in ``theme["discovery_history"]``. Ten is enough to
# see "is recall quality trending" without turning the themes JSON into a
# log file. Raise with care — every entry carries a full funnel dict.
_DISCOVERY_HISTORY_MAX = 10


def _themes_path() -> str:
    projects_dir = os.path.join(Config.UPLOAD_FOLDER, "projects")
    os.makedirs(projects_dir, exist_ok=True)
    return os.path.join(projects_dir, _THEMES_FILENAME)


def _load_themes() -> dict[str, Any]:
    path = _themes_path()
    if not os.path.exists(path):
        return {"version": 2, "themes": {}}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("version", 2)
    data.setdefault("themes", {})
    return data


def _save_themes(data: dict[str, Any]) -> None:
    path = _themes_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _neo4j_sync_theme(theme: dict) -> None:
    """Fire-and-forget Neo4j mirror sync for a single theme."""
    try:
        from ...repositories.neo4j.theme_repository import ThemeNeo4jRepository
        repo = ThemeNeo4jRepository()
        repo.sync_theme(theme)
        for m in theme.get("concept_memberships", []):
            repo.sync_membership(
                entry_id=m["entry_id"],
                theme_id=theme["theme_id"],
                score=m.get("score", 1.0),
                role=m.get("role", "member"),
                source=m.get("source", "sync"),
            )
    except Exception as e:
        logger.warning("Neo4j sync theme %s failed (non-fatal): %s", theme.get("theme_id"), e)


def _neo4j_delete_theme(theme_id: str) -> None:
    try:
        from ...repositories.neo4j.theme_repository import ThemeNeo4jRepository
        ThemeNeo4jRepository().delete_theme(theme_id)
    except Exception as e:
        logger.warning("Neo4j delete theme %s failed (non-fatal): %s", theme_id, e)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", name.strip().lower())
    return slug.strip("-")[:64]


# ---------------------------------------------------------------------------
# Backward compat: compute concept_entry_ids from memberships
# ---------------------------------------------------------------------------


def _compat_entry_ids(theme: dict) -> list[str]:
    """Return flat concept_entry_ids list from concept_memberships."""
    return sorted(set(m["entry_id"] for m in theme.get("concept_memberships", [])))


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class GlobalThemeNotFoundError(KeyError):
    pass


class GlobalThemeDuplicateError(ValueError):
    pass


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def list_themes(
    *,
    status: str | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    store = _load_themes()
    themes = list(store["themes"].values())
    if status:
        themes = [t for t in themes if t.get("status") == status]
    if domain is not None:
        if domain == "unknown":
            themes = [t for t in themes if "domain" not in t]
        else:
            themes = [t for t in themes if t.get("domain") == domain]
    for t in themes:
        t["concept_entry_ids"] = _compat_entry_ids(t)
    themes.sort(key=lambda t: t.get("name", "").lower())
    return themes


def get_theme(theme_id: str) -> dict[str, Any]:
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"全局主题不存在: {theme_id}")
    theme["concept_entry_ids"] = _compat_entry_ids(theme)
    return theme


def create_theme(
    *,
    name: str,
    description: str = "",
    status: str = "active",
    source: str = "user",
    keywords: list[str] | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    if domain is None:
        raise ValueError(
            "domain is required for new themes (v3 Stage 3). "
            "Pass domain='tech' or domain='methodology'."
        )
    if domain not in {"tech", "methodology"}:
        raise ValueError(
            f"invalid domain {domain!r} — must be 'tech' or 'methodology'"
        )

    name = name.strip()
    if not name:
        raise ValueError("name 不能为空")

    store = _load_themes()
    name_lower = name.lower()
    # Uniqueness check is domain-scoped (v3 domain-scoped ontology): themes
    # in different domains (tech/methodology) can legitimately share a name.
    # Legacy themes without a 'domain' field are treated as 'unknown' — new
    # themes in tech/methodology never collide with them regardless of name.
    for existing in store["themes"].values():
        if existing["name"].lower() != name_lower:
            continue
        if existing.get("domain") == domain:
            raise GlobalThemeDuplicateError(
                f"已存在同名全局主题 (domain={domain}): {existing['name']}"
            )

    now = datetime.now().isoformat()
    theme_id = f"gtheme_{uuid_mod.uuid4().hex[:10]}"
    theme: dict[str, Any] = {
        "theme_id": theme_id,
        "name": name,
        "slug": _slugify(name),
        "description": description,
        "status": status,
        "source": source,
        "domain": domain,
        "keywords": keywords or [],
        "concept_memberships": [],
        "source_project_clusters": [],
        "evidence_refs": [],
        "created_at": now,
        "updated_at": now,
    }

    store["themes"][theme_id] = theme
    _save_themes(store)
    _neo4j_sync_theme(theme)

    from .evolution_log import emit_event
    emit_event(
        event_type="created", entity_type="global_theme",
        entity_id=theme_id, entity_name=name,
    )

    theme["concept_entry_ids"] = []
    return theme


def update_theme(
    theme_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"全局主题不存在: {theme_id}")

    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("name 不能为空")
        name_lower = name.lower()
        for tid, existing in store["themes"].items():
            if tid != theme_id and existing["name"].lower() == name_lower:
                raise GlobalThemeDuplicateError(f"已存在同名全局主题: {existing['name']}")
        theme["name"] = name
        theme["slug"] = _slugify(name)

    if description is not None:
        theme["description"] = description
    if status is not None and status in ("active", "archived", "candidate"):
        theme["status"] = status
    if keywords is not None:
        theme["keywords"] = keywords

    theme["updated_at"] = datetime.now().isoformat()
    _save_themes(store)
    _neo4j_sync_theme(theme)

    from .evolution_log import emit_event
    emit_event(
        event_type="updated", entity_type="global_theme",
        entity_id=theme_id, entity_name=theme["name"],
    )

    theme["concept_entry_ids"] = _compat_entry_ids(theme)
    return theme


def delete_theme(theme_id: str) -> bool:
    store = _load_themes()
    if theme_id not in store["themes"]:
        return False
    deleted_name = store["themes"][theme_id].get("name", "")
    del store["themes"][theme_id]
    _save_themes(store)
    _neo4j_delete_theme(theme_id)

    from .evolution_log import emit_event
    emit_event(
        event_type="deleted", entity_type="global_theme",
        entity_id=theme_id, entity_name=deleted_name,
    )
    return True


# ---------------------------------------------------------------------------
# Concept membership (hub-and-spoke model)
# ---------------------------------------------------------------------------


def attach_concepts(
    theme_id: str,
    concept_entry_ids: list[str],
    *,
    role: str = "member",
    score: float = 1.0,
    actor_type: str = "human",
    actor_id: str = "",
    run_id: str = "",
    source: str = "workspace_ui",
) -> dict[str, Any]:
    """Attach concepts with role and score (hub-and-spoke model)."""
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"全局主题不存在: {theme_id}")

    theme.setdefault("concept_memberships", [])
    existing_ids = {m["entry_id"] for m in theme["concept_memberships"]}
    now = datetime.now().isoformat()

    newly_added = []
    updated_existing = False
    for cid in concept_entry_ids:
        if cid in existing_ids:
            # Update existing membership
            for m in theme["concept_memberships"]:
                if m["entry_id"] == cid:
                    if (
                        m.get("role") != role
                        or m.get("score") != score
                        or m.get("source") != source
                    ):
                        m["role"] = role
                        m["score"] = score
                        m["source"] = source
                        m["assigned_at"] = now
                        updated_existing = True
                    break
        else:
            theme["concept_memberships"].append({
                "entry_id": cid,
                "role": role,
                "score": score,
                "source": source,
                "assigned_at": now,
            })
            newly_added.append(cid)

    if not newly_added and not updated_existing:
        theme["concept_entry_ids"] = _compat_entry_ids(theme)
        return theme

    theme["updated_at"] = now
    _save_themes(store)
    _neo4j_sync_theme(theme)

    if newly_added:
        from .evolution_log import emit_event
        emit_event(
            event_type="concept_attached",
            entity_type="global_theme",
            entity_id=theme_id,
            entity_name=theme.get("name", ""),
            details={"concept_entry_ids": newly_added, "role": role, "score": score},
            actor_type=actor_type,
            actor_id=actor_id,
            run_id=run_id,
            source=source,
        )

    theme["concept_entry_ids"] = _compat_entry_ids(theme)
    return theme


def detach_concepts(
    theme_id: str,
    concept_entry_ids: list[str],
    *,
    actor_type: str = "human",
    actor_id: str = "",
    run_id: str = "",
    source: str = "workspace_ui",
) -> dict[str, Any]:
    """Detach concepts from a theme."""
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"全局主题不存在: {theme_id}")

    remove_set = set(concept_entry_ids)
    before_memberships = list(theme.get("concept_memberships", []))
    removed_ids = [
        m["entry_id"]
        for m in before_memberships
        if m["entry_id"] in remove_set
    ]
    theme["concept_memberships"] = [
        m for m in before_memberships
        if m["entry_id"] not in remove_set
    ]
    actually_removed = len(removed_ids)

    if actually_removed == 0:
        theme["concept_entry_ids"] = _compat_entry_ids(theme)
        return theme

    theme["updated_at"] = datetime.now().isoformat()
    _save_themes(store)
    _neo4j_sync_theme(theme)

    from .evolution_log import emit_event
    emit_event(
        event_type="concept_detached",
        entity_type="global_theme",
        entity_id=theme_id,
        entity_name=theme.get("name", ""),
        details={"concept_entry_ids": removed_ids, "removed_count": actually_removed},
        actor_type=actor_type, actor_id=actor_id, run_id=run_id, source=source,
    )

    theme["concept_entry_ids"] = _compat_entry_ids(theme)
    return theme


def set_theme_status(theme_id: str, new_status: str) -> dict[str, Any]:
    """Flip a theme's lifecycle status (candidate / active / merged / archived).

    Used by M2 (candidate→active auto-promotion, GPT consult d10c98cab0b64a56)
    and future human overrides. Emits an evolution event with the transition
    so audit callers can reconstruct the theme lifecycle.
    """
    valid = {"candidate", "active", "merged", "archived", "rejected_duplicate"}
    if new_status not in valid:
        raise ValueError(f"invalid theme status {new_status!r}; valid={sorted(valid)}")

    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(theme_id)

    old_status = theme.get("status", "active")
    if old_status == new_status:
        theme["concept_entry_ids"] = _compat_entry_ids(theme)
        return theme
    theme["status"] = new_status
    theme["updated_at"] = datetime.now().isoformat()
    _save_themes(store)
    _neo4j_sync_theme(theme)

    from .evolution_log import emit_event
    emit_event(
        event_type="theme_status_changed",
        entity_type="global_theme",
        entity_id=theme_id,
        entity_name=theme.get("name", ""),
        details={"from": old_status, "to": new_status},
    )
    theme["concept_entry_ids"] = _compat_entry_ids(theme)
    return theme


def promote_candidate(theme_id: str, entry_ids: list[str]) -> dict[str, Any]:
    """Promote candidate memberships to member role."""
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(theme_id)
    promote_set = set(entry_ids)
    for m in theme.get("concept_memberships", []):
        if m["entry_id"] in promote_set and m.get("role") == "candidate":
            m["role"] = "member"
            m["score"] = max(m.get("score", 0), 0.78)
            m["assigned_at"] = datetime.now().isoformat()
    theme["updated_at"] = datetime.now().isoformat()
    _save_themes(store)
    _neo4j_sync_theme(theme)
    theme["concept_entry_ids"] = _compat_entry_ids(theme)
    return theme


def reject_candidate(theme_id: str, entry_ids: list[str]) -> dict[str, Any]:
    """Remove candidate memberships (rejected by user)."""
    return detach_concepts(theme_id, entry_ids, source="governance_reject")


def merge_themes(source_theme_id: str, target_theme_id: str) -> dict[str, Any]:
    """Merge source theme into target: move all memberships, delete source."""
    store = _load_themes()
    source = store["themes"].get(source_theme_id)
    target = store["themes"].get(target_theme_id)
    if not source:
        raise GlobalThemeNotFoundError(f"source theme {source_theme_id} not found")
    if not target:
        raise GlobalThemeNotFoundError(f"target theme {target_theme_id} not found")

    target.setdefault("concept_memberships", [])
    existing_ids = {m["entry_id"] for m in target["concept_memberships"]}
    for m in source.get("concept_memberships", []):
        if m["entry_id"] not in existing_ids:
            target["concept_memberships"].append(m)
            existing_ids.add(m["entry_id"])

    del store["themes"][source_theme_id]
    target["updated_at"] = datetime.now().isoformat()
    _save_themes(store)
    _neo4j_delete_theme(source_theme_id)
    _neo4j_sync_theme(target)

    from .evolution_log import emit_event
    emit_event(
        event_type="theme_merged", entity_type="global_theme",
        entity_id=target_theme_id,
        entity_name=target["name"],
        details={"merged_from": source_theme_id, "merged_from_name": source.get("name")},
    )

    target["concept_entry_ids"] = _compat_entry_ids(target)
    return target


# ---------------------------------------------------------------------------
# Hub view + orphans
# ---------------------------------------------------------------------------


def get_hub_view(theme_id: str) -> dict[str, Any]:
    """Build a rich hub-and-spoke view payload for a single theme."""
    theme = get_theme(theme_id)
    memberships = theme.get("concept_memberships", [])

    # Load concept registry for names and project links
    from . import global_concept_registry as registry
    all_entries = {e["entry_id"]: e for e in registry.list_entries()}

    members = []
    candidates = []
    related_projects: dict[str, dict] = {}

    for m in memberships:
        entry = all_entries.get(m["entry_id"], {})
        item = {
            "entry_id": m["entry_id"],
            "canonical_name": entry.get("canonical_name", m["entry_id"]),
            "concept_type": entry.get("concept_type", "Concept"),
            "score": m.get("score", 1.0),
            "role": m.get("role", "member"),
            "source": m.get("source", ""),
        }
        if m.get("role") == "candidate":
            candidates.append(item)
        else:
            members.append(item)

        # Track related projects
        for link in entry.get("source_links", []):
            pid = link.get("project_id", "")
            if pid and pid not in related_projects:
                related_projects[pid] = {
                    "project_id": pid,
                    "project_name": link.get("project_name", ""),
                    "matched_concept_count": 0,
                }
            if pid:
                related_projects[pid]["matched_concept_count"] += 1

    members.sort(key=lambda x: -x["score"])
    candidates.sort(key=lambda x: -x["score"])

    return {
        "theme": {
            "theme_id": theme["theme_id"],
            "name": theme["name"],
            "slug": theme.get("slug", ""),
            "description": theme.get("description", ""),
            "status": theme.get("status", "active"),
            "source": theme.get("source", "user"),
            "keywords": theme.get("keywords", []),
            "member_count": len(members),
            "candidate_count": len(candidates),
            "created_at": theme.get("created_at"),
            "updated_at": theme.get("updated_at"),
        },
        "core_concepts": members,
        "candidate_concepts": candidates,
        "related_projects": sorted(
            related_projects.values(),
            key=lambda x: -x["matched_concept_count"],
        ),
    }


def list_orphans(limit: int = 200) -> list[dict[str, Any]]:
    """Return canonical concepts not assigned to any theme."""
    from . import global_concept_registry as registry
    all_entries = registry.list_entries()

    # Collect all entry_ids that are in any theme
    store = _load_themes()
    assigned_ids: set[str] = set()
    for theme in store["themes"].values():
        for m in theme.get("concept_memberships", []):
            assigned_ids.add(m["entry_id"])

    orphans = []
    for entry in all_entries:
        if entry["entry_id"] not in assigned_ids:
            orphans.append({
                "entry_id": entry["entry_id"],
                "canonical_name": entry.get("canonical_name", ""),
                "concept_type": entry.get("concept_type", "Concept"),
            })
    return orphans[:limit]


# Concept types that frequently surface as pure time/quantity artefacts
# ("100 万行代码", "9000 多次提交", "2020 年夏天正式上线"). GPT flagged
# that recommending these as theme members is noisy; we still return them,
# but demote to ``relevance="low"`` and move them below the high-relevance
# group in the payload so the UI can render them under a collapsed section.
_EVIDENCE_LIKE_TYPES = {"Evidence", "Metric", "Example"}


_DIGIT_PATTERN = re.compile(r"\d")


def _looks_trivially_quantitative(name: str) -> bool:
    """Heuristic for "this is probably just a number/date/duration".

    Matches when the concept name is short **and** contains digits, e.g.
    ``"100 万行代码"`` / ``"9000 多次提交"`` / ``"2020 年夏天"``. Names like
    ``"100 次深度访谈的迭代方法"`` stay because they are longer.
    """
    stripped = (name or "").strip()
    if not stripped:
        return False
    if not _DIGIT_PATTERN.search(stripped):
        return False
    return len(stripped) <= 14


def _classify_suggestion_relevance(entry: dict[str, Any]) -> str:
    """Return ``"high"`` or ``"low"`` for a suggestion candidate.

    ``low`` means "likely trivial evidence/example" per GPT must-fix.
    Callers keep these but visually separate them from the high-relevance
    list so users don't drown in quantitative fragments.
    """
    ctype = str(entry.get("concept_type") or "").strip()
    name = str(entry.get("canonical_name") or "").strip()
    if ctype in _EVIDENCE_LIKE_TYPES and _looks_trivially_quantitative(name):
        return "low"
    return "high"


def suggested_memberships_for_theme(theme_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    """Return canonical concepts that share articles with this theme but
    aren't yet attached.

    Rationale ("主题漏接"): a concept that came from an article already
    represented in the theme is almost certainly relevant. If it slipped
    past the auto pipeline, the user needs to see it before they claim
    the theme is complete. Zero-fallback: no fuzzy similarity, only
    concrete article overlap.

    Each suggestion carries:
    * ``entry_id``, ``canonical_name``, ``concept_type``, ``description``
    * ``shared_articles`` — list of ``{project_id, project_name}`` pairs
    * ``reason`` — short human text explaining why it was suggested
    * ``relevance`` — ``"high" | "low"`` (see :func:`_classify_suggestion_relevance`)
    """
    from . import global_concept_registry as registry
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"主题不存在: {theme_id}")

    attached_ids = {m["entry_id"] for m in theme.get("concept_memberships", [])}

    # Collect the projects the theme already covers.
    all_entries = {e["entry_id"]: e for e in registry.list_entries()}
    theme_projects: dict[str, str] = {}
    for m in theme.get("concept_memberships", []):
        entry = all_entries.get(m["entry_id"])
        if not entry:
            continue
        for link in entry.get("source_links") or []:
            pid = link.get("project_id")
            if pid:
                theme_projects[pid] = link.get("project_name") or pid
    if not theme_projects:
        return []

    suggestions: list[dict[str, Any]] = []
    for entry in all_entries.values():
        if entry["entry_id"] in attached_ids:
            continue
        overlap: list[dict[str, str]] = []
        for link in entry.get("source_links") or []:
            pid = link.get("project_id")
            if pid and pid in theme_projects:
                overlap.append({
                    "project_id": pid,
                    "project_name": theme_projects[pid],
                })
        if not overlap:
            continue
        suggestions.append({
            "entry_id": entry["entry_id"],
            "canonical_name": entry.get("canonical_name", ""),
            "concept_type": entry.get("concept_type", "Concept"),
            "description": (entry.get("description") or "")[:160],
            "shared_articles": overlap,
            "reason": (
                f"与本主题已包含的 {overlap[0]['project_name']} 同属一篇文章，"
                "但尚未纳入主题成员。"
            ),
            "relevance": _classify_suggestion_relevance(entry),
        })

    # Rank: high relevance first, more article overlap first, stable tail on
    # canonical_name for determinism. Low-relevance items still appear but
    # sink to the bottom so the UI can render them under a secondary section.
    relevance_rank = {"high": 0, "low": 1}
    suggestions.sort(
        key=lambda s: (
            relevance_rank.get(s["relevance"], 2),
            -len(s["shared_articles"]),
            s["canonical_name"],
        )
    )
    return suggestions[:limit]


def record_discovery_run(
    theme_id: str,
    *,
    stats: dict[str, Any],
    job_id: str | None = None,
) -> dict[str, Any]:
    """Persist the latest discovery run's coverage stats on the theme.

    Used by ``cross_concept_discoverer.discover`` to make "我们已经找过了吗"
    visible on the panorama endpoint. Stats retained on ``discovery_coverage``:

    * ``candidates_count`` — how many candidate pairs the recall stage produced
    * ``discovered`` — how many new xrels were persisted
    * ``skipped`` — dedupe hits
    * ``errors_count`` — number of errors (bounded)
    * ``last_run_at`` — ISO timestamp

    Additionally, a rolling ``discovery_history`` list (most-recent first,
    capped at :data:`_DISCOVERY_HISTORY_MAX`) is appended per run with a
    bounded subset of fields so Theme UI and future A/B dashboards can
    diff funnel counts across runs without the raw stats blob bloating
    the theme JSON. Each entry mirrors ``discovery_coverage`` plus the
    whole ``funnel`` dict and the ``job_id``.
    """
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"主题不存在: {theme_id}")

    now_iso = datetime.now().isoformat()
    discovered = int(stats.get("discovered", 0) or 0)
    candidates_count = int(stats.get("candidates_count", 0) or 0)
    skipped = int(stats.get("skipped", 0) or 0)
    errors_count = int(len(stats.get("errors", []) or []))
    reason = str(stats.get("reason", "") or "")
    funnel = stats.get("funnel") or {}

    coverage = dict(theme.get("discovery_coverage") or {})
    coverage.update({
        "candidates_count": candidates_count,
        "discovered": discovered,
        "skipped": skipped,
        "errors_count": errors_count,
        "last_run_at": now_iso,
        "reason": reason,
    })
    theme["discovery_coverage"] = coverage

    # Rolling history (added P4 step 2, 2026-04-17). A minimal bounded
    # record per run — NOT the raw stats blob, so model payloads and
    # long error strings stay out of the themes JSON.
    history_entry = {
        "job_id": job_id,
        "run_at": now_iso,
        "discovered": discovered,
        "candidates_count": candidates_count,
        "skipped": skipped,
        "errors_count": errors_count,
        "reason": reason,
        "funnel": dict(funnel) if isinstance(funnel, dict) else {},
    }
    history = list(theme.get("discovery_history") or [])
    history.insert(0, history_entry)  # most-recent first
    if len(history) > _DISCOVERY_HISTORY_MAX:
        history = history[:_DISCOVERY_HISTORY_MAX]
    theme["discovery_history"] = history

    theme["updated_at"] = now_iso
    store["themes"][theme_id] = theme
    _save_themes(store)
    return coverage


def get_discovery_history(theme_id: str) -> list[dict[str, Any]]:
    """Return the theme's rolling discover history (most-recent first).

    Raises :class:`GlobalThemeNotFoundError` for an unknown theme.
    Returns ``[]`` for a theme that has never been discover-run.
    """
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"主题不存在: {theme_id}")
    return list(theme.get("discovery_history") or [])


# ---------------------------------------------------------------------------
# Legacy compat: project cluster link/unlink (kept for old callers)
# ---------------------------------------------------------------------------


def link_project_cluster(
    theme_id: str, *, project_id: str, cluster_id: str, cluster_name: str = "",
) -> dict[str, Any]:
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"全局主题不存在: {theme_id}")
    for link in theme.get("source_project_clusters", []):
        if link["project_id"] == project_id and link["cluster_id"] == cluster_id:
            return theme
    theme.setdefault("source_project_clusters", []).append({
        "project_id": project_id, "cluster_id": cluster_id,
        "cluster_name": cluster_name, "linked_at": datetime.now().isoformat(),
    })
    theme["updated_at"] = datetime.now().isoformat()
    _save_themes(store)
    from .evolution_log import emit_event
    emit_event(
        event_type="cluster_linked",
        entity_type="global_theme",
        entity_id=theme_id,
        entity_name=theme.get("name", ""),
        project_id=project_id,
        details={"cluster_id": cluster_id, "cluster_name": cluster_name},
    )
    theme["concept_entry_ids"] = _compat_entry_ids(theme)
    return theme


def unlink_project_cluster(
    theme_id: str, *, project_id: str, cluster_id: str,
) -> dict[str, Any]:
    store = _load_themes()
    theme = store["themes"].get(theme_id)
    if not theme:
        raise GlobalThemeNotFoundError(f"全局主题不存在: {theme_id}")
    before_links = list(theme.get("source_project_clusters", []))
    theme["source_project_clusters"] = [
        l for l in before_links
        if not (l["project_id"] == project_id and l["cluster_id"] == cluster_id)
    ]
    if len(theme["source_project_clusters"]) == len(before_links):
        theme["concept_entry_ids"] = _compat_entry_ids(theme)
        return theme
    theme["updated_at"] = datetime.now().isoformat()
    _save_themes(store)
    from .evolution_log import emit_event
    emit_event(
        event_type="cluster_unlinked",
        entity_type="global_theme",
        entity_id=theme_id,
        entity_name=theme.get("name", ""),
        project_id=project_id,
        details={"cluster_id": cluster_id},
    )
    theme["concept_entry_ids"] = _compat_entry_ids(theme)
    return theme


def suggest_from_project(project_id: str) -> dict[str, Any]:
    from ...models.project import ProjectManager
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        raise GlobalThemeNotFoundError(f"项目不存在: {project_id}")
    clusters = list(project.theme_clusters or [])
    store = _load_themes()
    linked_set: set[tuple[str, str]] = set()
    name_to_theme: dict[str, dict] = {}
    for theme in store["themes"].values():
        name_to_theme[theme["name"].lower()] = theme
        for link in theme.get("source_project_clusters", []):
            linked_set.add((link["project_id"], link["cluster_id"]))
    new_candidates, existing_matches, already_linked = [], [], []
    for cluster in clusters:
        cid = cluster.get("id", "")
        cname = cluster.get("name", "")
        if not cid:
            continue
        if (project_id, cid) in linked_set:
            already_linked.append({"cluster_id": cid, "cluster_name": cname})
        elif (match := name_to_theme.get(cname.lower())):
            existing_matches.append({
                "cluster_id": cid, "cluster_name": cname,
                "matched_theme_id": match["theme_id"], "matched_theme_name": match["name"],
            })
        else:
            new_candidates.append({
                "cluster_id": cid, "cluster_name": cname,
                "concept_count": len(cluster.get("concept_ids", [])),
            })
    return {
        "project_id": project_id, "project_name": project.name,
        "total_clusters": len(clusters),
        "new_candidates": new_candidates, "existing_matches": existing_matches,
        "already_linked": already_linked,
    }
