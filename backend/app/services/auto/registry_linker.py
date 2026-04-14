"""Auto-link / auto-register canonical concepts based on suggest-from-project.

Reads ``suggest_from_project()`` output and processes its 4 buckets:

- ``existing_matches``  → auto link (idempotent)
- ``new_candidates``    → auto create+link, using the inverse type rule
                          (anything not in ``_NEVER_AUTO_REGISTER_TYPES``,
                          formerly only ``{Topic, Technology}``). Still
                          requires ``connectedCount >= 2`` in the
                          project's concept view as the structural signal.
- ``cross_type_matches`` → record an audit event, do NOT auto-link
                           (cross-type drift is a real signal but the
                           direction must be a human decision)
- ``already_linked``    → skip

The type rule was inverted on 2026-04-11 evening after a real Harness
article produced Architecture, Problem, Mechanism, Metric, etc. — types
the LLM ontology generator emits freely, none of which matched the old
``{Topic, Technology}`` whitelist, so 0 of 45 candidates got registered.
The inverse rule follows ``AutoConceptDecider``: accept any type that is
not in the ``never`` set, gated by ``connectedCount``.

Idempotency:
- Before ``create_entry`` we check whether a canonical with the same
  ``(canonical_name, concept_type)`` already exists. If yes, we re-use it.
- Before ``link_project_concept`` we check whether the
  ``(project_id, concept_key)`` source link already exists. If yes, we
  short-circuit to a "no-op already linked" path.

All actions emit fine-grained ``evolution_log`` events with
``actor_type="auto"``, ``actor_id="auto_pipeline"``, ``run_id`` set,
and ``source="auto_url_pipeline"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..registry import global_concept_registry as registry
from ..registry.evolution_log import emit_event
from ..workspace.concept_normalization import normalize_concept_name


# Concept types that are NEVER auto-created as canonicals, even if
# strongly connected. Parallels ``AutoConceptDecider._NEVER_ACCEPT``.
_NEVER_AUTO_REGISTER_TYPES: frozenset[str] = frozenset({"Insight"})

# Minimum connectedCount in the project view for auto-register
_MIN_CONNECTED_FOR_REGISTER: int = 2


@dataclass
class AutoLinkSummary:
    """Counters describing what the linker did this run."""

    linked_existing: int = 0
    created_and_linked: int = 0
    cross_type_flagged: int = 0
    skipped_already_linked: int = 0
    skipped_new_candidate_type: int = 0
    skipped_new_candidate_low_signal: int = 0
    errors: list[str] = field(default_factory=list)
    new_canonical_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "linked_existing": self.linked_existing,
            "created_and_linked": self.created_and_linked,
            "cross_type_flagged": self.cross_type_flagged,
            "skipped_already_linked": self.skipped_already_linked,
            "skipped_new_candidate_type": self.skipped_new_candidate_type,
            "skipped_new_candidate_low_signal": self.skipped_new_candidate_low_signal,
            "errors": list(self.errors),
            "new_canonical_ids": list(self.new_canonical_ids),
        }


class AutoRegistryLinker:
    """Process suggest-from-project response with idempotency + audit."""

    def __init__(
        self,
        *,
        never_register_types: Iterable[str] | None = None,
        min_connected_for_register: int = _MIN_CONNECTED_FOR_REGISTER,
        actor_id: str = "auto_pipeline",
        source: str = "auto_url_pipeline",
        # Kept for backward compatibility with callers/tests that
        # explicitly pass a positive whitelist. When set, ONLY these
        # types are auto-registered (the old behavior). When None, the
        # inverse rule applies: any type not in ``never_register_types``.
        register_types: Iterable[str] | None = None,
    ) -> None:
        self.never_register_types = (
            frozenset(never_register_types)
            if never_register_types
            else _NEVER_AUTO_REGISTER_TYPES
        )
        self.register_types: frozenset[str] | None = (
            frozenset(register_types) if register_types else None
        )
        self.min_connected_for_register = min_connected_for_register
        self.actor_id = actor_id
        self.source = source

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def process(
        self,
        *,
        project_id: str,
        project_name: str,
        suggest_payload: dict,
        candidate_signal: dict[str, dict],
        run_id: str,
    ) -> AutoLinkSummary:
        """Run the linker over a complete suggest-from-project response.

        Args:
            project_id: Project being processed.
            project_name: Human-readable project name (for source_links).
            suggest_payload: ``suggest_from_project()`` return value.
            candidate_signal: ``{concept_key: candidate_dict}`` from the
                concept view, used to look up ``connectedCount`` for the
                new_candidates auto-register gate.
            run_id: per-URL run identifier from the auto pipeline.
        """
        summary = AutoLinkSummary()

        for match in suggest_payload.get("existing_matches") or []:
            self._handle_existing_match(
                project_id=project_id,
                project_name=project_name,
                match=match,
                run_id=run_id,
                summary=summary,
            )

        for candidate in suggest_payload.get("new_candidates") or []:
            self._handle_new_candidate(
                project_id=project_id,
                project_name=project_name,
                candidate=candidate,
                signal=candidate_signal.get(candidate.get("concept_key", "")),
                run_id=run_id,
                summary=summary,
            )

        for cross in suggest_payload.get("cross_type_matches") or []:
            self._handle_cross_type(
                project_id=project_id,
                cross=cross,
                run_id=run_id,
                summary=summary,
            )

        for already in suggest_payload.get("already_linked") or []:
            summary.skipped_already_linked += 1

        return summary

    # ------------------------------------------------------------------
    # Per-bucket handlers
    # ------------------------------------------------------------------

    def _handle_existing_match(
        self,
        *,
        project_id: str,
        project_name: str,
        match: dict,
        run_id: str,
        summary: AutoLinkSummary,
    ) -> None:
        entry_id = match.get("matched_entry_id")
        concept_key = match.get("concept_key")
        if not entry_id or not concept_key:
            summary.errors.append(f"existing_match missing fields: {match}")
            return

        if self._is_already_linked(entry_id, project_id, concept_key):
            summary.skipped_already_linked += 1
            return

        try:
            registry.link_project_concept(
                entry_id,
                project_id=project_id,
                concept_key=concept_key,
                project_name=project_name,
            )
        except Exception as error:  # noqa: BLE001
            summary.errors.append(f"link {entry_id}/{concept_key}: {error}")
            return

        summary.linked_existing += 1
        emit_event(
            event_type="canonical_auto_linked",
            entity_type="concept_entry",
            entity_id=entry_id,
            entity_name=match.get("matched_canonical_name", ""),
            project_id=project_id,
            details={
                "concept_key": concept_key,
                "via": "existing_match",
                "display_name": match.get("display_name", ""),
                "concept_type": match.get("concept_type", ""),
            },
            actor_type="auto",
            actor_id=self.actor_id,
            run_id=run_id,
            source=self.source,
        )

    def _handle_new_candidate(
        self,
        *,
        project_id: str,
        project_name: str,
        candidate: dict,
        signal: dict | None,
        run_id: str,
        summary: AutoLinkSummary,
    ) -> None:
        concept_type = (candidate.get("concept_type") or "").strip()
        # Inverse type gate: reject if explicitly in the never-set, OR
        # (for back-compat) if a positive whitelist is configured and
        # this type is outside it.
        if concept_type in self.never_register_types:
            summary.skipped_new_candidate_type += 1
            return
        if (
            self.register_types is not None
            and concept_type not in self.register_types
        ):
            summary.skipped_new_candidate_type += 1
            return

        connected = int((signal or {}).get("connectedCount") or 0)
        if connected < self.min_connected_for_register:
            summary.skipped_new_candidate_low_signal += 1
            return

        canonical_name = (
            candidate.get("display_name") or candidate.get("concept_key") or ""
        ).strip()
        if not canonical_name:
            summary.errors.append(f"new_candidate missing display_name: {candidate}")
            return

        # Idempotency: re-use an existing entry that matches name+type
        entry = self._find_existing_entry(canonical_name, concept_type)
        created_now = False
        if entry is None:
            try:
                entry = registry.create_entry(
                    canonical_name=canonical_name,
                    concept_type=concept_type,
                )
                created_now = True
            except Exception as error:  # noqa: BLE001
                summary.errors.append(f"create {canonical_name}: {error}")
                return

        entry_id = entry.get("entry_id") if isinstance(entry, dict) else None
        if not entry_id:
            summary.errors.append(f"created entry missing id: {entry}")
            return

        if created_now:
            emit_event(
                event_type="canonical_auto_created",
                entity_type="concept_entry",
                entity_id=entry_id,
                entity_name=canonical_name,
                project_id=project_id,
                details={
                    "concept_type": concept_type,
                    "from_concept_key": candidate.get("concept_key", ""),
                },
                actor_type="auto",
                actor_id=self.actor_id,
                run_id=run_id,
                source=self.source,
            )
            summary.new_canonical_ids.append(entry_id)

        # Now link, with the same idempotency check
        concept_key = candidate.get("concept_key", "")
        if not self._is_already_linked(entry_id, project_id, concept_key):
            try:
                registry.link_project_concept(
                    entry_id,
                    project_id=project_id,
                    concept_key=concept_key,
                    project_name=project_name,
                )
                summary.created_and_linked += 1
                emit_event(
                    event_type="canonical_auto_linked",
                    entity_type="concept_entry",
                    entity_id=entry_id,
                    entity_name=canonical_name,
                    project_id=project_id,
                    details={
                        "concept_key": concept_key,
                        "via": "new_candidate",
                        "concept_type": concept_type,
                    },
                    actor_type="auto",
                    actor_id=self.actor_id,
                    run_id=run_id,
                    source=self.source,
                )
            except Exception as error:  # noqa: BLE001
                summary.errors.append(f"link new {entry_id}/{concept_key}: {error}")
        else:
            summary.skipped_already_linked += 1

    def _handle_cross_type(
        self,
        *,
        project_id: str,
        cross: dict,
        run_id: str,
        summary: AutoLinkSummary,
    ) -> None:
        # Cross-type matches are NEVER auto-linked. Just record the audit event.
        summary.cross_type_flagged += 1
        emit_event(
            event_type="cross_type_match_flagged",
            entity_type="concept_entry",
            entity_id=cross.get("matched_entry_id", ""),
            entity_name=cross.get("matched_canonical_name", ""),
            project_id=project_id,
            details={
                "concept_key": cross.get("concept_key", ""),
                "display_name": cross.get("display_name", ""),
                "from_type": cross.get("concept_type", ""),
                "to_type": cross.get("matched_concept_type", ""),
                "note": "auto pipeline detected cross-type alias signal; user must decide",
            },
            actor_type="auto",
            actor_id=self.actor_id,
            run_id=run_id,
            source=self.source,
        )

    # ------------------------------------------------------------------
    # Idempotency helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_already_linked(entry_id: str, project_id: str, concept_key: str) -> bool:
        try:
            entry = registry.get_entry(entry_id)
        except Exception:
            return False
        for link in entry.get("source_links") or []:
            if (
                link.get("project_id") == project_id
                and link.get("concept_key") == concept_key
            ):
                return True
        return False

    @staticmethod
    def _find_existing_entry(canonical_name: str, concept_type: str) -> dict | None:
        norm = normalize_concept_name(canonical_name)
        for entry in registry.list_entries(concept_type=concept_type):
            if normalize_concept_name(entry.get("canonical_name", "")) == norm:
                return entry
        return None
