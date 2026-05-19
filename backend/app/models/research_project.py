"""Strategic research project storage.

ResearchProject is intentionally separate from the existing article/graph
Project model. It stores a human-initiated strategic research asset container
and must not trigger article graph build or legacy Phase 1 backfill behavior.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional


_DEFAULT_ROOT_DIR = Path(__file__).resolve().parents[2] / "data" / "research_projects"
_ID_PATTERN = re.compile(r"^rp_[0-9a-f]{12}$")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _new_project_id() -> str:
    return f"rp_{secrets.token_hex(6)}"


def _new_prefixed_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(raw.encode('utf-8')).hexdigest()}"


class ResearchProjectStatus(str, Enum):
    """Minimal P1 lifecycle states for a strategic research container."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class ResearchProject:
    """Strategic research asset container."""

    id: str
    title: str
    background: str = ""
    audience: str = ""
    goal: str = ""
    status: ResearchProjectStatus = ResearchProjectStatus.DRAFT
    research_brief: dict[str, Any] = field(
        default_factory=lambda: {
            "problem_statement": "",
            "scope": "",
            "key_questions": [],
        }
    )
    issue_tree: list[Any] = field(default_factory=list)
    linked_topic_clusters: list[Any] = field(default_factory=list)
    linked_themes: list[Any] = field(default_factory=list)
    linked_concepts: list[Any] = field(default_factory=list)
    evidence_items: list[Any] = field(default_factory=list)
    evidence_matrix_rows: list[Any] = field(default_factory=list)
    insight_cards: list[Any] = field(default_factory=list)
    artifact_drafts: list[Any] = field(default_factory=list)
    artifact_packs: list[Any] = field(default_factory=list)
    strategic_options: list[Any] = field(default_factory=list)
    validation_plans: list[Any] = field(default_factory=list)
    leadership_decision_records: list[Any] = field(default_factory=list)
    leadership_briefings: list[Any] = field(default_factory=list)
    governance_reviews: list[Any] = field(default_factory=list)
    review_history_entries: list[Any] = field(default_factory=list)
    research_snapshots: list[Any] = field(default_factory=list)
    snapshot_review_notes: list[Any] = field(default_factory=list)
    review_log: list[Any] = field(default_factory=list)
    local_evidence_pack: Optional[dict[str, Any]] = None
    research_runs: list[Any] = field(default_factory=list)
    consultation_logs: list[Any] = field(default_factory=list)
    external_research_packs: list[Any] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "background": self.background,
            "audience": self.audience,
            "goal": self.goal,
            "status": self.status.value if isinstance(self.status, ResearchProjectStatus) else self.status,
            "research_brief": self.research_brief,
            "issue_tree": self.issue_tree,
            "linked_topic_clusters": self.linked_topic_clusters,
            "linked_themes": self.linked_themes,
            "linked_concepts": self.linked_concepts,
            "evidence_items": self.evidence_items,
            "evidence_matrix_rows": self.evidence_matrix_rows,
            "insight_cards": self.insight_cards,
            "artifact_drafts": self.artifact_drafts,
            "artifact_packs": self.artifact_packs,
            "strategic_options": self.strategic_options,
            "validation_plans": self.validation_plans,
            "leadership_decision_records": self.leadership_decision_records,
            "leadership_briefings": self.leadership_briefings,
            "governance_reviews": self.governance_reviews,
            "review_history_entries": self.review_history_entries,
            "research_snapshots": self.research_snapshots,
            "snapshot_review_notes": self.snapshot_review_notes,
            "review_log": self.review_log,
            "local_evidence_pack": self.local_evidence_pack,
            "research_runs": self.research_runs,
            "consultation_logs": self.consultation_logs,
            "external_research_packs": self.external_research_packs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchProject":
        status = data.get("status", ResearchProjectStatus.DRAFT.value)
        if isinstance(status, str):
            status = ResearchProjectStatus(status)
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            background=data.get("background", ""),
            audience=data.get("audience", ""),
            goal=data.get("goal", ""),
            status=status,
            research_brief=data.get("research_brief") or {
                "problem_statement": "",
                "scope": "",
                "key_questions": [],
            },
            issue_tree=data.get("issue_tree") or [],
            linked_topic_clusters=data.get("linked_topic_clusters") or [],
            linked_themes=data.get("linked_themes") or [],
            linked_concepts=data.get("linked_concepts") or [],
            evidence_items=data.get("evidence_items") or [],
            evidence_matrix_rows=data.get("evidence_matrix_rows") or [],
            insight_cards=data.get("insight_cards") or [],
            artifact_drafts=data.get("artifact_drafts") or [],
            artifact_packs=data.get("artifact_packs") or [],
            strategic_options=data.get("strategic_options") or [],
            validation_plans=data.get("validation_plans") or [],
            leadership_decision_records=data.get("leadership_decision_records") or [],
            leadership_briefings=data.get("leadership_briefings") or [],
            governance_reviews=data.get("governance_reviews") or [],
            review_history_entries=data.get("review_history_entries") or [],
            research_snapshots=data.get("research_snapshots") or [],
            snapshot_review_notes=data.get("snapshot_review_notes") or [],
            review_log=data.get("review_log") or [],
            local_evidence_pack=data.get("local_evidence_pack"),
            research_runs=data.get("research_runs") or [],
            consultation_logs=data.get("consultation_logs") or [],
            external_research_packs=data.get("external_research_packs") or [],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class ResearchProjectStoreError(RuntimeError):
    """Raised when ResearchProject persistence fails."""


class ResearchProjectStore:
    """JSON-file store for strategic ResearchProject records."""

    ROOT_DIR: Path = _DEFAULT_ROOT_DIR
    SUPPORTED_SNAPSHOT_ASSET_KINDS = {
        "project",
        "evidence_items",
        "evidence_matrix_rows",
        "insight_cards",
        "artifact_drafts",
        "artifact_packs",
        "strategic_options",
        "validation_plans",
        "leadership_decision_records",
        "leadership_briefings",
        "governance_reviews",
        "review_history",
    }
    SNAPSHOT_ID_FIELDS = {
        "evidence_items": "evidence_id",
        "evidence_matrix_rows": "id",
        "insight_cards": "id",
        "artifact_drafts": "id",
        "artifact_packs": "pack_id",
        "strategic_options": "option_id",
        "validation_plans": "plan_id",
        "leadership_decision_records": "decision_id",
        "leadership_briefings": "briefing_id",
        "governance_reviews": "review_id",
        "review_history": "history_entry_id",
    }
    SNAPSHOT_ASSET_TYPES = {
        "evidence_items": "evidence_item",
        "evidence_matrix_rows": "evidence_matrix_row",
        "insight_cards": "insight_card",
        "artifact_drafts": "artifact_draft",
        "artifact_packs": "artifact_pack",
        "strategic_options": "strategic_option",
        "validation_plans": "validation_plan",
        "leadership_decision_records": "leadership_decision_record",
        "leadership_briefings": "leadership_briefing",
        "governance_reviews": "governance_review",
        "review_history": "review_history_entry",
    }
    SNAPSHOT_REVIEW_NOTE_SECTION_KEYS = {
        "governance_gate",
        "leadership_briefing_readiness",
        "review_history_activity",
        "asset_kind_counts",
        "raw_diff",
        "other",
    }
    SNAPSHOT_REVIEW_NOTE_TYPES = {
        "observation",
        "question",
        "accepted_change",
        "needs_follow_up",
    }
    SNAPSHOT_REVIEW_NOTE_SEVERITIES = {
        "info",
        "watch",
        "blocker",
    }
    SNAPSHOT_REVIEW_NOTE_STATUSES = {
        "open",
        "acknowledged",
        "resolved",
        "deferred",
    }
    SNAPSHOT_REVIEW_NOTE_UPDATE_FIELDS = {
        "status",
        "owner",
        "resolution_note",
        "actor",
    }
    SNAPSHOT_REVIEW_NOTE_RUNTIME_FIELDS = {
        "model",
        "model_provider",
        "provider",
        "prompt",
        "tool_call",
        "workflow",
        "workflow_id",
        "auto_decision",
        "generated_analysis",
        "repair",
        "repair_action",
        "rollback",
        "rollback_target",
        "approval",
        "gate_verdict",
    }

    def __init__(self, root_dir: Optional[str | Path] = None) -> None:
        self.root_dir = Path(root_dir or self.ROOT_DIR).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _project_path(self, project_id: str) -> Path:
        if not _ID_PATTERN.match(project_id):
            raise ResearchProjectStoreError(f"invalid research project id: {project_id}")
        return self.root_dir / f"{project_id}.json"

    def _project_asset_dir(self, project_id: str, asset_kind: str) -> Path:
        if not _ID_PATTERN.match(project_id):
            raise ResearchProjectStoreError(f"invalid research project id: {project_id}")
        if not re.match(r"^[a-z_]+$", asset_kind):
            raise ResearchProjectStoreError(f"invalid research asset kind: {asset_kind}")
        return self.root_dir / project_id / asset_kind

    def _asset_path(self, project_id: str, asset_kind: str, asset_id: str) -> Path:
        if not re.match(r"^[a-z]+_[0-9a-f]{12}$", asset_id):
            raise ResearchProjectStoreError(f"invalid research asset id: {asset_id}")
        return self._project_asset_dir(project_id, asset_kind) / f"{asset_id}.json"

    def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def _read_asset(self, project_id: str, asset_kind: str, asset_id: str) -> Optional[dict[str, Any]]:
        try:
            path = self._asset_path(project_id, asset_kind, asset_id)
        except ResearchProjectStoreError:
            return None
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ResearchProjectStoreError(f"research asset JSON is corrupted: {path}") from exc

    def _list_assets(self, project_id: str, asset_kind: str, id_prefix: str) -> list[dict[str, Any]]:
        path = self._project_asset_dir(project_id, asset_kind)
        if not path.exists():
            return []
        assets: list[dict[str, Any]] = []
        for item in path.glob(f"{id_prefix}_*.json"):
            try:
                assets.append(json.loads(item.read_text(encoding="utf-8")))
            except json.JSONDecodeError as exc:
                raise ResearchProjectStoreError(f"invalid research asset JSON: {item}") from exc
        assets.sort(key=lambda asset: asset.get("updated_at") or asset.get("created_at") or "", reverse=True)
        return assets

    def _find_by_idempotency(
        self,
        project_id: str,
        asset_kind: str,
        id_prefix: str,
        idempotency_key: str,
    ) -> Optional[dict[str, Any]]:
        if not idempotency_key:
            return None
        for asset in self._list_assets(project_id, asset_kind, id_prefix):
            if asset.get("idempotency_key") == idempotency_key:
                return asset
        return None

    def _write_index_item(
        self,
        project: ResearchProject,
        field: str,
        id_field: str,
        index_item: dict[str, Any],
    ) -> None:
        existing = [
            item for item in list(getattr(project, field) or [])
            if item.get(id_field) != index_item.get(id_field)
        ]
        existing.append(index_item)
        existing.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
        setattr(project, field, existing)

    def create(self, payload: dict[str, Any]) -> ResearchProject:
        now = _now_iso()
        project = ResearchProject(
            id=_new_project_id(),
            title=str(payload["title"]).strip(),
            background=str(payload.get("background") or ""),
            audience=str(payload.get("audience") or ""),
            goal=str(payload.get("goal") or ""),
            status=ResearchProjectStatus(payload.get("status") or ResearchProjectStatus.DRAFT.value),
            research_brief=dict(payload.get("research_brief") or {
                "problem_statement": "",
                "scope": "",
                "key_questions": [],
            }),
            issue_tree=list(payload.get("issue_tree") or []),
            linked_topic_clusters=list(payload.get("linked_topic_clusters") or []),
            linked_themes=list(payload.get("linked_themes") or []),
            linked_concepts=list(payload.get("linked_concepts") or []),
            evidence_items=list(payload.get("evidence_items") or []),
            evidence_matrix_rows=list(payload.get("evidence_matrix_rows") or []),
            insight_cards=list(payload.get("insight_cards") or []),
            artifact_drafts=list(payload.get("artifact_drafts") or []),
            artifact_packs=list(payload.get("artifact_packs") or []),
            strategic_options=list(payload.get("strategic_options") or []),
            validation_plans=list(payload.get("validation_plans") or []),
            leadership_decision_records=list(payload.get("leadership_decision_records") or []),
            leadership_briefings=list(payload.get("leadership_briefings") or []),
            governance_reviews=list(payload.get("governance_reviews") or []),
            review_history_entries=list(payload.get("review_history_entries") or []),
            research_snapshots=list(payload.get("research_snapshots") or []),
            snapshot_review_notes=list(payload.get("snapshot_review_notes") or []),
            review_log=list(payload.get("review_log") or []),
            created_at=now,
            updated_at=now,
        )
        self.save(project)
        return project

    def save(self, project: ResearchProject) -> None:
        path = self._project_path(project.id)
        self._atomic_write(path, project.to_dict())

    def get(self, project_id: str) -> Optional[ResearchProject]:
        try:
            path = self._project_path(project_id)
        except ResearchProjectStoreError:
            return None
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ResearchProjectStoreError(f"research project JSON is corrupted: {path}") from exc
        return ResearchProject.from_dict(data)

    def list(self) -> list[ResearchProject]:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        projects: list[ResearchProject] = []
        for path in self.root_dir.glob("rp_*.json"):
            try:
                project = ResearchProject.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                raise ResearchProjectStoreError(f"invalid research project JSON: {path}") from exc
            projects.append(project)
        projects.sort(key=lambda item: item.updated_at or item.created_at, reverse=True)
        return projects

    def update(self, project_id: str, updates: dict[str, Any]) -> Optional[ResearchProject]:
        project = self.get(project_id)
        if project is None:
            return None

        for key, value in updates.items():
            if key == "status":
                setattr(project, key, ResearchProjectStatus(value))
            elif hasattr(project, key):
                setattr(project, key, value)
        project.updated_at = _now_iso()
        self.save(project)
        return project

    def get_local_evidence_pack(self, project_id: str) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        return project.local_evidence_pack

    def save_local_evidence_pack(
        self,
        project_id: str,
        pack: dict[str, Any],
    ) -> Optional[ResearchProject]:
        project = self.get(project_id)
        if project is None:
            return None
        project.local_evidence_pack = pack
        project.updated_at = _now_iso()
        self.save(project)
        return project

    def update_local_evidence_candidate_status(
        self,
        project_id: str,
        evidence_id: str,
        *,
        status: str,
        note: str = "",
    ) -> Optional[ResearchProject]:
        if status not in {"candidate", "accepted", "rejected"}:
            raise ValueError("status must be candidate, accepted, or rejected")
        project = self.get(project_id)
        if project is None:
            return None
        pack = project.local_evidence_pack
        if not isinstance(pack, dict):
            raise ResearchProjectStoreError("local evidence pack is missing")

        candidates = pack.get("candidates") or []
        target = None
        for candidate in candidates:
            if candidate.get("evidence_id") == evidence_id:
                target = candidate
                break
        if target is None:
            raise ResearchProjectStoreError(f"local evidence candidate not found: {evidence_id}")

        now = _now_iso()
        target["status"] = status
        target["review_note"] = note
        target["reviewed_at"] = now

        accepted_ids = set(pack.get("accepted_evidence_ids") or [])
        rejected_ids = set(pack.get("rejected_evidence_ids") or [])
        accepted_ids.discard(evidence_id)
        rejected_ids.discard(evidence_id)
        if status == "accepted":
            accepted_ids.add(evidence_id)
            self._upsert_evidence_item(project, pack, target, accepted_at=now)
        elif status == "rejected":
            rejected_ids.add(evidence_id)
            project.evidence_items = [
                item for item in project.evidence_items
                if item.get("evidence_id") != evidence_id
            ]
        else:
            project.evidence_items = [
                item for item in project.evidence_items
                if item.get("evidence_id") != evidence_id
            ]

        pack["accepted_evidence_ids"] = sorted(accepted_ids)
        pack["rejected_evidence_ids"] = sorted(rejected_ids)
        pack["updated_at"] = now
        pack["summary"] = self._build_pack_summary(pack)
        project.local_evidence_pack = pack
        project.updated_at = now
        self.save(project)
        return project

    def _upsert_evidence_item(
        self,
        project: ResearchProject,
        pack: dict[str, Any],
        candidate: dict[str, Any],
        *,
        accepted_at: str,
    ) -> None:
        evidence_id = candidate.get("evidence_id")
        source = candidate.get("source") or {}
        source_ref = next(
            (ref for ref in (candidate.get("source_refs") or []) if not ref.get("degraded")),
            (candidate.get("source_refs") or [{}])[0] if candidate.get("source_refs") else {},
        )
        item = {
            "evidence_id": evidence_id,
            "project_id": project.id,
            "title": candidate.get("title", ""),
            "evidence_type": candidate.get("evidence_type", ""),
            "status": "accepted",
            "pack_id": pack.get("pack_id", ""),
            "source_registry": (candidate.get("source") or {}).get("registry", ""),
            "source_concept_id": candidate.get("source_concept_id") or source.get("source_concept_id") or source.get("entry_id", ""),
            "source_article_id": candidate.get("source_article_id") or source_ref.get("source_article_id", ""),
            "source_article_title": candidate.get("source_article_title") or source_ref.get("source_article_title", ""),
            "source_material_slice_id": candidate.get("source_material_slice_id") or source_ref.get("source_material_slice_id", ""),
            "source_lead_id": candidate.get("source_lead_id") or source_ref.get("source_lead_id", ""),
            "source_markdown_path": candidate.get("source_markdown_path") or source_ref.get("source_markdown_path", ""),
            "source_content_hash": candidate.get("source_content_hash") or source_ref.get("source_content_hash", ""),
            "source_quote": candidate.get("source_quote") or source_ref.get("source_text", ""),
            "source_excerpt": candidate.get("source_excerpt") or source_ref.get("source_excerpt", ""),
            "source_context": candidate.get("source_context") or source_ref.get("source_context", ""),
            "claim": candidate.get("summary", ""),
            "created_from": "local_evidence_pack",
            "created_by": "human",
            "degraded": any(ref.get("degraded") for ref in candidate.get("source_refs") or []),
            "accepted_at": accepted_at,
            "provenance": {
                "source": "local_evidence_pack",
                "pack_id": pack.get("pack_id", ""),
                "source_concept_id": candidate.get("source_concept_id") or source.get("source_concept_id") or source.get("entry_id", ""),
                "source_article_id": candidate.get("source_article_id") or source_ref.get("source_article_id", ""),
                "source_material_slice_id": candidate.get("source_material_slice_id") or source_ref.get("source_material_slice_id", ""),
                "source_lead_id": candidate.get("source_lead_id") or source_ref.get("source_lead_id", ""),
                "source_content_hash": candidate.get("source_content_hash") or source_ref.get("source_content_hash", ""),
                "retrieval_version": pack.get("retrieval_version", ""),
            },
        }
        existing = [
            old for old in project.evidence_items
            if old.get("evidence_id") != evidence_id
        ]
        existing.append(item)
        project.evidence_items = existing

    def create_research_run(self, project_id: str, payload: dict[str, Any]) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        return self._create_asset(
            project,
            asset_kind="research_runs",
            id_prefix="rr",
            id_field="run_id",
            index_field="research_runs",
            payload=payload,
            index_builder=lambda item: {
                "run_id": item["run_id"],
                "stage": item.get("stage", ""),
                "phase": item.get("phase", ""),
                "title": item.get("title", ""),
                "status": item.get("status", ""),
                "summary": item.get("summary", ""),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
            },
        )

    def list_research_runs(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "research_runs", "rr")

    def get_research_run(self, project_id: str, run_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "research_runs", run_id)

    def create_consultation_log(self, project_id: str, payload: dict[str, Any]) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        return self._create_asset(
            project,
            asset_kind="consultation_logs",
            id_prefix="cl",
            id_field="consultation_id",
            index_field="consultation_logs",
            payload=payload,
            index_builder=lambda item: {
                "consultation_id": item["consultation_id"],
                "kind": item.get("kind", ""),
                "stage": item.get("stage", ""),
                "status": item.get("status", ""),
                "answer_summary": item.get("answer_summary", ""),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
            },
        )

    def list_consultation_logs(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "consultation_logs", "cl")

    def get_consultation_log(self, project_id: str, consultation_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "consultation_logs", consultation_id)

    def import_external_research_pack(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        payload = dict(payload)
        payload.setdefault("scope", "C2_external")
        candidates = []
        for raw in payload.get("evidence_candidates") or []:
            candidate = dict(raw)
            candidate.setdefault("candidate_id", self._candidate_id(candidate))
            candidate.setdefault("review_status", "pending")
            candidates.append(candidate)
        payload["evidence_candidates"] = candidates
        return self._create_asset(
            project,
            asset_kind="external_research_packs",
            id_prefix="erp",
            id_field="pack_id",
            index_field="external_research_packs",
            payload=payload,
            index_builder=self._external_pack_index,
        )

    def list_external_research_packs(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "external_research_packs", "erp")

    def get_external_research_pack(self, project_id: str, pack_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "external_research_packs", pack_id)

    def create_evidence_matrix_row(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("claim_type", "strategic_claim")
        clean.setdefault("supporting_evidence_ids", [])
        clean.setdefault("counter_evidence_ids", [])
        clean.setdefault("related_insight_ids", [])
        clean.setdefault("confidence", "medium")
        clean.setdefault("material_readiness", "raw")
        clean.setdefault("status", "draft")
        self._validate_choice(clean["claim_type"], "claim_type", {
            "strategic_claim",
            "risk",
            "assumption",
            "option",
            "decision_point",
        })
        self._validate_choice(clean["confidence"], "confidence", {"low", "medium", "high"})
        self._validate_choice(clean["material_readiness"], "material_readiness", {
            "raw",
            "usable",
            "presentation_ready",
            "insufficient",
        })
        self._validate_choice(clean["status"], "status", {
            "draft",
            "reviewed",
            "accepted",
            "rejected",
            "superseded",
        })
        self._require_text(clean, "question", "claim")
        clean["traceability_warnings"] = self._validate_evidence_refs(
            project,
            clean.get("supporting_evidence_ids") or [],
            clean.get("counter_evidence_ids") or [],
        )
        self._validate_insight_refs(project.id, clean.get("related_insight_ids") or [])
        return self._create_asset(
            project,
            asset_kind="evidence_matrix_rows",
            id_prefix="emr",
            id_field="id",
            index_field="evidence_matrix_rows",
            payload=clean,
            index_builder=self._evidence_matrix_row_index,
        )

    def list_evidence_matrix_rows(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "evidence_matrix_rows", "emr")

    def get_evidence_matrix_row(self, project_id: str, row_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "evidence_matrix_rows", row_id)

    def update_evidence_matrix_row(
        self,
        project_id: str,
        row_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "question",
            "claim",
            "claim_type",
            "supporting_evidence_ids",
            "counter_evidence_ids",
            "related_insight_ids",
            "confidence",
            "material_readiness",
            "status",
            "notes",
            "updated_by",
        }
        return self._update_synthesis_asset(
            project_id,
            asset_kind="evidence_matrix_rows",
            asset_id=row_id,
            index_field="evidence_matrix_rows",
            allowed=allowed,
            updates=updates,
            validator=self._validate_evidence_matrix_row,
            index_builder=self._evidence_matrix_row_index,
        )

    def create_insight_card(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("supporting_evidence_ids", [])
        clean.setdefault("counter_evidence_ids", [])
        clean.setdefault("matrix_row_ids", [])
        clean.setdefault("confidence", "medium")
        clean.setdefault("status", "draft")
        clean.setdefault("tags", [])
        self._validate_insight_card(project, clean)
        return self._create_asset(
            project,
            asset_kind="insight_cards",
            id_prefix="ic",
            id_field="id",
            index_field="insight_cards",
            payload=clean,
            index_builder=self._insight_card_index,
        )

    def list_insight_cards(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "insight_cards", "ic")

    def get_insight_card(self, project_id: str, card_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "insight_cards", card_id)

    def update_insight_card(
        self,
        project_id: str,
        card_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "title",
            "claim",
            "implication",
            "supporting_evidence_ids",
            "counter_evidence_ids",
            "matrix_row_ids",
            "confidence",
            "status",
            "tags",
            "notes",
            "updated_by",
        }
        return self._update_synthesis_asset(
            project_id,
            asset_kind="insight_cards",
            asset_id=card_id,
            index_field="insight_cards",
            allowed=allowed,
            updates=updates,
            validator=self._validate_insight_card,
            index_builder=self._insight_card_index,
        )

    def create_artifact_draft(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("source_insight_ids", [])
        clean.setdefault("source_evidence_ids", [])
        clean.setdefault("outline", [])
        clean.setdefault("status", "draft")
        clean.setdefault("material_readiness", "outline_only")
        self._validate_artifact_draft(project, clean)
        return self._create_asset(
            project,
            asset_kind="artifact_drafts",
            id_prefix="ad",
            id_field="id",
            index_field="artifact_drafts",
            payload=clean,
            index_builder=self._artifact_draft_index,
        )

    def list_artifact_drafts(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "artifact_drafts", "ad")

    def get_artifact_draft(self, project_id: str, draft_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "artifact_drafts", draft_id)

    def update_artifact_draft(
        self,
        project_id: str,
        draft_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "artifact_type",
            "title",
            "purpose",
            "audience",
            "source_insight_ids",
            "source_evidence_ids",
            "outline",
            "status",
            "material_readiness",
            "notes",
            "updated_by",
        }
        return self._update_synthesis_asset(
            project_id,
            asset_kind="artifact_drafts",
            asset_id=draft_id,
            index_field="artifact_drafts",
            allowed=allowed,
            updates=updates,
            validator=self._validate_artifact_draft,
            index_builder=self._artifact_draft_index,
        )

    def create_artifact_pack(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("pack_type", "leadership_deck")
        clean.setdefault("status", "draft")
        clean.setdefault("readiness", "idea")
        clean.setdefault("source_artifact_draft_ids", [])
        clean.setdefault("source_insight_ids", [])
        clean.setdefault("source_evidence_ids", [])
        clean.setdefault("items", [])
        clean.setdefault("pages", [])
        clean.setdefault("file_refs", [])
        clean.setdefault("review_rounds", [])
        clean.setdefault("decision_log", [])
        clean.setdefault("created_by", {})
        self._validate_artifact_pack(project, clean)
        return self._create_asset(
            project,
            asset_kind="artifact_packs",
            id_prefix="ap",
            id_field="pack_id",
            index_field="artifact_packs",
            payload=clean,
            index_builder=self._artifact_pack_index,
        )

    def list_artifact_packs(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "artifact_packs", "ap")

    def get_artifact_pack(self, project_id: str, pack_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "artifact_packs", pack_id)

    def update_artifact_pack(
        self,
        project_id: str,
        pack_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "title",
            "pack_type",
            "purpose",
            "audience",
            "status",
            "readiness",
            "source_artifact_draft_ids",
            "source_insight_ids",
            "source_evidence_ids",
            "notes",
            "updated_by",
        }
        return self._update_artifact_pack(project_id, pack_id, updates, allowed=allowed)

    def add_artifact_pack_item(
        self,
        project_id: str,
        pack_id: str,
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        return self._append_artifact_pack_child(
            project_id,
            pack_id,
            list_field="items",
            id_field="item_id",
            id_prefix="api",
            payload=payload,
            validator=self._validate_artifact_pack_item,
        )

    def update_artifact_pack_item(
        self,
        project_id: str,
        pack_id: str,
        item_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {"artifact_draft_id", "artifact_type", "title", "role_in_pack", "sequence", "status", "notes"}
        return self._update_artifact_pack_child(
            project_id,
            pack_id,
            list_field="items",
            id_field="item_id",
            child_id=item_id,
            updates=updates,
            allowed=allowed,
            validator=self._validate_artifact_pack_item,
        )

    def add_artifact_pack_page(
        self,
        project_id: str,
        pack_id: str,
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        return self._append_artifact_pack_child(
            project_id,
            pack_id,
            list_field="pages",
            id_field="page_id",
            id_prefix="pg",
            payload=payload,
            validator=self._validate_artifact_pack_page,
        )

    def update_artifact_pack_page(
        self,
        project_id: str,
        pack_id: str,
        page_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "sequence",
            "page_title",
            "page_type",
            "source_artifact_draft_id",
            "page_claim",
            "key_messages",
            "source_insight_ids",
            "source_evidence_ids",
            "source_matrix_row_ids",
            "visual_intent",
            "material_status",
            "review_status",
            "notes",
        }
        return self._update_artifact_pack_child(
            project_id,
            pack_id,
            list_field="pages",
            id_field="page_id",
            child_id=page_id,
            updates=updates,
            allowed=allowed,
            validator=self._validate_artifact_pack_page,
        )

    def add_artifact_pack_file_ref(
        self,
        project_id: str,
        pack_id: str,
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        return self._append_artifact_pack_child(
            project_id,
            pack_id,
            list_field="file_refs",
            id_field="file_ref_id",
            id_prefix="fr",
            payload=payload,
            validator=self._validate_artifact_pack_file_ref,
        )

    def update_artifact_pack_file_ref(
        self,
        project_id: str,
        pack_id: str,
        file_ref_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "file_kind",
            "title",
            "relative_path",
            "external_uri",
            "checksum",
            "size_bytes",
            "created_by_run_id",
            "linked_page_ids",
            "linked_artifact_draft_ids",
            "notes",
        }
        return self._update_artifact_pack_child(
            project_id,
            pack_id,
            list_field="file_refs",
            id_field="file_ref_id",
            child_id=file_ref_id,
            updates=updates,
            allowed=allowed,
            validator=self._validate_artifact_pack_file_ref,
        )

    def add_artifact_pack_review_round(
        self,
        project_id: str,
        pack_id: str,
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        return self._append_artifact_pack_child(
            project_id,
            pack_id,
            list_field="review_rounds",
            id_field="review_round_id",
            id_prefix="rv",
            payload=payload,
            validator=self._validate_artifact_pack_review_round,
        )

    def create_strategic_option(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("option_type", "strategic_path")
        clean.setdefault("status", "draft")
        clean.setdefault("recommendation_level", "recommended")
        clean.setdefault("decision_posture", "need_validation")
        clean.setdefault("source_insight_ids", [])
        clean.setdefault("source_evidence_matrix_row_ids", [])
        clean.setdefault("source_evidence_ids", [])
        clean.setdefault("source_artifact_draft_ids", [])
        clean.setdefault("source_artifact_pack_ids", [])
        clean.setdefault("assumptions", [])
        clean.setdefault("expected_benefits", [])
        clean.setdefault("risks", [])
        clean.setdefault("tradeoffs", [])
        clean.setdefault("success_metrics", [])
        clean.setdefault("review_state", "not_reviewed")
        clean.setdefault("decision_log", [])
        self._validate_strategic_option(project, clean)
        return self._create_asset(
            project,
            asset_kind="strategic_options",
            id_prefix="so",
            id_field="option_id",
            index_field="strategic_options",
            payload=clean,
            index_builder=self._strategic_option_index,
        )

    def list_strategic_options(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "strategic_options", "so")

    def get_strategic_option(self, project_id: str, option_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "strategic_options", option_id)

    def update_strategic_option(
        self,
        project_id: str,
        option_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "title",
            "summary",
            "option_type",
            "status",
            "recommendation_level",
            "decision_posture",
            "source_insight_ids",
            "source_evidence_matrix_row_ids",
            "source_evidence_ids",
            "source_artifact_draft_ids",
            "source_artifact_pack_ids",
            "assumptions",
            "expected_benefits",
            "risks",
            "tradeoffs",
            "success_metrics",
            "review_state",
            "review_notes",
            "decision_log",
            "updated_by",
        }
        return self._update_decision_asset(
            project_id,
            asset_kind="strategic_options",
            asset_id=option_id,
            id_field="option_id",
            index_field="strategic_options",
            allowed=allowed,
            updates=updates,
            validator=self._validate_strategic_option,
            index_builder=self._strategic_option_index,
        )

    def create_validation_plan(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("status", "draft")
        clean.setdefault("plan_type", "pilot_validation")
        clean.setdefault("linked_option_ids", [])
        clean.setdefault("source_insight_ids", [])
        clean.setdefault("source_evidence_ids", [])
        clean.setdefault("source_artifact_pack_ids", [])
        clean.setdefault("validation_questions", [])
        clean.setdefault("validation_methods", [])
        clean.setdefault("milestones", [])
        clean.setdefault("metrics", [])
        clean.setdefault("risks_to_validate", [])
        clean.setdefault("evidence_capture_plan", [])
        clean.setdefault("review_state", "not_reviewed")
        clean.setdefault("approval_state", "draft")
        clean.setdefault("decision_log", [])
        self._validate_validation_plan(project, clean)
        return self._create_asset(
            project,
            asset_kind="validation_plans",
            id_prefix="vp",
            id_field="plan_id",
            index_field="validation_plans",
            payload=clean,
            index_builder=self._validation_plan_index,
        )

    def list_validation_plans(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "validation_plans", "vp")

    def get_validation_plan(self, project_id: str, plan_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "validation_plans", plan_id)

    def update_validation_plan(
        self,
        project_id: str,
        plan_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "title",
            "summary",
            "status",
            "plan_type",
            "linked_option_ids",
            "source_insight_ids",
            "source_evidence_ids",
            "source_artifact_pack_ids",
            "validation_questions",
            "validation_methods",
            "milestones",
            "metrics",
            "risks_to_validate",
            "evidence_capture_plan",
            "review_state",
            "approval_state",
            "decision_log",
            "updated_by",
        }
        return self._update_decision_asset(
            project_id,
            asset_kind="validation_plans",
            asset_id=plan_id,
            id_field="plan_id",
            index_field="validation_plans",
            allowed=allowed,
            updates=updates,
            validator=self._validate_validation_plan,
            index_builder=self._validation_plan_index,
        )

    def create_leadership_decision_record(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("decision_status", "proposed")
        clean.setdefault("decision_type", "strategic_direction")
        clean.setdefault("linked_option_ids", [])
        clean.setdefault("linked_validation_plan_ids", [])
        clean.setdefault("source_insight_ids", [])
        clean.setdefault("source_artifact_pack_ids", [])
        clean.setdefault("rejected_option_ids", [])
        clean.setdefault("deferred_option_ids", [])
        clean.setdefault("rationale", [])
        clean.setdefault("conditions", [])
        clean.setdefault("open_questions", [])
        clean.setdefault("next_actions", [])
        clean.setdefault("review_rounds", [])
        clean.setdefault("decision_log", [])
        self._normalize_leadership_review_rounds(clean)
        self._validate_leadership_decision_record(project, clean)
        return self._create_asset(
            project,
            asset_kind="leadership_decision_records",
            id_prefix="ldr",
            id_field="decision_id",
            index_field="leadership_decision_records",
            payload=clean,
            index_builder=self._leadership_decision_record_index,
        )

    def list_leadership_decision_records(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        return self._list_assets(project_id, "leadership_decision_records", "ldr")

    def get_leadership_decision_record(
        self,
        project_id: str,
        decision_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "leadership_decision_records", decision_id)

    def update_leadership_decision_record(
        self,
        project_id: str,
        decision_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "title",
            "decision_status",
            "decision_type",
            "linked_option_ids",
            "linked_validation_plan_ids",
            "source_insight_ids",
            "source_artifact_pack_ids",
            "decision_summary",
            "chosen_option_id",
            "rejected_option_ids",
            "deferred_option_ids",
            "rationale",
            "conditions",
            "open_questions",
            "next_actions",
            "review_rounds",
            "decision_log",
            "updated_by",
        }
        return self._update_decision_asset(
            project_id,
            asset_kind="leadership_decision_records",
            asset_id=decision_id,
            id_field="decision_id",
            index_field="leadership_decision_records",
            allowed=allowed,
            updates=updates,
            validator=self._validate_leadership_decision_record,
            index_builder=self._leadership_decision_record_index,
            pre_validate=self._normalize_leadership_review_rounds,
        )

    def create_leadership_briefing(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("briefing_type", "strategic_readout")
        clean.setdefault("status", "draft")
        clean.setdefault("readiness", "not_ready")
        clean.setdefault("version", 1)
        clean.setdefault("executive_summary", {})
        clean.setdefault("source_asset_refs", [])
        clean.setdefault("sections", [])
        clean.setdefault("decision_asks", [])
        clean.setdefault("review_rounds", [])
        clean.setdefault("decision_log", [])
        self._normalize_leadership_briefing(clean)
        self._validate_leadership_briefing(project, clean)
        return self._create_asset(
            project,
            asset_kind="leadership_briefings",
            id_prefix="lb",
            id_field="briefing_id",
            index_field="leadership_briefings",
            payload=clean,
            index_builder=self._leadership_briefing_index,
        )

    def list_leadership_briefings(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        project = self.get(project_id)
        if project is None:
            return None
        return list(project.leadership_briefings or [])

    def get_leadership_briefing(
        self,
        project_id: str,
        briefing_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "leadership_briefings", briefing_id)

    def update_leadership_briefing(
        self,
        project_id: str,
        briefing_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "title",
            "briefing_type",
            "audience",
            "purpose",
            "status",
            "readiness",
            "version",
            "executive_summary",
            "source_asset_refs",
            "sections",
            "decision_asks",
            "review_rounds",
            "decision_log",
            "updated_by",
        }
        return self._update_decision_asset(
            project_id,
            asset_kind="leadership_briefings",
            asset_id=briefing_id,
            id_field="briefing_id",
            index_field="leadership_briefings",
            allowed=allowed,
            updates=updates,
            validator=self._validate_leadership_briefing,
            index_builder=self._leadership_briefing_index,
            pre_validate=self._normalize_leadership_briefing,
            history_asset_type="leadership_briefing",
        )

    def create_governance_review(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[tuple[dict[str, Any], bool]]:
        project = self.get(project_id)
        if project is None:
            return None
        idempotency_key = str(payload.get("idempotency_key") or "").strip()
        existing = self._find_by_idempotency(project_id, "governance_reviews", "gr", idempotency_key)
        if existing is not None and payload.get("seed_from_traceability_map") is True:
            return existing, True
        clean = dict(payload)
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        clean.setdefault("review_type", "stage_gate")
        clean.setdefault("status", "draft")
        clean.setdefault("gate_decision", "not_decided")
        clean.setdefault("readiness", "not_ready")
        clean.setdefault("traceability_map_version", {})
        clean.setdefault("checklist_items", [])
        clean.setdefault("findings", [])
        clean.setdefault("risk_dispositions", [])
        clean.setdefault("signoffs", [])
        clean.setdefault("review_summary", {})
        if clean.get("seed_from_traceability_map") is True:
            self._seed_governance_review_from_traceability(project, clean)
        self._normalize_governance_review(clean)
        self._validate_governance_review(project, clean)
        return self._create_asset(
            project,
            asset_kind="governance_reviews",
            id_prefix="gr",
            id_field="review_id",
            index_field="governance_reviews",
            payload=clean,
            index_builder=self._governance_review_index,
        )

    def list_governance_reviews(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        project = self.get(project_id)
        if project is None:
            return None
        return list(project.governance_reviews or [])

    def get_governance_review(self, project_id: str, review_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "governance_reviews", review_id)

    def update_governance_review(
        self,
        project_id: str,
        review_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        allowed = {
            "title",
            "review_type",
            "status",
            "gate_decision",
            "readiness",
            "checklist_items",
            "findings",
            "risk_dispositions",
            "signoffs",
            "review_summary",
            "updated_by",
        }
        return self._update_decision_asset(
            project_id,
            asset_kind="governance_reviews",
            asset_id=review_id,
            id_field="review_id",
            index_field="governance_reviews",
            allowed=allowed,
            updates=updates,
            validator=self._validate_governance_review,
            index_builder=self._governance_review_index,
            pre_validate=self._normalize_governance_review,
            history_asset_type="governance_review",
        )

    def list_review_history(
        self,
        project_id: str,
        *,
        asset_type: str | None = None,
        asset_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> Optional[list[dict[str, Any]]]:
        if self.get(project_id) is None:
            return None
        entries = self._list_assets(project_id, "review_history", "rhe")
        if asset_type:
            entries = [entry for entry in entries if entry.get("asset_type") == asset_type]
        if asset_id:
            entries = [entry for entry in entries if entry.get("asset_id") == asset_id]
        if event_type:
            entries = [entry for entry in entries if entry.get("event_type") == event_type]
        entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return entries[: max(1, min(int(limit or 50), 200))]

    def get_review_history_entry(self, project_id: str, history_entry_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "review_history", history_entry_id)

    def create_review_history_note(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        self._require_text(clean, "asset_type", "asset_id", "note")
        asset_ref = {
            "asset_type": clean["asset_type"],
            "asset_id": clean["asset_id"],
        }
        self._validate_source_ref(project, asset_ref, "review_history_note.asset_ref")
        related = clean.get("related_asset_refs") or []
        self._validate_source_refs(project, related, "related_asset_refs")
        actor = clean.get("actor") or {
            "actor_type": "manual_user",
            "display_name": "Reviewer",
        }
        if not isinstance(actor, dict):
            raise ResearchProjectStoreError("actor must be an object")
        entry = self._make_review_history_entry(
            project=project,
            asset_type=clean["asset_type"],
            asset_id=clean["asset_id"],
            event_type="review_note_added",
            event_source="manual_note",
            changed_fields=[],
            note=str(clean.get("note") or ""),
            actor=actor,
            related_asset_refs=related,
            summary="Review note added.",
            correlation_id=str(clean.get("correlation_id") or ""),
        )
        return self._persist_review_history_entry(project, entry)

    def create_research_snapshot(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        clean = dict(payload)
        self._require_text(clean, "title")
        included = self._normalize_snapshot_asset_kinds(clean.get("included_asset_kinds"))
        governance_review_id = str(clean.get("governance_review_id") or "").strip()
        if governance_review_id:
            self._validate_asset_refs(
                project,
                field="governance_review_id",
                values=[governance_review_id],
                asset_kind="governance_reviews",
                id_prefix="gr",
                index_values=project.governance_reviews,
                id_field="review_id",
            )
        actor = clean.get("actor") or {"actor_type": "manual_user", "display_name": "Reviewer"}
        if isinstance(actor, str):
            actor = {"actor_type": "manual_user", "display_name": actor}
        if not isinstance(actor, dict):
            raise ResearchProjectStoreError("actor must be an object or string")

        now = _now_iso()
        snapshot_id = clean.get("snapshot_id") or _new_prefixed_id("rs")
        if not re.match(r"^rs_[0-9a-f]{12}$", snapshot_id):
            raise ResearchProjectStoreError("snapshot_id must use rs_ prefix")
        capture = self._build_research_snapshot_capture(
            project,
            included_asset_kinds=included,
            linked_governance_review_id=governance_review_id,
        )
        snapshot = {
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "project_id": project.id,
            "title": str(clean.get("title") or "").strip(),
            "reason": str(clean.get("reason") or ""),
            "gate_type": str(clean.get("gate_type") or "manual_gate"),
            "actor": {
                "actor_type": str(actor.get("actor_type") or "manual_user"),
                "actor_id": str(actor.get("actor_id") or ""),
                "display_name": str(actor.get("display_name") or "Reviewer"),
            },
            "created_at": now,
            **capture,
        }
        fingerprint_payload = {
            key: value for key, value in snapshot.items()
            if key != "snapshot_fingerprint"
        }
        snapshot["snapshot_fingerprint"] = self._fingerprint_payload(fingerprint_payload)
        self._persist_research_snapshot(project, snapshot)
        self._record_research_snapshot_history(project, snapshot)
        return snapshot

    def list_research_snapshots(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        project = self.get(project_id)
        if project is None:
            return None
        snapshots = list(project.research_snapshots or [])
        snapshots.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return snapshots

    def get_research_snapshot(self, project_id: str, snapshot_id: str) -> Optional[dict[str, Any]]:
        if self.get(project_id) is None:
            return None
        return self._read_asset(project_id, "research_snapshots", snapshot_id)

    def diff_research_snapshot_to_current(self, project_id: str, snapshot_id: str) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        snapshot = self._read_asset(project_id, "research_snapshots", snapshot_id)
        if snapshot is None:
            raise ResearchProjectStoreError(f"research snapshot not found: {snapshot_id}")
        current = self._build_research_snapshot_capture(
            project,
            included_asset_kinds=snapshot.get("included_asset_kinds") or [],
            linked_governance_review_id=(snapshot.get("linked_governance_review") or {}).get("governance_review_id", ""),
        )
        return self._diff_snapshot_captures(snapshot, current, compared_at=_now_iso())

    def create_snapshot_review_note(
        self,
        project_id: str,
        snapshot_id: str,
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        snapshot = self._read_asset(project_id, "research_snapshots", snapshot_id)
        if snapshot is None:
            raise ResearchProjectStoreError(f"research snapshot not found: {snapshot_id}")
        clean = self._validate_snapshot_review_note_payload(payload)
        actor = clean.get("actor") or {"actor_type": "manual_user", "display_name": "Reviewer"}
        if isinstance(actor, str):
            actor = {"actor_type": "manual_user", "display_name": actor}
        if not isinstance(actor, dict):
            raise ResearchProjectStoreError("actor must be an object or string")

        now = _now_iso()
        note_id = clean.get("note_id") or _new_prefixed_id("srn")
        if not re.match(r"^srn_[0-9a-f]{12}$", note_id):
            raise ResearchProjectStoreError("note_id must use srn_ prefix")
        target_ref = clean["target_ref"]
        note = {
            "schema_version": 1,
            "note_id": note_id,
            "project_id": project.id,
            "snapshot_id": snapshot_id,
            "target_ref": target_ref,
            "note_type": clean["note_type"],
            "severity": clean["severity"],
            "status": "open",
            "owner": "",
            "resolution_note": "",
            "resolved_at": "",
            "resolved_by": "",
            "note": clean["note"],
            "actor": {
                "actor_type": str(actor.get("actor_type") or "manual_user"),
                "actor_id": str(actor.get("actor_id") or ""),
                "display_name": str(actor.get("display_name") or "Reviewer"),
            },
            "created_at": now,
            "updated_at": now,
            "source": {
                "kind": "snapshot_diff_review",
                "snapshot_id": snapshot_id,
                "created_from": "snapshot_evidence_review_panel",
            },
        }
        self._persist_snapshot_review_note(project, note)
        history = self._record_snapshot_review_note_history(project, note)
        return {
            "snapshot_review_note": note,
            "review_history_entry": history,
        }

    def list_snapshot_review_notes(self, project_id: str, snapshot_id: str) -> Optional[list[dict[str, Any]]]:
        project = self.get(project_id)
        if project is None:
            return None
        if self._read_asset(project_id, "research_snapshots", snapshot_id) is None:
            raise ResearchProjectStoreError(f"research snapshot not found: {snapshot_id}")
        notes = [
            note for note in self._list_assets(project_id, "snapshot_review_notes", "srn")
            if note.get("snapshot_id") == snapshot_id
        ]
        notes.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return notes

    def get_snapshot_review_note(self, project_id: str, snapshot_id: str, note_id: str) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        if self._read_asset(project_id, "research_snapshots", snapshot_id) is None:
            raise ResearchProjectStoreError(f"research snapshot not found: {snapshot_id}")
        note = self._read_asset(project_id, "snapshot_review_notes", note_id)
        if note is None or note.get("snapshot_id") != snapshot_id:
            return None
        return note

    def update_snapshot_review_note(
        self,
        project_id: str,
        snapshot_id: str,
        note_id: str,
        payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        if self._read_asset(project_id, "research_snapshots", snapshot_id) is None:
            raise ResearchProjectStoreError(f"research snapshot not found: {snapshot_id}")
        note = self._read_asset(project_id, "snapshot_review_notes", note_id)
        if note is None or note.get("snapshot_id") != snapshot_id:
            return None
        clean = self._validate_snapshot_review_note_update_payload(payload)
        actor = clean["actor"]
        actor_display = str(actor.get("display_name") or actor.get("actor_id") or "Reviewer")

        before = dict(note)
        after = dict(note)
        if "status" in clean:
            after["status"] = clean["status"]
        if "owner" in clean:
            after["owner"] = clean["owner"]
        if "resolution_note" in clean:
            after["resolution_note"] = clean["resolution_note"]

        old_status = str(before.get("status") or "open")
        new_status = str(after.get("status") or "open")
        now = _now_iso()
        if old_status != "resolved" and new_status == "resolved":
            after["resolved_at"] = now
            after["resolved_by"] = actor_display
        elif old_status == "resolved" and new_status != "resolved":
            after["resolved_at"] = ""
            after["resolved_by"] = ""

        changed_fields = self._snapshot_review_note_disposition_changes(before, after)
        if not changed_fields:
            return {"snapshot_review_note": note, "review_history_entry": None}

        after["updated_at"] = now
        self._persist_snapshot_review_note(project, after)
        history = self._record_snapshot_review_note_disposition_history(
            project,
            before,
            after,
            actor,
            changed_fields,
        )
        return {
            "snapshot_review_note": after,
            "review_history_entry": history,
        }

    def update_external_research_candidate_status(
        self,
        project_id: str,
        pack_id: str,
        candidate_id: str,
        *,
        review_status: str,
        review_note: str = "",
    ) -> Optional[tuple[dict[str, Any], ResearchProject]]:
        if review_status not in {"pending", "accepted", "rejected"}:
            raise ValueError("review_status must be pending, accepted, or rejected")
        project = self.get(project_id)
        if project is None:
            return None
        pack = self._read_asset(project_id, "external_research_packs", pack_id)
        if pack is None:
            raise ResearchProjectStoreError(f"external research pack not found: {pack_id}")

        target = None
        for candidate in pack.get("evidence_candidates") or []:
            if candidate.get("candidate_id") == candidate_id or candidate.get("external_id") == candidate_id:
                target = candidate
                break
        if target is None:
            raise ResearchProjectStoreError(f"external research candidate not found: {candidate_id}")

        now = _now_iso()
        target["review_status"] = review_status
        target["review_note"] = review_note
        target["reviewed_at"] = now
        pack["updated_at"] = now
        pack["accepted_candidate_ids"] = sorted(
            candidate.get("candidate_id", "")
            for candidate in pack.get("evidence_candidates") or []
            if candidate.get("review_status") == "accepted" and candidate.get("candidate_id")
        )
        pack["rejected_candidate_ids"] = sorted(
            candidate.get("candidate_id", "")
            for candidate in pack.get("evidence_candidates") or []
            if candidate.get("review_status") == "rejected" and candidate.get("candidate_id")
        )
        pack["accepted_count"] = len(pack["accepted_candidate_ids"])
        pack["rejected_count"] = len(pack["rejected_candidate_ids"])

        if review_status == "accepted":
            self._upsert_external_evidence_item(project, pack, target, accepted_at=now)
        else:
            evidence_id = self._external_evidence_id(pack, target)
            project.evidence_items = [
                item for item in project.evidence_items
                if item.get("evidence_id") != evidence_id
            ]

        self._atomic_write(self._asset_path(project_id, "external_research_packs", pack_id), pack)
        self._write_index_item(project, "external_research_packs", "pack_id", self._external_pack_index(pack))
        project.updated_at = now
        self.save(project)
        return pack, project

    def _create_asset(
        self,
        project: ResearchProject,
        *,
        asset_kind: str,
        id_prefix: str,
        id_field: str,
        index_field: str,
        payload: dict[str, Any],
        index_builder,
    ) -> tuple[dict[str, Any], bool]:
        clean = dict(payload)
        idempotency_key = str(clean.get("idempotency_key") or "").strip()
        hash_input = {
            key: value
            for key, value in clean.items()
            if key not in {id_field, "created_at", "updated_at"}
        }
        payload_hash = _payload_hash(hash_input)
        existing = self._find_by_idempotency(project.id, asset_kind, id_prefix, idempotency_key)
        if existing is not None:
            if existing.get("payload_hash") != payload_hash:
                raise ResearchProjectStoreError("idempotency key conflict")
            return existing, True

        now = _now_iso()
        clean[id_field] = clean.get(id_field) or _new_prefixed_id(id_prefix)
        clean["project_id"] = project.id
        clean.setdefault("status", "imported" if asset_kind == "external_research_packs" else "completed")
        clean["idempotency_key"] = idempotency_key
        clean["payload_hash"] = payload_hash
        clean["created_at"] = now
        clean["updated_at"] = now
        self._atomic_write(self._asset_path(project.id, asset_kind, clean[id_field]), clean)
        self._write_index_item(project, index_field, id_field, index_builder(clean))
        project.updated_at = now
        self.save(project)
        return clean, False

    def _update_synthesis_asset(
        self,
        project_id: str,
        *,
        asset_kind: str,
        asset_id: str,
        index_field: str,
        allowed: set[str],
        updates: dict[str, Any],
        validator,
        index_builder,
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise ResearchProjectStoreError(f"unsupported fields: {', '.join(unknown)}")
        asset = self._read_asset(project_id, asset_kind, asset_id)
        if asset is None:
            raise ResearchProjectStoreError(f"research synthesis asset not found: {asset_id}")
        clean = {**asset, **updates}
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        validator(project, clean)
        clean["updated_at"] = _now_iso()
        clean["payload_hash"] = _payload_hash({
            key: value
            for key, value in clean.items()
            if key not in {"created_at", "updated_at", "payload_hash"}
        })
        self._atomic_write(self._asset_path(project_id, asset_kind, asset_id), clean)
        self._write_index_item(project, index_field, "id", index_builder(clean))
        project.updated_at = clean["updated_at"]
        self.save(project)
        return clean

    def _update_decision_asset(
        self,
        project_id: str,
        *,
        asset_kind: str,
        asset_id: str,
        id_field: str,
        index_field: str,
        allowed: set[str],
        updates: dict[str, Any],
        validator,
        index_builder,
        pre_validate=None,
        history_asset_type: str | None = None,
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise ResearchProjectStoreError(f"unsupported fields: {', '.join(unknown)}")
        asset = self._read_asset(project_id, asset_kind, asset_id)
        if asset is None:
            raise ResearchProjectStoreError(f"research decision asset not found: {asset_id}")
        clean = {**asset, **updates}
        clean["schema_version"] = int(clean.get("schema_version") or 1)
        if pre_validate is not None:
            pre_validate(clean)
        validator(project, clean)
        clean["updated_at"] = _now_iso()
        clean["payload_hash"] = _payload_hash({
            key: value
            for key, value in clean.items()
            if key not in {"created_at", "updated_at", "payload_hash"}
        })
        self._atomic_write(self._asset_path(project_id, asset_kind, asset_id), clean)
        self._write_index_item(project, index_field, id_field, index_builder(clean))
        project.updated_at = clean["updated_at"]
        self.save(project)
        if history_asset_type:
            self._record_review_history_from_update(
                project,
                asset_type=history_asset_type,
                asset_id=asset_id,
                before=asset,
                after=clean,
                event_source="kfc_api_patch",
                actor={"actor_type": "manual_user", "display_name": str(clean.get("updated_by") or "Reviewer")},
            )
        return clean

    def _record_review_history_from_update(
        self,
        project: ResearchProject,
        *,
        asset_type: str,
        asset_id: str,
        before: dict[str, Any],
        after: dict[str, Any],
        event_source: str,
        actor: dict[str, Any],
        note: str = "",
        correlation_id: str = "",
    ) -> Optional[dict[str, Any]]:
        changed_fields = self._review_history_changed_fields(before, after)
        if not changed_fields:
            return None
        entry = self._make_review_history_entry(
            project=project,
            asset_type=asset_type,
            asset_id=asset_id,
            event_type=self._review_history_event_type(changed_fields),
            event_source=event_source,
            changed_fields=changed_fields,
            note=note,
            actor=actor,
            related_asset_refs=self._review_history_related_refs(after),
            summary=self._review_history_summary(asset_type, after, changed_fields),
            correlation_id=correlation_id,
        )
        return self._persist_review_history_entry(project, entry)

    def _make_review_history_entry(
        self,
        *,
        project: ResearchProject,
        asset_type: str,
        asset_id: str,
        event_type: str,
        event_source: str,
        changed_fields: list[dict[str, Any]],
        note: str,
        actor: dict[str, Any],
        related_asset_refs: list[dict[str, Any]],
        summary: str,
        correlation_id: str = "",
    ) -> dict[str, Any]:
        return {
            "history_entry_id": _new_prefixed_id("rhe"),
            "schema_version": 1,
            "project_id": project.id,
            "asset_type": asset_type,
            "asset_id": asset_id,
            "asset_title": self._asset_title_for_history(asset_type, asset_id),
            "event_type": event_type,
            "event_source": event_source,
            "actor": {
                "actor_type": str(actor.get("actor_type") or "manual_user"),
                "actor_id": str(actor.get("actor_id") or ""),
                "display_name": str(actor.get("display_name") or "Reviewer"),
            },
            "created_at": _now_iso(),
            "correlation_id": correlation_id,
            "changed_fields": changed_fields,
            "review_context": {
                "related_asset_refs": related_asset_refs,
            },
            "note": note,
            "summary": summary,
            "metadata": {"schema_version": 1},
        }

    def _persist_review_history_entry(self, project: ResearchProject, entry: dict[str, Any]) -> dict[str, Any]:
        self._atomic_write(
            self._asset_path(project.id, "review_history", entry["history_entry_id"]),
            entry,
        )
        self._write_index_item(
            project,
            "review_history_entries",
            "history_entry_id",
            self._review_history_index(entry),
        )
        project.updated_at = entry["created_at"]
        self.save(project)
        return entry

    def _review_history_changed_fields(self, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
        ignored = {"updated_at", "payload_hash"}
        changes: list[dict[str, Any]] = []
        keys = sorted((set(before) | set(after)) - ignored)
        for key in keys:
            old_value = self._normalize_history_value(before.get(key))
            new_value = self._normalize_history_value(after.get(key))
            if old_value == new_value:
                continue
            changes.append({
                "path": key,
                "old_value": self._history_value_payload(before.get(key)),
                "new_value": self._history_value_payload(after.get(key)),
                "change_kind": "updated" if key in before and key in after else ("added" if key in after else "removed"),
            })
        return changes

    def _normalize_history_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._normalize_history_value(value[key])
                for key in sorted(value)
                if key not in {"updated_at", "payload_hash"}
            }
        if isinstance(value, list):
            if all(isinstance(item, str) for item in value):
                return sorted(value)
            return [self._normalize_history_value(item) for item in value]
        return value

    def _history_value_payload(self, value: Any) -> Any:
        if isinstance(value, str):
            if len(value) > 400:
                return {
                    "preview": value[:200],
                    "hash": f"sha256:{sha256(value.encode('utf-8')).hexdigest()}",
                    "truncated": True,
                }
            return value
        if isinstance(value, (dict, list)):
            raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if len(raw) > 1000:
                return {
                    "preview": raw[:200],
                    "hash": f"sha256:{sha256(raw.encode('utf-8')).hexdigest()}",
                    "truncated": True,
                }
        return value

    def _review_history_event_type(self, changed_fields: list[dict[str, Any]]) -> str:
        paths = {str(item.get("path") or "") for item in changed_fields}
        if "gate_decision" in paths:
            return "gate_decision_changed"
        if any(path.startswith("signoffs") or path == "signoffs" for path in paths):
            return "signoff_changed"
        if "approval_state" in paths:
            return "approval_changed"
        if "readiness" in paths:
            return "readiness_changed"
        if paths & {"status", "review_status", "review_state", "decision_status"}:
            return "status_changed"
        if any("source_" in path or path.endswith("_refs") or path.endswith("_ids") for path in paths):
            return "source_reference_changed"
        return "field_changed"

    def _review_history_summary(self, asset_type: str, after: dict[str, Any], changed_fields: list[dict[str, Any]]) -> str:
        labels = ", ".join(str(item.get("path") or "") for item in changed_fields[:3])
        title = after.get("title") or after.get("question") or after.get("claim") or after.get("review_id") or after.get("briefing_id") or ""
        return f"{asset_type} {title} changed: {labels}".strip()

    def _review_history_related_refs(self, asset: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for field in ("source_asset_refs", "source_refs", "related_asset_refs"):
            value = asset.get(field)
            if isinstance(value, list):
                refs.extend(ref for ref in value if isinstance(ref, dict) and ref.get("asset_type") and ref.get("asset_id"))
        if asset.get("traceability_map_version"):
            refs.append({
                "asset_type": "traceability_map",
                "asset_id": str((asset.get("traceability_map_version") or {}).get("computed_at") or "computed"),
            })
        seen: set[tuple[str, str]] = set()
        unique: list[dict[str, Any]] = []
        for ref in refs:
            key = (str(ref.get("asset_type")), str(ref.get("asset_id")))
            if key in seen:
                continue
            seen.add(key)
            unique.append({"asset_type": key[0], "asset_id": key[1]})
        return unique[:20]

    def _asset_title_for_history(self, asset_type: str, asset_id: str) -> str:
        id_field_by_type = {
            "governance_review": "review_id",
            "leadership_briefing": "briefing_id",
        }
        kind_by_type = {
            "governance_review": "governance_reviews",
            "leadership_briefing": "leadership_briefings",
        }
        prefix_by_type = {
            "governance_review": "gr",
            "leadership_briefing": "lb",
        }
        # The caller already has project-scoped validation; this helper only
        # provides display metadata for timeline rows.
        return asset_id

    def _review_history_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "history_entry_id": item["history_entry_id"],
            "asset_type": item.get("asset_type", ""),
            "asset_id": item.get("asset_id", ""),
            "asset_title": item.get("asset_title", ""),
            "event_type": item.get("event_type", ""),
            "event_source": item.get("event_source", ""),
            "summary": item.get("summary", ""),
            "actor": item.get("actor") or {},
            "changed_field_count": len(item.get("changed_fields") or []),
            "note": item.get("note", ""),
            "created_at": item.get("created_at", ""),
        }

    def _normalize_snapshot_asset_kinds(self, values: Any) -> list[str]:
        if values in (None, ""):
            values = [
                "project",
                "evidence_items",
                "evidence_matrix_rows",
                "insight_cards",
                "artifact_drafts",
                "artifact_packs",
                "strategic_options",
                "validation_plans",
                "leadership_decision_records",
                "leadership_briefings",
                "governance_reviews",
                "review_history",
            ]
        if not isinstance(values, list):
            raise ResearchProjectStoreError("included_asset_kinds must be an array")
        normalized: list[str] = []
        for value in values:
            kind = str(value or "").strip()
            if kind not in self.SUPPORTED_SNAPSHOT_ASSET_KINDS:
                allowed = ", ".join(sorted(self.SUPPORTED_SNAPSHOT_ASSET_KINDS))
                raise ResearchProjectStoreError(f"included_asset_kinds must be one of: {allowed}")
            if kind not in normalized:
                normalized.append(kind)
        return normalized

    def _build_research_snapshot_capture(
        self,
        project: ResearchProject,
        *,
        included_asset_kinds: list[str],
        linked_governance_review_id: str = "",
    ) -> dict[str, Any]:
        included = self._normalize_snapshot_asset_kinds(included_asset_kinds)
        asset_kind_summaries: dict[str, Any] = {}
        asset_fingerprints: dict[str, list[dict[str, Any]]] = {}
        for kind in included:
            if kind == "project":
                continue
            compact_items = [
                self._compact_snapshot_asset(kind, item)
                for item in self._snapshot_items_for_kind(project, kind)
            ]
            compact_items = [item for item in compact_items if item.get("asset_id")]
            compact_items.sort(key=lambda item: item.get("asset_id", ""))
            asset_fingerprints[kind] = compact_items
            asset_kind_summaries[kind] = self._snapshot_kind_summary(compact_items)

        governance = self._snapshot_governance_link(project, linked_governance_review_id)
        briefing = self._snapshot_leadership_briefing_link(project)
        return {
            "included_asset_kinds": included,
            "project_summary": {
                "project_id": project.id,
                "title": project.title,
                "status": project.status.value if isinstance(project.status, ResearchProjectStatus) else project.status,
                "updated_at": project.updated_at,
            },
            "asset_kind_summaries": asset_kind_summaries,
            "asset_fingerprints": asset_fingerprints,
            "review_history_watermark": self._review_history_watermark(project),
            "linked_governance_review": governance,
            "linked_leadership_briefing": briefing,
        }

    def _snapshot_items_for_kind(self, project: ResearchProject, kind: str) -> list[dict[str, Any]]:
        if kind == "review_history":
            return list(project.review_history_entries or [])
        values = getattr(project, kind, [])
        return [item for item in (values or []) if isinstance(item, dict)]

    def _compact_snapshot_asset(self, kind: str, item: dict[str, Any]) -> dict[str, Any]:
        id_field = self.SNAPSHOT_ID_FIELDS[kind]
        asset_id = str(item.get(id_field) or "")
        selected = {
            "asset_id": asset_id,
            "asset_type": self.SNAPSHOT_ASSET_TYPES[kind],
            "title": str(item.get("title") or item.get("question") or item.get("claim") or item.get("summary") or asset_id),
            "status": str(item.get("status") or item.get("review_status") or item.get("decision_status") or ""),
            "readiness": str(item.get("readiness") or item.get("review_state") or item.get("approval_state") or ""),
            "gate_decision": str(item.get("gate_decision") or ""),
            "approval_state": str(item.get("approval_state") or ""),
            "review_state": str(item.get("review_state") or ""),
            "decision_status": str(item.get("decision_status") or ""),
            "updated_at": str(item.get("updated_at") or item.get("created_at") or ""),
            "source_ref_count": self._snapshot_source_ref_count(item),
        }
        selected["fingerprint"] = self._fingerprint_payload(selected)
        return selected

    def _snapshot_source_ref_count(self, item: dict[str, Any]) -> int:
        total = 0
        for key, value in item.items():
            if not isinstance(value, list):
                continue
            if key.endswith("_ids") or key.endswith("_refs") or key.startswith("source_") or key.startswith("linked_"):
                total += len(value)
        return total

    def _snapshot_kind_summary(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        latest = max((item.get("updated_at") or "" for item in items), default="")
        status_counts: dict[str, int] = {}
        readiness_counts: dict[str, int] = {}
        gate_decision_counts: dict[str, int] = {}
        for item in items:
            for source, target in (
                (item.get("status"), status_counts),
                (item.get("readiness"), readiness_counts),
                (item.get("gate_decision"), gate_decision_counts),
            ):
                if source:
                    target[str(source)] = target.get(str(source), 0) + 1
        return {
            "count": len(items),
            "status_counts": status_counts,
            "readiness_counts": readiness_counts,
            "gate_decision_counts": gate_decision_counts,
            "latest_updated_at": latest,
            "kind_fingerprint": self._fingerprint_payload({"items": items}),
        }

    def _review_history_watermark(self, project: ResearchProject) -> dict[str, Any]:
        entries = list(project.review_history_entries or [])
        entries.sort(key=lambda item: item.get("created_at", ""))
        latest = entries[-1] if entries else {}
        return {
            "latest_entry_id": latest.get("history_entry_id", ""),
            "latest_created_at": latest.get("created_at", ""),
            "entry_count": len(entries),
        }

    def _snapshot_governance_link(self, project: ResearchProject, review_id: str = "") -> dict[str, Any]:
        reviews = [item for item in project.governance_reviews or [] if isinstance(item, dict)]
        review = None
        if review_id:
            review = next((item for item in reviews if item.get("review_id") == review_id), None)
        if review is None and reviews:
            reviews.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
            review = reviews[0]
        if review is None:
            return {}
        return {
            "governance_review_id": review.get("review_id", ""),
            "gate_decision": review.get("gate_decision", ""),
            "readiness": review.get("readiness", ""),
            "ready_for_next_stage": bool(review.get("ready_for_next_stage") or (review.get("review_summary") or {}).get("ready_for_next_stage")),
        }

    def _snapshot_leadership_briefing_link(self, project: ResearchProject) -> dict[str, Any]:
        briefings = [item for item in project.leadership_briefings or [] if isinstance(item, dict)]
        if not briefings:
            return {}
        briefings.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
        briefing = briefings[0]
        return {
            "briefing_id": briefing.get("briefing_id", ""),
            "readiness": briefing.get("readiness", ""),
            "status": briefing.get("status", ""),
            "approval_state": briefing.get("approval_state", ""),
        }

    def _persist_research_snapshot(self, project: ResearchProject, snapshot: dict[str, Any]) -> None:
        self._atomic_write(
            self._asset_path(project.id, "research_snapshots", snapshot["snapshot_id"]),
            snapshot,
        )
        self._write_index_item(
            project,
            "research_snapshots",
            "snapshot_id",
            self._research_snapshot_index(snapshot),
        )
        project.updated_at = snapshot["created_at"]
        self.save(project)

    def _record_research_snapshot_history(self, project: ResearchProject, snapshot: dict[str, Any]) -> dict[str, Any]:
        entry = self._make_review_history_entry(
            project=project,
            asset_type="research_snapshot",
            asset_id=snapshot["snapshot_id"],
            event_type="research_snapshot_created",
            event_source="manual_snapshot",
            changed_fields=[{
                "path": "research_snapshots",
                "old_value": max(0, len(project.research_snapshots or []) - 1),
                "new_value": len(project.research_snapshots or []),
                "change_kind": "added",
            }],
            note=str(snapshot.get("reason") or ""),
            actor=snapshot.get("actor") or {"actor_type": "manual_user", "display_name": "Reviewer"},
            related_asset_refs=([
                {
                    "asset_type": "governance_review",
                    "asset_id": snapshot["linked_governance_review"]["governance_review_id"],
                }
            ] if (snapshot.get("linked_governance_review") or {}).get("governance_review_id") else []),
            summary=f"Created research baseline snapshot: {snapshot.get('title', '')}".strip(),
        )
        return self._persist_review_history_entry(project, entry)

    def _persist_snapshot_review_note(self, project: ResearchProject, note: dict[str, Any]) -> None:
        self._atomic_write(
            self._asset_path(project.id, "snapshot_review_notes", note["note_id"]),
            note,
        )
        self._write_index_item(
            project,
            "snapshot_review_notes",
            "note_id",
            self._snapshot_review_note_index(note),
        )
        project.updated_at = note.get("updated_at") or note["created_at"]
        self.save(project)

    def _record_snapshot_review_note_history(self, project: ResearchProject, note: dict[str, Any]) -> dict[str, Any]:
        target_ref = note.get("target_ref") or {}
        related = [{
            "asset_type": "research_snapshot",
            "asset_id": note["snapshot_id"],
        }]
        if target_ref.get("asset_kind") and target_ref.get("asset_id"):
            related.append({
                "asset_type": str(target_ref.get("asset_kind")),
                "asset_id": str(target_ref.get("asset_id")),
            })
        entry = self._make_review_history_entry(
            project=project,
            asset_type="snapshot_review_note",
            asset_id=note["note_id"],
            event_type="snapshot_review_note_created",
            event_source="manual_snapshot_review_note",
            changed_fields=[{
                "path": "snapshot_review_notes",
                "old_value": max(0, len(project.snapshot_review_notes or []) - 1),
                "new_value": len(project.snapshot_review_notes or []),
                "change_kind": "added",
            }],
            note=str(note.get("note") or ""),
            actor=note.get("actor") or {"actor_type": "manual_user", "display_name": "Reviewer"},
            related_asset_refs=related,
            summary=f"Manual snapshot review note created for snapshot {note.get('snapshot_id', '')}".strip(),
        )
        entry["metadata"] = {
            "schema_version": 1,
            "snapshot_id": note.get("snapshot_id", ""),
            "section_key": target_ref.get("section_key", ""),
            "note_type": note.get("note_type", ""),
            "severity": note.get("severity", ""),
        }
        return self._persist_review_history_entry(project, entry)

    def _record_snapshot_review_note_disposition_history(
        self,
        project: ResearchProject,
        before: dict[str, Any],
        after: dict[str, Any],
        actor: dict[str, Any],
        changed_fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        target_ref = after.get("target_ref") or {}
        related = [{
            "asset_type": "research_snapshot",
            "asset_id": after["snapshot_id"],
        }]
        if target_ref.get("asset_kind") and target_ref.get("asset_id"):
            related.append({
                "asset_type": str(target_ref.get("asset_kind")),
                "asset_id": str(target_ref.get("asset_id")),
            })
        status_before = str(before.get("status") or "open")
        status_after = str(after.get("status") or "open")
        entry = self._make_review_history_entry(
            project=project,
            asset_type="snapshot_review_note",
            asset_id=after["note_id"],
            event_type="snapshot_review_note_disposition_updated",
            event_source="manual_snapshot_review_note",
            changed_fields=changed_fields,
            note=str(after.get("resolution_note") or ""),
            actor=actor,
            related_asset_refs=related,
            summary=f"Snapshot review note disposition updated from {status_before} to {status_after}.",
        )
        entry["metadata"] = {
            "schema_version": 1,
            "snapshot_id": after.get("snapshot_id", ""),
            "section_key": target_ref.get("section_key", ""),
            "note_type": after.get("note_type", ""),
            "severity": after.get("severity", ""),
            "status_before": status_before,
            "status_after": status_after,
        }
        return self._persist_review_history_entry(project, entry)

    def _snapshot_review_note_disposition_changes(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for field in ("status", "owner", "resolution_note", "resolved_at", "resolved_by"):
            old_value = before.get(field) or ""
            new_value = after.get(field) or ""
            if old_value == new_value:
                continue
            changes.append({
                "path": f"snapshot_review_notes.{field}",
                "old_value": old_value,
                "new_value": new_value,
                "change_kind": "updated",
            })
        return changes

    def _snapshot_review_note_index(self, note: dict[str, Any]) -> dict[str, Any]:
        target_ref = note.get("target_ref") or {}
        return {
            "note_id": note["note_id"],
            "snapshot_id": note.get("snapshot_id", ""),
            "section_key": target_ref.get("section_key", ""),
            "asset_kind": target_ref.get("asset_kind", ""),
            "asset_id": target_ref.get("asset_id", ""),
            "field": target_ref.get("field", ""),
            "note_type": note.get("note_type", ""),
            "severity": note.get("severity", ""),
            "status": note.get("status", ""),
            "owner": note.get("owner", ""),
            "resolution_note": note.get("resolution_note", ""),
            "resolved_at": note.get("resolved_at", ""),
            "resolved_by": note.get("resolved_by", ""),
            "actor": note.get("actor") or {},
            "created_at": note.get("created_at", ""),
            "updated_at": note.get("updated_at", ""),
        }

    def _research_snapshot_index(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "snapshot_id": snapshot["snapshot_id"],
            "title": snapshot.get("title", ""),
            "reason": snapshot.get("reason", ""),
            "gate_type": snapshot.get("gate_type", ""),
            "actor": snapshot.get("actor") or {},
            "included_asset_kinds": snapshot.get("included_asset_kinds") or [],
            "asset_counts": {
                kind: summary.get("count", 0)
                for kind, summary in (snapshot.get("asset_kind_summaries") or {}).items()
            },
            "linked_governance_review": snapshot.get("linked_governance_review") or {},
            "linked_leadership_briefing": snapshot.get("linked_leadership_briefing") or {},
            "review_history_watermark": snapshot.get("review_history_watermark") or {},
            "snapshot_fingerprint": snapshot.get("snapshot_fingerprint", ""),
            "created_at": snapshot.get("created_at", ""),
        }

    def _fingerprint_payload(self, payload: dict[str, Any]) -> str:
        return _payload_hash(payload)

    def _diff_snapshot_captures(self, snapshot: dict[str, Any], current: dict[str, Any], *, compared_at: str) -> dict[str, Any]:
        baseline_assets = snapshot.get("asset_fingerprints") or {}
        current_assets = current.get("asset_fingerprints") or {}
        kinds = sorted(set(baseline_assets) | set(current_assets))
        asset_count_changes: dict[str, Any] = {}
        asset_id_changes: dict[str, Any] = {}
        asset_state_changes: dict[str, list[Any]] = {}
        assets_added = 0
        assets_removed = 0
        assets_changed = 0
        changed_kinds: set[str] = set()

        for kind in kinds:
            before_items = {item.get("asset_id"): item for item in baseline_assets.get(kind, []) if item.get("asset_id")}
            after_items = {item.get("asset_id"): item for item in current_assets.get(kind, []) if item.get("asset_id")}
            before_ids = set(before_items)
            after_ids = set(after_items)
            added = sorted(after_ids - before_ids)
            removed = sorted(before_ids - after_ids)
            if added or removed:
                asset_id_changes[kind] = {"added": added, "removed": removed}
                assets_added += len(added)
                assets_removed += len(removed)
                changed_kinds.add(kind)
            if len(before_ids) != len(after_ids):
                asset_count_changes[kind] = {
                    "from": len(before_ids),
                    "to": len(after_ids),
                    "delta": len(after_ids) - len(before_ids),
                }
                changed_kinds.add(kind)

            changed_rows: list[dict[str, Any]] = []
            for asset_id in sorted(before_ids & after_ids):
                before = before_items[asset_id]
                after = after_items[asset_id]
                if before.get("fingerprint") == after.get("fingerprint"):
                    continue
                fields = {}
                for field in ("title", "status", "readiness", "gate_decision", "approval_state", "review_state", "decision_status", "source_ref_count"):
                    if before.get(field) != after.get(field):
                        fields[field] = {"from": before.get(field), "to": after.get(field)}
                changed_rows.append({
                    "asset_id": asset_id,
                    "asset_type": after.get("asset_type") or before.get("asset_type", ""),
                    "title": after.get("title") or before.get("title", ""),
                    "changed_fields": fields,
                    "fingerprint_changed": True,
                })
            if changed_rows:
                asset_state_changes[kind] = changed_rows
                assets_changed += len(changed_rows)
                changed_kinds.add(kind)

        review_history_change = self._diff_review_history_watermark(
            snapshot.get("review_history_watermark") or {},
            current.get("review_history_watermark") or {},
        )
        governance_change = self._diff_governance_link(
            snapshot.get("linked_governance_review") or {},
            current.get("linked_governance_review") or {},
        )
        briefing_change = self._diff_leadership_briefing_link(
            snapshot.get("linked_leadership_briefing") or {},
            current.get("linked_leadership_briefing") or {},
        )
        if review_history_change.get("changed"):
            changed_kinds.add("review_history")
        if governance_change.get("changed"):
            changed_kinds.add("governance_reviews")
        if briefing_change.get("changed"):
            changed_kinds.add("leadership_briefings")

        return {
            "project_id": snapshot.get("project_id", ""),
            "snapshot_id": snapshot.get("snapshot_id", ""),
            "snapshot_created_at": snapshot.get("created_at", ""),
            "compared_at": compared_at,
            "summary": {
                "has_changes": bool(changed_kinds),
                "asset_kinds_changed": len(changed_kinds),
                "assets_added": assets_added,
                "assets_removed": assets_removed,
                "assets_changed": assets_changed,
                "review_history_changed": review_history_change.get("changed", False),
                "governance_gate_decision_changed": governance_change.get("gate_decision_changed", False),
                "leadership_briefing_readiness_changed": briefing_change.get("readiness_changed", False),
            },
            "asset_count_changes": asset_count_changes,
            "asset_id_changes": asset_id_changes,
            "asset_state_changes": asset_state_changes,
            "review_history_change": review_history_change,
            "governance_change": governance_change,
            "leadership_briefing_change": briefing_change,
        }

    def _diff_review_history_watermark(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        return {
            "from_latest_entry_id": before.get("latest_entry_id", ""),
            "to_latest_entry_id": after.get("latest_entry_id", ""),
            "from_entry_count": before.get("entry_count", 0),
            "to_entry_count": after.get("entry_count", 0),
            "changed": before != after,
        }

    def _diff_governance_link(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        return {
            "from_gate_decision": before.get("gate_decision", ""),
            "to_gate_decision": after.get("gate_decision", ""),
            "from_readiness": before.get("readiness", ""),
            "to_readiness": after.get("readiness", ""),
            "gate_decision_changed": before.get("gate_decision", "") != after.get("gate_decision", ""),
            "readiness_changed": before.get("readiness", "") != after.get("readiness", ""),
            "changed": before != after,
        }

    def _diff_leadership_briefing_link(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        return {
            "from_readiness": before.get("readiness", ""),
            "to_readiness": after.get("readiness", ""),
            "from_status": before.get("status", ""),
            "to_status": after.get("status", ""),
            "readiness_changed": before.get("readiness", "") != after.get("readiness", ""),
            "status_changed": before.get("status", "") != after.get("status", ""),
            "changed": before != after,
        }

    def _validate_snapshot_review_note_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ResearchProjectStoreError("snapshot review note payload must be an object")
        forbidden = sorted(set(payload) & self.SNAPSHOT_REVIEW_NOTE_RUNTIME_FIELDS)
        if forbidden:
            raise ResearchProjectStoreError(f"unsupported runtime fields: {', '.join(forbidden)}")
        clean = dict(payload)
        self._require_text(clean, "note", "note_type", "severity")
        note_text = str(clean.get("note") or "").strip()
        if len(note_text) > 4000:
            raise ResearchProjectStoreError("note exceeds 4000 characters")
        target_ref = clean.get("target_ref") or {}
        if not isinstance(target_ref, dict):
            raise ResearchProjectStoreError("target_ref must be an object")
        forbidden_target = sorted(set(target_ref) & self.SNAPSHOT_REVIEW_NOTE_RUNTIME_FIELDS)
        if forbidden_target:
            raise ResearchProjectStoreError(f"unsupported runtime fields: {', '.join(forbidden_target)}")
        section_key = str(target_ref.get("section_key") or "").strip()
        self._validate_choice(section_key, "target_ref.section_key", self.SNAPSHOT_REVIEW_NOTE_SECTION_KEYS)
        note_type = str(clean.get("note_type") or "").strip()
        severity = str(clean.get("severity") or "").strip()
        self._validate_choice(note_type, "note_type", self.SNAPSHOT_REVIEW_NOTE_TYPES)
        self._validate_choice(severity, "severity", self.SNAPSHOT_REVIEW_NOTE_SEVERITIES)
        status = str(clean.get("status") or "open").strip()
        self._validate_choice(status, "status", self.SNAPSHOT_REVIEW_NOTE_STATUSES)
        if status != "open":
            raise ResearchProjectStoreError("status must be open when creating a snapshot review note")
        return {
            "note_id": str(clean.get("note_id") or "").strip(),
            "target_ref": {
                "section_key": section_key,
                "asset_kind": str(target_ref.get("asset_kind") or "").strip(),
                "asset_id": str(target_ref.get("asset_id") or "").strip(),
                "field": str(target_ref.get("field") or "").strip(),
            },
            "note_type": note_type,
            "severity": severity,
            "status": status,
            "note": note_text,
            "actor": clean.get("actor"),
        }

    def _validate_snapshot_review_note_update_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ResearchProjectStoreError("snapshot review note update payload must be an object")
        forbidden = sorted(set(payload) & self.SNAPSHOT_REVIEW_NOTE_RUNTIME_FIELDS)
        if forbidden:
            raise ResearchProjectStoreError(f"unsupported runtime fields: {', '.join(forbidden)}")
        unknown = sorted(set(payload) - self.SNAPSHOT_REVIEW_NOTE_UPDATE_FIELDS)
        if unknown:
            raise ResearchProjectStoreError(f"unsupported snapshot review note update fields: {', '.join(unknown)}")
        if "actor" not in payload:
            raise ResearchProjectStoreError("actor is required for snapshot review note disposition updates")
        actor = payload.get("actor")
        if isinstance(actor, str):
            actor = {"actor_type": "manual_user", "display_name": actor.strip()}
        if not isinstance(actor, dict):
            raise ResearchProjectStoreError("actor must be an object or string")
        actor_display = str(actor.get("display_name") or actor.get("actor_id") or "").strip()
        if not actor_display:
            raise ResearchProjectStoreError("actor must identify a manual reviewer")

        clean: dict[str, Any] = {
            "actor": {
                "actor_type": str(actor.get("actor_type") or "manual_user"),
                "actor_id": str(actor.get("actor_id") or ""),
                "display_name": actor_display,
            }
        }
        if "status" in payload:
            status = str(payload.get("status") or "").strip()
            self._validate_choice(status, "status", self.SNAPSHOT_REVIEW_NOTE_STATUSES)
            clean["status"] = status
        if "owner" in payload:
            owner = "" if payload.get("owner") is None else str(payload.get("owner")).strip()
            if len(owner) > 200:
                raise ResearchProjectStoreError("owner exceeds 200 characters")
            clean["owner"] = owner
        if "resolution_note" in payload:
            resolution_note = "" if payload.get("resolution_note") is None else str(payload.get("resolution_note")).strip()
            if len(resolution_note) > 4000:
                raise ResearchProjectStoreError("resolution_note exceeds 4000 characters")
            clean["resolution_note"] = resolution_note
        return clean

    def _require_text(self, payload: dict[str, Any], *fields: str) -> None:
        missing = [field for field in fields if not str(payload.get(field) or "").strip()]
        if missing:
            raise ResearchProjectStoreError(f"missing required fields: {', '.join(missing)}")

    def _validate_choice(self, value: Any, field: str, choices: set[str]) -> None:
        if value not in choices:
            raise ResearchProjectStoreError(f"{field} must be one of {sorted(choices)}")

    def _validate_string_list(self, payload: dict[str, Any], field: str) -> list[str]:
        value = payload.get(field) or []
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ResearchProjectStoreError(f"{field} must be an array of strings")
        payload[field] = value
        return value

    def _accepted_evidence_by_id(self, project: ResearchProject) -> dict[str, dict[str, Any]]:
        accepted: dict[str, dict[str, Any]] = {}
        for item in project.evidence_items or []:
            evidence_id = item.get("evidence_id")
            if not evidence_id:
                continue
            if item.get("status") == "accepted" or item.get("review_status") == "accepted":
                accepted[evidence_id] = item
        return accepted

    def _validate_evidence_refs(self, project: ResearchProject, *groups: list[str]) -> list[str]:
        accepted = self._accepted_evidence_by_id(project)
        warnings: list[str] = []
        for group in groups:
            if not isinstance(group, list) or any(not isinstance(item, str) for item in group):
                raise ResearchProjectStoreError("evidence references must be arrays of strings")
            missing = [evidence_id for evidence_id in group if evidence_id not in accepted]
            if missing:
                raise ResearchProjectStoreError(f"evidence references not accepted in project: {', '.join(missing)}")
            for evidence_id in group:
                evidence = accepted[evidence_id]
                if not evidence.get("origin") and not evidence.get("scope"):
                    warnings.append(f"{evidence_id}: accepted evidence has limited provenance")
        return sorted(set(warnings))

    def _validate_insight_refs(self, project_id: str, insight_ids: list[str]) -> None:
        if not isinstance(insight_ids, list) or any(not isinstance(item, str) for item in insight_ids):
            raise ResearchProjectStoreError("insight references must be an array of strings")
        existing = {item.get("id") for item in self._list_assets(project_id, "insight_cards", "ic")}
        missing = [item for item in insight_ids if item not in existing]
        if missing:
            raise ResearchProjectStoreError(f"insight references not found in project: {', '.join(missing)}")

    def _validate_matrix_refs(self, project_id: str, row_ids: list[str]) -> None:
        if not isinstance(row_ids, list) or any(not isinstance(item, str) for item in row_ids):
            raise ResearchProjectStoreError("matrix row references must be an array of strings")
        existing = {item.get("id") for item in self._list_assets(project_id, "evidence_matrix_rows", "emr")}
        missing = [item for item in row_ids if item not in existing]
        if missing:
            raise ResearchProjectStoreError(f"matrix row references not found in project: {', '.join(missing)}")

    def _validate_evidence_matrix_row(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._require_text(item, "question", "claim")
        self._validate_choice(item.get("claim_type"), "claim_type", {
            "strategic_claim",
            "risk",
            "assumption",
            "option",
            "decision_point",
        })
        self._validate_choice(item.get("confidence"), "confidence", {"low", "medium", "high"})
        self._validate_choice(item.get("material_readiness"), "material_readiness", {
            "raw",
            "usable",
            "presentation_ready",
            "insufficient",
        })
        self._validate_choice(item.get("status"), "status", {
            "draft",
            "reviewed",
            "accepted",
            "rejected",
            "superseded",
        })
        supporting = self._validate_string_list(item, "supporting_evidence_ids")
        counter = self._validate_string_list(item, "counter_evidence_ids")
        related = self._validate_string_list(item, "related_insight_ids")
        item["traceability_warnings"] = self._validate_evidence_refs(project, supporting, counter)
        self._validate_insight_refs(project.id, related)

    def _validate_insight_card(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._require_text(item, "title", "claim", "implication")
        self._validate_choice(item.get("confidence"), "confidence", {"low", "medium", "high"})
        self._validate_choice(item.get("status"), "status", {
            "draft",
            "reviewed",
            "accepted",
            "rejected",
            "superseded",
            "used_in_artifact",
        })
        supporting = self._validate_string_list(item, "supporting_evidence_ids")
        counter = self._validate_string_list(item, "counter_evidence_ids")
        matrix_rows = self._validate_string_list(item, "matrix_row_ids")
        self._validate_string_list(item, "tags")
        item["traceability_warnings"] = self._validate_evidence_refs(project, supporting, counter)
        self._validate_matrix_refs(project.id, matrix_rows)

    def _validate_artifact_draft(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._require_text(item, "artifact_type", "title", "purpose")
        self._validate_choice(item.get("artifact_type"), "artifact_type", {
            "memo_outline",
            "slide_outline",
            "qa_pack",
            "drawio_page_spec",
            "briefing_note",
            "decision_record",
        })
        self._validate_choice(item.get("status"), "status", {
            "draft",
            "reviewed",
            "accepted",
            "rejected",
            "superseded",
        })
        self._validate_choice(item.get("material_readiness"), "material_readiness", {
            "outline_only",
            "needs_review",
            "presentation_ready",
            "exported_outside_kfc",
        })
        source_insights = self._validate_string_list(item, "source_insight_ids")
        source_evidence = self._validate_string_list(item, "source_evidence_ids")
        outline = item.get("outline") or []
        if not isinstance(outline, list):
            raise ResearchProjectStoreError("outline must be an array")
        for section in outline:
            if not isinstance(section, dict):
                raise ResearchProjectStoreError("outline sections must be objects")
            if not str(section.get("section_id") or "").strip():
                raise ResearchProjectStoreError("outline section_id is required")
            if "source_insight_ids" in section:
                ids = section.get("source_insight_ids") or []
                if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
                    raise ResearchProjectStoreError("outline source_insight_ids must be an array of strings")
                self._validate_insight_refs(project.id, ids)
        item["outline"] = outline
        item["traceability_warnings"] = self._validate_evidence_refs(project, source_evidence)
        self._validate_insight_refs(project.id, source_insights)

    def _asset_ids(self, project_id: str, asset_kind: str, id_prefix: str, index_values: list[Any], id_field: str = "id") -> set[str]:
        ids = {item.get(id_field) for item in index_values or [] if isinstance(item, dict) and item.get(id_field)}
        ids.update(item.get(id_field) for item in self._list_assets(project_id, asset_kind, id_prefix) if item.get(id_field))
        return ids

    def _validate_asset_refs(
        self,
        project: ResearchProject,
        *,
        field: str,
        values: list[str],
        asset_kind: str,
        id_prefix: str,
        index_values: list[Any],
        id_field: str = "id",
    ) -> None:
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ResearchProjectStoreError(f"{field} must be an array of strings")
        existing = self._asset_ids(project.id, asset_kind, id_prefix, index_values, id_field=id_field)
        missing = [item for item in values if item not in existing]
        if missing:
            raise ResearchProjectStoreError(f"{field} references not found in project: {', '.join(missing)}")

    def _validate_artifact_draft_refs(self, project: ResearchProject, values: list[str], field: str) -> None:
        self._validate_asset_refs(
            project,
            field=field,
            values=values,
            asset_kind="artifact_drafts",
            id_prefix="ad",
            index_values=project.artifact_drafts,
            id_field="id",
        )

    def _validate_matrix_row_refs(self, project: ResearchProject, values: list[str], field: str) -> None:
        self._validate_asset_refs(
            project,
            field=field,
            values=values,
            asset_kind="evidence_matrix_rows",
            id_prefix="emr",
            index_values=project.evidence_matrix_rows,
            id_field="id",
        )

    def _validate_artifact_pack_refs(self, project: ResearchProject, values: list[str], field: str) -> None:
        self._validate_asset_refs(
            project,
            field=field,
            values=values,
            asset_kind="artifact_packs",
            id_prefix="ap",
            index_values=project.artifact_packs,
            id_field="pack_id",
        )

    def _validate_strategic_option_refs(self, project: ResearchProject, values: list[str], field: str) -> None:
        self._validate_asset_refs(
            project,
            field=field,
            values=values,
            asset_kind="strategic_options",
            id_prefix="so",
            index_values=project.strategic_options,
            id_field="option_id",
        )

    def _validate_validation_plan_refs(self, project: ResearchProject, values: list[str], field: str) -> None:
        self._validate_asset_refs(
            project,
            field=field,
            values=values,
            asset_kind="validation_plans",
            id_prefix="vp",
            index_values=project.validation_plans,
            id_field="plan_id",
        )

    def _validate_leadership_decision_refs(self, project: ResearchProject, values: list[str], field: str) -> None:
        self._validate_asset_refs(
            project,
            field=field,
            values=values,
            asset_kind="leadership_decision_records",
            id_prefix="ldr",
            index_values=project.leadership_decision_records,
            id_field="decision_id",
        )

    def _validate_no_runtime_fields(self, item: Any, path: str = "payload") -> None:
        forbidden = {
            "_".join(("model", "provider")),
            "_".join(("model", "runner")),
            "_".join(("llm", "client")),
            "".join(("cr", "on")),
            "schedule",
            "worker_id",
            "queue",
            "dag",
            "".join(("sub", "process")),
        }
        if isinstance(item, dict):
            found = sorted(key for key in item if str(key).lower() in forbidden)
            if found:
                raise ResearchProjectStoreError(f"{path} contains runtime execution fields: {', '.join(found)}")
            for key, value in item.items():
                self._validate_no_runtime_fields(value, f"{path}.{key}")
        elif isinstance(item, list):
            for idx, value in enumerate(item):
                self._validate_no_runtime_fields(value, f"{path}[{idx}]")

    def _validate_strategic_option(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._validate_no_runtime_fields(item)
        self._require_text(item, "title")
        self._validate_choice(item.get("option_type"), "option_type", {
            "strategic_path",
            "investment_priority",
            "pilot_path",
            "platform_positioning",
            "watch_option",
        })
        self._validate_choice(item.get("status"), "status", {
            "draft",
            "under_review",
            "validated",
            "rejected",
            "superseded",
            "accepted_for_planning",
        })
        self._validate_choice(item.get("recommendation_level"), "recommendation_level", {
            "recommended",
            "alternative",
            "watch",
            "not_recommended",
        })
        self._validate_choice(item.get("decision_posture"), "decision_posture", {
            "lean_yes",
            "lean_no",
            "need_validation",
            "split_decision",
            "undecided",
        })
        self._validate_choice(item.get("review_state"), "review_state", {
            "not_reviewed",
            "ready_for_review",
            "reviewed",
            "needs_revision",
        })
        source_insights = self._validate_string_list(item, "source_insight_ids")
        source_rows = self._validate_string_list(item, "source_evidence_matrix_row_ids")
        source_evidence = self._validate_string_list(item, "source_evidence_ids")
        source_drafts = self._validate_string_list(item, "source_artifact_draft_ids")
        source_packs = self._validate_string_list(item, "source_artifact_pack_ids")
        self._validate_insight_refs(project.id, source_insights)
        self._validate_matrix_row_refs(project, source_rows, "source_evidence_matrix_row_ids")
        item["traceability_warnings"] = self._validate_evidence_refs(project, source_evidence)
        self._validate_artifact_draft_refs(project, source_drafts, "source_artifact_draft_ids")
        self._validate_artifact_pack_refs(project, source_packs, "source_artifact_pack_ids")
        for field in ("assumptions", "expected_benefits", "risks", "tradeoffs", "success_metrics", "decision_log"):
            if not isinstance(item.get(field) or [], list):
                raise ResearchProjectStoreError(f"{field} must be an array")
        if item.get("status") in {"validated", "accepted_for_planning"} and not (
            source_insights or source_rows or source_evidence
        ):
            raise ResearchProjectStoreError("validated strategic options require traceability to insight, matrix row, or evidence")

    def _validate_validation_plan(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._validate_no_runtime_fields(item)
        self._require_text(item, "title")
        self._validate_choice(item.get("status"), "status", {
            "draft",
            "under_review",
            "approved",
            "in_external_execution",
            "completed",
            "cancelled",
        })
        self._validate_choice(item.get("plan_type"), "plan_type", {
            "pilot_validation",
            "customer_interview",
            "desk_research",
            "prototype_test",
            "competitive_benchmark",
            "internal_review",
        })
        self._validate_choice(item.get("review_state"), "review_state", {
            "not_reviewed",
            "ready_for_review",
            "reviewed",
            "needs_revision",
        })
        self._validate_choice(item.get("approval_state"), "approval_state", {
            "draft",
            "ready_for_review",
            "approved",
            "blocked",
        })
        linked_options = self._validate_string_list(item, "linked_option_ids")
        source_insights = self._validate_string_list(item, "source_insight_ids")
        source_evidence = self._validate_string_list(item, "source_evidence_ids")
        source_packs = self._validate_string_list(item, "source_artifact_pack_ids")
        self._validate_strategic_option_refs(project, linked_options, "linked_option_ids")
        self._validate_insight_refs(project.id, source_insights)
        item["traceability_warnings"] = self._validate_evidence_refs(project, source_evidence)
        self._validate_artifact_pack_refs(project, source_packs, "source_artifact_pack_ids")
        for field in (
            "validation_questions",
            "validation_methods",
            "milestones",
            "metrics",
            "risks_to_validate",
            "evidence_capture_plan",
            "decision_log",
        ):
            if not isinstance(item.get(field) or [], list):
                raise ResearchProjectStoreError(f"{field} must be an array")
        for method in item.get("validation_methods") or []:
            if not isinstance(method, dict):
                raise ResearchProjectStoreError("validation_methods must contain objects")
            execution_location = method.get("execution_location", "external")
            self._validate_choice(execution_location, "execution_location", {"external", "manual", "codex_external"})
            method["execution_location"] = execution_location
        if item.get("status") == "approved":
            if not linked_options:
                raise ResearchProjectStoreError("approved validation plans require linked_option_ids")
            if not item.get("validation_questions"):
                raise ResearchProjectStoreError("approved validation plans require validation_questions")
            if not item.get("validation_methods"):
                raise ResearchProjectStoreError("approved validation plans require validation_methods")
            if not (item.get("metrics") or item.get("milestones")):
                raise ResearchProjectStoreError("approved validation plans require metrics or milestones")

    def _validate_leadership_decision_record(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._validate_no_runtime_fields(item)
        self._require_text(item, "title")
        self._validate_choice(item.get("decision_status"), "decision_status", {
            "proposed",
            "needs_revision",
            "approved",
            "rejected",
            "deferred",
            "superseded",
        })
        self._validate_choice(item.get("decision_type"), "decision_type", {
            "strategic_direction",
            "investment_priority",
            "pilot_approval",
            "material_approval",
            "scope_cut",
        })
        linked_options = self._validate_string_list(item, "linked_option_ids")
        linked_plans = self._validate_string_list(item, "linked_validation_plan_ids")
        source_insights = self._validate_string_list(item, "source_insight_ids")
        source_packs = self._validate_string_list(item, "source_artifact_pack_ids")
        rejected = self._validate_string_list(item, "rejected_option_ids")
        deferred = self._validate_string_list(item, "deferred_option_ids")
        self._validate_strategic_option_refs(project, linked_options, "linked_option_ids")
        self._validate_validation_plan_refs(project, linked_plans, "linked_validation_plan_ids")
        self._validate_insight_refs(project.id, source_insights)
        self._validate_artifact_pack_refs(project, source_packs, "source_artifact_pack_ids")
        chosen = str(item.get("chosen_option_id") or "").strip()
        if chosen and chosen not in linked_options:
            raise ResearchProjectStoreError("chosen_option_id must be included in linked_option_ids")
        for field, values in (("rejected_option_ids", rejected), ("deferred_option_ids", deferred)):
            missing = [value for value in values if value not in linked_options]
            if missing:
                raise ResearchProjectStoreError(f"{field} must be a subset of linked_option_ids")
        for field in ("rationale", "conditions", "open_questions", "next_actions", "review_rounds", "decision_log"):
            if not isinstance(item.get(field) or [], list):
                raise ResearchProjectStoreError(f"{field} must be an array")
        if item.get("decision_status") == "approved":
            if not chosen:
                raise ResearchProjectStoreError("approved leadership decisions require chosen_option_id")
            if not item.get("rationale"):
                raise ResearchProjectStoreError("approved leadership decisions require rationale")
            if self._has_unresolved_blocking_leadership_review(item):
                raise ResearchProjectStoreError("leadership decision cannot be approved with unresolved blocking review rounds")

    def _validate_source_ref(self, project: ResearchProject, ref: dict[str, Any], field: str) -> None:
        self._require_text(ref, "asset_type", "asset_id")
        asset_type = ref["asset_type"]
        asset_id = ref["asset_id"]
        self._validate_choice(asset_type, "asset_type", {
            "evidence_item",
            "evidence_matrix_row",
            "insight_card",
            "artifact_draft",
            "artifact_pack",
            "strategic_option",
            "validation_plan",
            "leadership_decision_record",
            "leadership_briefing",
            "governance_review",
            "consultation_log",
            "external_research_pack",
            "research_run",
        })
        if asset_type == "evidence_item":
            self._validate_evidence_refs(project, [asset_id])
        elif asset_type == "evidence_matrix_row":
            self._validate_matrix_row_refs(project, [asset_id], field)
        elif asset_type == "insight_card":
            self._validate_insight_refs(project.id, [asset_id])
        elif asset_type == "artifact_draft":
            self._validate_artifact_draft_refs(project, [asset_id], field)
        elif asset_type == "artifact_pack":
            self._validate_artifact_pack_refs(project, [asset_id], field)
        elif asset_type == "strategic_option":
            self._validate_strategic_option_refs(project, [asset_id], field)
        elif asset_type == "validation_plan":
            self._validate_validation_plan_refs(project, [asset_id], field)
        elif asset_type == "leadership_decision_record":
            self._validate_leadership_decision_refs(project, [asset_id], field)
        elif asset_type == "leadership_briefing":
            self._validate_asset_refs(
                project,
                field=field,
                values=[asset_id],
                asset_kind="leadership_briefings",
                id_prefix="lb",
                index_values=project.leadership_briefings,
                id_field="briefing_id",
            )
        elif asset_type == "governance_review":
            self._validate_asset_refs(
                project,
                field=field,
                values=[asset_id],
                asset_kind="governance_reviews",
                id_prefix="gr",
                index_values=project.governance_reviews,
                id_field="review_id",
            )
        elif asset_type == "consultation_log":
            self._validate_asset_refs(
                project,
                field=field,
                values=[asset_id],
                asset_kind="consultation_logs",
                id_prefix="cl",
                index_values=project.consultation_logs,
                id_field="consultation_id",
            )
        elif asset_type == "external_research_pack":
            self._validate_asset_refs(
                project,
                field=field,
                values=[asset_id],
                asset_kind="external_research_packs",
                id_prefix="erp",
                index_values=project.external_research_packs,
                id_field="pack_id",
            )
        elif asset_type == "research_run":
            self._validate_asset_refs(
                project,
                field=field,
                values=[asset_id],
                asset_kind="research_runs",
                id_prefix="rr",
                index_values=project.research_runs,
                id_field="run_id",
            )

    def _validate_source_refs(self, project: ResearchProject, refs: list[Any], field: str) -> None:
        if not isinstance(refs, list):
            raise ResearchProjectStoreError(f"{field} must be an array")
        seen: set[tuple[str, str]] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                raise ResearchProjectStoreError(f"{field} must contain objects")
            self._validate_source_ref(project, ref, field)
            key = (ref["asset_type"], ref["asset_id"])
            if key in seen:
                raise ResearchProjectStoreError(f"{field} contains duplicate source references")
            seen.add(key)
            ref.setdefault("required", False)

    def _seed_governance_review_from_traceability(self, project: ResearchProject, item: dict[str, Any]) -> None:
        from ..services.research_traceability_map import build_traceability_map

        traceability = build_traceability_map(project.id, store=self)
        if traceability is None:
            raise ResearchProjectStoreError(f"research project not found: {project.id}")
        summary = traceability.get("summary") or {}
        issues = traceability.get("issues") or []
        item["traceability_map_version"] = {
            "computed_at": traceability.get("generated_at", ""),
            "readiness": traceability.get("traceability_readiness", ""),
            "node_count": summary.get("node_count", 0),
            "edge_count": summary.get("edge_count", 0),
            "missing_reference_count": summary.get("missing_reference_count", 0),
            "weak_support_count": sum(
                1 for issue in issues
                if issue.get("issue_type") in {"unsupported_insight", "unsupported_option", "unsupported_artifact_draft"}
            ),
            "orphan_node_count": summary.get("orphan_node_count", 0),
            "unsupported_asset_count": sum(
                1 for issue in issues
                if str(issue.get("issue_type") or "").startswith("unsupported")
            ),
        }
        existing_check_ids = {entry.get("item_id") for entry in item.get("checklist_items") or []}
        checklist_specs = [
            ("chk_traceability_exists", "traceability", "Traceability map is computable", True, summary.get("node_count", 0) >= 0),
            ("chk_chain_reviewable", "traceability", "Evidence to briefing chain is reviewable", True, summary.get("edge_count", 0) > 0),
            ("chk_no_missing_refs", "traceability", "No unresolved missing references", True, summary.get("missing_reference_count", 0) == 0),
            ("chk_weak_support_reviewed", "support", "Weak support findings reviewed", True, summary.get("warning_issue_count", 0) == 0),
            ("chk_orphans_reviewed", "coverage", "Orphan assets reviewed", False, summary.get("orphan_node_count", 0) == 0),
            ("chk_manual_signoff", "signoff", "Manual sign-off completed", True, False),
        ]
        seeded_checklist = []
        for item_id, category, label, required, passes in checklist_specs:
            if item_id in existing_check_ids:
                continue
            seeded_checklist.append({
                "item_id": item_id,
                "category": category,
                "label": label,
                "required": required,
                "status": "pass" if passes else "fail",
                "severity": "major" if required else "minor",
                "notes": "",
                "source": "system_seeded",
            })
        item["checklist_items"] = seeded_checklist + list(item.get("checklist_items") or [])
        findings = list(item.get("findings") or [])
        for issue in issues:
            findings.append({
                "finding_id": _new_prefixed_id("gf"),
                "finding_type": issue.get("issue_type", "manual"),
                "severity": self._finding_severity_from_issue(issue.get("severity")),
                "status": "open",
                "asset_ref": {
                    "asset_type": issue.get("asset_type", ""),
                    "asset_id": issue.get("asset_id", ""),
                },
                "description": issue.get("message", ""),
                "recommended_action": "Review and either resolve outside KFC or document a waiver/risk disposition.",
                "disposition": "",
                "owner": "",
                "due_note": "",
                "source": "traceability_map",
            })
        for orphan in traceability.get("orphans") or []:
            node_id = str(orphan.get("node_id") or "")
            if ":" not in node_id:
                continue
            asset_type, asset_id = node_id.split(":", 1)
            findings.append({
                "finding_id": _new_prefixed_id("gf"),
                "finding_type": "orphan_node",
                "severity": "minor",
                "status": "open",
                "asset_ref": {"asset_type": asset_type, "asset_id": asset_id},
                "description": orphan.get("reason", "Asset is not connected by explicit traceability edges."),
                "recommended_action": "Review whether this asset should be linked, waived, or left as accepted risk.",
                "disposition": "",
                "owner": "",
                "due_note": "",
                "source": "traceability_map",
            })
        item["findings"] = findings

    def _finding_severity_from_issue(self, severity: Any) -> str:
        if severity == "blocking":
            return "blocker"
        if severity == "warning":
            return "major"
        return "minor"

    def _normalize_governance_review(self, item: dict[str, Any]) -> None:
        for field in ("checklist_items", "findings", "risk_dispositions", "signoffs"):
            if not isinstance(item.get(field) or [], list):
                raise ResearchProjectStoreError(f"{field} must be an array")
        for entry in item.get("checklist_items") or []:
            entry.setdefault("item_id", _new_prefixed_id("chk"))
            entry.setdefault("category", "manual")
            entry.setdefault("required", False)
            entry.setdefault("status", "open")
            entry.setdefault("severity", "minor")
            entry.setdefault("notes", "")
            entry.setdefault("source", "manual")
        for entry in item.get("findings") or []:
            entry.setdefault("finding_id", _new_prefixed_id("gf"))
            entry.setdefault("finding_type", "manual")
            entry.setdefault("severity", "minor")
            entry.setdefault("status", "open")
            entry.setdefault("asset_ref", {})
            entry.setdefault("description", "")
            entry.setdefault("recommended_action", "")
            entry.setdefault("disposition", "")
            entry.setdefault("owner", "")
            entry.setdefault("due_note", "")
            entry.setdefault("source", "manual")
        for entry in item.get("risk_dispositions") or []:
            entry.setdefault("risk_id", _new_prefixed_id("risk"))
            entry.setdefault("related_finding_ids", [])
            entry.setdefault("risk_level", "medium")
            entry.setdefault("decision", "accept")
            entry.setdefault("rationale", "")
            entry.setdefault("approver", "")
            entry.setdefault("updated_at", _now_iso())
        for entry in item.get("signoffs") or []:
            entry.setdefault("signoff_id", _new_prefixed_id("sig"))
            entry.setdefault("role", "reviewer")
            entry.setdefault("name", "")
            entry.setdefault("decision", "not_reviewed")
            entry.setdefault("comment", "")
            entry.setdefault("signed_at", "")
        item["review_summary"] = self._build_governance_review_summary(item)

    def _build_governance_review_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        closed = {"accepted_risk", "resolved_externally", "waived"}
        findings = item.get("findings") or []
        open_blockers = [
            entry for entry in findings
            if entry.get("severity") == "blocker" and entry.get("status") not in closed
        ]
        open_majors = [
            entry for entry in findings
            if entry.get("severity") == "major" and entry.get("status") not in closed
        ]
        accepted_risks = [entry for entry in findings if entry.get("status") == "accepted_risk"]
        failed_required = [
            entry for entry in item.get("checklist_items") or []
            if entry.get("required") is True and entry.get("status") not in {"pass", "waived"}
        ]
        signoffs = item.get("signoffs") or []
        approved = any(entry.get("decision") in {"approved", "approved_with_risks"} for entry in signoffs)
        rejected = any(entry.get("decision") == "rejected" for entry in signoffs)
        overall = "ready" if not open_blockers and not open_majors and not failed_required and approved and not rejected else "partial"
        if open_blockers or failed_required or rejected:
            overall = "not_ready"
        return {
            "overall_readiness": overall,
            "blocker_count": len(open_blockers),
            "major_open_count": len(open_majors),
            "accepted_risk_count": len(accepted_risks),
            "failed_required_count": len(failed_required),
            "approved_signoff_count": sum(1 for entry in signoffs if entry.get("decision") in {"approved", "approved_with_risks"}),
            "ready_for_next_stage": overall == "ready",
            "summary_note": (item.get("review_summary") or {}).get("summary_note", ""),
        }

    def _validate_governance_review(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._validate_no_runtime_fields(item)
        self._require_text(item, "title", "review_type")
        self._validate_choice(item.get("review_type"), "review_type", {"stage_gate", "readiness_review", "leadership_review"})
        self._validate_choice(item.get("status"), "status", {"draft", "in_review", "signed_off", "rejected"})
        self._validate_choice(item.get("gate_decision"), "gate_decision", {"not_decided", "ready", "ready_with_risks", "blocked"})
        self._validate_choice(item.get("readiness"), "readiness", {"not_ready", "partial", "ready"})
        if not isinstance(item.get("traceability_map_version") or {}, dict):
            raise ResearchProjectStoreError("traceability_map_version must be an object")
        checklist_ids: set[str] = set()
        for entry in item.get("checklist_items") or []:
            self._require_text(entry, "item_id", "category", "label", "status", "severity", "source")
            self._validate_choice(entry.get("status"), "checklist status", {"open", "pass", "fail", "waived"})
            self._validate_choice(entry.get("severity"), "checklist severity", {"info", "minor", "major", "blocker"})
            self._validate_choice(entry.get("source"), "checklist source", {"system_seeded", "manual"})
            if entry["item_id"] in checklist_ids:
                raise ResearchProjectStoreError("checklist item_id values must be unique")
            checklist_ids.add(entry["item_id"])
        finding_ids: set[str] = set()
        for entry in item.get("findings") or []:
            self._require_text(entry, "finding_id", "finding_type", "severity", "status", "description", "source")
            self._validate_choice(entry.get("severity"), "finding severity", {"minor", "major", "blocker"})
            self._validate_choice(entry.get("status"), "finding status", {"open", "triaged", "accepted_risk", "resolved_externally", "waived"})
            self._validate_choice(entry.get("source"), "finding source", {"traceability_map", "manual"})
            if entry["finding_id"] in finding_ids:
                raise ResearchProjectStoreError("finding_id values must be unique")
            finding_ids.add(entry["finding_id"])
            ref = entry.get("asset_ref") or {}
            if ref.get("asset_type") or ref.get("asset_id"):
                self._validate_source_ref(project, ref, "findings.asset_ref")
        for entry in item.get("risk_dispositions") or []:
            self._require_text(entry, "risk_id", "risk_level", "decision")
            self._validate_choice(entry.get("risk_level"), "risk_level", {"low", "medium", "high", "critical"})
            self._validate_choice(entry.get("decision"), "risk decision", {"accept", "mitigate_before_next_stage", "block_release", "defer"})
            related = self._validate_string_list(entry, "related_finding_ids")
            missing = [finding_id for finding_id in related if finding_id not in finding_ids]
            if missing:
                raise ResearchProjectStoreError(f"related_finding_ids references not found: {', '.join(missing)}")
        for entry in item.get("signoffs") or []:
            self._require_text(entry, "signoff_id", "role", "decision")
            self._validate_choice(entry.get("decision"), "signoff decision", {"approved", "approved_with_risks", "rejected", "not_reviewed"})
        summary = item.get("review_summary") or {}
        if item.get("gate_decision") == "ready":
            if summary.get("blocker_count") or summary.get("major_open_count") or summary.get("failed_required_count"):
                raise ResearchProjectStoreError("ready governance reviews require all blockers, major findings, and required checklist failures resolved")
            if not summary.get("approved_signoff_count"):
                raise ResearchProjectStoreError("ready governance reviews require an approved signoff")
        if item.get("gate_decision") == "ready_with_risks":
            if summary.get("blocker_count") or summary.get("failed_required_count"):
                raise ResearchProjectStoreError("ready_with_risks governance reviews cannot have open blockers or failed required checklist items")
            if not str(summary.get("summary_note") or "").strip():
                raise ResearchProjectStoreError("ready_with_risks governance reviews require review_summary.summary_note")
            if not summary.get("approved_signoff_count"):
                raise ResearchProjectStoreError("ready_with_risks governance reviews require an approved signoff")

    def _normalize_leadership_briefing(self, item: dict[str, Any]) -> None:
        now = _now_iso()
        sections = item.get("sections") or []
        if not isinstance(sections, list):
            raise ResearchProjectStoreError("sections must be an array")
        normalized_sections = []
        used_section_ids: set[str] = set()
        for index, raw in enumerate(sections, start=1):
            if not isinstance(raw, dict):
                raise ResearchProjectStoreError("sections must contain objects")
            section = dict(raw)
            section.setdefault("section_id", _new_prefixed_id("lbs"))
            section.setdefault("order", index)
            section.setdefault("section_type", "context")
            section.setdefault("talking_points", [])
            section.setdefault("source_refs", [])
            section.setdefault("open_issues", [])
            section.setdefault("review_state", "draft")
            if section["section_id"] in used_section_ids:
                raise ResearchProjectStoreError("section_id values must be unique")
            used_section_ids.add(section["section_id"])
            normalized_sections.append(section)
        item["sections"] = normalized_sections

        asks = item.get("decision_asks") or []
        if not isinstance(asks, list):
            raise ResearchProjectStoreError("decision_asks must be an array")
        normalized_asks = []
        used_ask_ids: set[str] = set()
        for raw in asks:
            if not isinstance(raw, dict):
                raise ResearchProjectStoreError("decision_asks must contain objects")
            ask = dict(raw)
            ask.setdefault("ask_id", _new_prefixed_id("ask"))
            ask.setdefault("linked_option_ids", [])
            ask.setdefault("linked_validation_plan_ids", [])
            ask.setdefault("linked_decision_record_ids", [])
            ask.setdefault("status", "open")
            if ask["ask_id"] in used_ask_ids:
                raise ResearchProjectStoreError("ask_id values must be unique")
            used_ask_ids.add(ask["ask_id"])
            normalized_asks.append(ask)
        item["decision_asks"] = normalized_asks

        reviews = item.get("review_rounds") or []
        if not isinstance(reviews, list):
            raise ResearchProjectStoreError("review_rounds must be an array")
        normalized_reviews = []
        used_review_ids: set[str] = set()
        for raw in reviews:
            if not isinstance(raw, dict):
                raise ResearchProjectStoreError("review_rounds must contain objects")
            review = dict(raw)
            review.setdefault("round_id", _new_prefixed_id("lbr"))
            review.setdefault("decision", "comment")
            review.setdefault("blocking", False)
            review.setdefault("resolved", False)
            review.setdefault("created_at", now)
            review.setdefault("updated_at", now)
            if review["round_id"] in used_review_ids:
                raise ResearchProjectStoreError("round_id values must be unique")
            used_review_ids.add(review["round_id"])
            normalized_reviews.append(review)
        item["review_rounds"] = normalized_reviews

    def _validate_leadership_briefing(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._validate_no_runtime_fields(item)
        self._require_text(item, "title", "briefing_type", "audience", "purpose")
        self._validate_choice(item.get("briefing_type"), "briefing_type", {
            "strategic_readout",
            "decision_briefing",
            "validation_readout",
            "executive_update",
            "board_style_briefing",
        })
        self._validate_choice(item.get("status"), "status", {"draft", "in_review", "approved", "archived"})
        self._validate_choice(item.get("readiness"), "readiness", {"not_ready", "needs_review", "ready", "approved"})
        if not isinstance(item.get("version"), int) or item.get("version") < 1:
            raise ResearchProjectStoreError("version must be a positive integer")
        if not isinstance(item.get("executive_summary") or {}, dict):
            raise ResearchProjectStoreError("executive_summary must be an object")
        self._validate_source_refs(project, item.get("source_asset_refs") or [], "source_asset_refs")
        orders: set[int] = set()
        for section in item.get("sections") or []:
            self._require_text(section, "section_id", "title", "section_type")
            if not isinstance(section.get("order"), int) or section.get("order") < 1:
                raise ResearchProjectStoreError("section order must be a positive integer")
            if section["order"] in orders:
                raise ResearchProjectStoreError("section order values must be unique")
            orders.add(section["order"])
            self._validate_choice(section.get("section_type"), "section_type", {
                "context",
                "problem",
                "evidence",
                "insight",
                "option",
                "recommendation",
                "validation_plan",
                "decision_ask",
                "risk",
                "next_steps",
                "appendix",
            })
            self._validate_choice(section.get("review_state"), "review_state", {
                "draft",
                "needs_review",
                "approved",
                "blocked",
            })
            if not isinstance(section.get("talking_points") or [], list):
                raise ResearchProjectStoreError("section talking_points must be an array")
            if not isinstance(section.get("open_issues") or [], list):
                raise ResearchProjectStoreError("section open_issues must be an array")
            self._validate_source_refs(project, section.get("source_refs") or [], "sections.source_refs")
        for ask in item.get("decision_asks") or []:
            self._require_text(ask, "ask_id", "title")
            self._validate_choice(ask.get("status"), "decision ask status", {
                "open",
                "answered",
                "deferred",
                "withdrawn",
            })
            option_ids = self._validate_string_list(ask, "linked_option_ids")
            plan_ids = self._validate_string_list(ask, "linked_validation_plan_ids")
            decision_ids = self._validate_string_list(ask, "linked_decision_record_ids")
            self._validate_strategic_option_refs(project, option_ids, "linked_option_ids")
            self._validate_validation_plan_refs(project, plan_ids, "linked_validation_plan_ids")
            self._validate_leadership_decision_refs(project, decision_ids, "linked_decision_record_ids")
        for review in item.get("review_rounds") or []:
            self._require_text(review, "round_id", "reviewer", "decision")
            self._validate_choice(review.get("decision"), "review decision", {
                "approved",
                "changes_requested",
                "rejected",
                "comment",
            })
        item["readiness_checks"] = self._build_leadership_briefing_readiness_checks(item)
        if item.get("readiness") in {"ready", "approved"} or item.get("status") == "approved":
            checks = item["readiness_checks"]
            if not checks["has_executive_summary"]:
                raise ResearchProjectStoreError("ready leadership briefings require executive_summary")
            if not item.get("sections"):
                raise ResearchProjectStoreError("ready leadership briefings require sections")
            if not checks["all_required_sources_resolved"]:
                raise ResearchProjectStoreError("ready leadership briefings require resolved required sources")
            if checks["has_unresolved_section_issues"]:
                raise ResearchProjectStoreError("ready leadership briefings cannot have blocked sections")
            summary = item.get("executive_summary") or {}
            if summary.get("decision_required") is not False and not item.get("decision_asks"):
                raise ResearchProjectStoreError("ready leadership briefings require decision_asks unless decision_required is false")
        if item.get("readiness") == "approved" or item.get("status") == "approved":
            if self._has_unresolved_blocking_briefing_review(item):
                raise ResearchProjectStoreError("leadership briefing cannot be approved with unresolved blocking review rounds")


    def _validate_artifact_pack(self, project: ResearchProject, item: dict[str, Any]) -> None:
        self._require_text(item, "title", "pack_type", "purpose")
        self._validate_choice(item.get("pack_type"), "pack_type", {
            "leadership_deck",
            "strategy_memo",
            "qa_package",
            "drawio_spec_pack",
            "mixed_material_pack",
            "decision_package",
        })
        self._validate_choice(item.get("status"), "status", {
            "draft",
            "in_review",
            "needs_revision",
            "approved",
            "archived",
        })
        self._validate_choice(item.get("readiness"), "readiness", {
            "idea",
            "outline_ready",
            "source_mapped",
            "file_refs_added",
            "review_ready",
            "approved_for_export",
            "delivered",
        })
        source_drafts = self._validate_string_list(item, "source_artifact_draft_ids")
        source_insights = self._validate_string_list(item, "source_insight_ids")
        source_evidence = self._validate_string_list(item, "source_evidence_ids")
        self._validate_artifact_draft_refs(project, source_drafts, "source_artifact_draft_ids")
        self._validate_insight_refs(project.id, source_insights)
        item["traceability_warnings"] = self._validate_evidence_refs(project, source_evidence)
        for field in ("items", "pages", "file_refs", "review_rounds", "decision_log"):
            if not isinstance(item.get(field) or [], list):
                raise ResearchProjectStoreError(f"{field} must be an array")
        if item.get("status") == "approved" and self._has_unresolved_blocking_decision(item):
            raise ResearchProjectStoreError("artifact pack cannot be approved with unresolved blocking review decisions")

    def _validate_artifact_pack_item(self, project: ResearchProject, pack: dict[str, Any], item: dict[str, Any]) -> None:
        item.setdefault("role_in_pack", "main_deck")
        item.setdefault("sequence", len(pack.get("items") or []) + 1)
        item.setdefault("status", "included")
        self._require_text(item, "artifact_draft_id", "title", "role_in_pack")
        self._validate_artifact_draft_refs(project, [item["artifact_draft_id"]], "artifact_draft_id")
        self._validate_choice(item.get("role_in_pack"), "role_in_pack", {
            "main_deck",
            "backup",
            "appendix",
            "qa_support",
            "drawio_source",
            "memo_source",
            "decision_record",
        })
        self._validate_choice(item.get("status"), "status", {"included", "removed"})
        if not isinstance(item.get("sequence"), int):
            raise ResearchProjectStoreError("sequence must be an integer")

    def _validate_artifact_pack_page(self, project: ResearchProject, pack: dict[str, Any], item: dict[str, Any]) -> None:
        item.setdefault("sequence", len(pack.get("pages") or []) + 1)
        item.setdefault("page_type", "argument")
        item.setdefault("key_messages", [])
        item.setdefault("source_insight_ids", [])
        item.setdefault("source_evidence_ids", [])
        item.setdefault("source_matrix_row_ids", [])
        item.setdefault("visual_intent", {})
        item.setdefault("material_status", "planned")
        item.setdefault("review_status", "unreviewed")
        self._require_text(item, "page_title", "page_claim")
        self._validate_choice(item.get("page_type"), "page_type", {
            "title",
            "argument",
            "framework",
            "case",
            "evidence",
            "option",
            "roadmap",
            "qa",
            "appendix",
        })
        self._validate_choice(item.get("material_status"), "material_status", {
            "planned",
            "outlined",
            "externally_generated",
            "file_linked",
            "screenshot_linked",
            "ready_for_review",
            "approved",
        })
        self._validate_choice(item.get("review_status"), "review_status", {
            "unreviewed",
            "accepted",
            "needs_revision",
            "rejected",
        })
        if not isinstance(item.get("sequence"), int):
            raise ResearchProjectStoreError("sequence must be an integer")
        key_messages = self._validate_string_list(item, "key_messages")
        if len(key_messages) > 12:
            raise ResearchProjectStoreError("key_messages is too large")
        if item.get("source_artifact_draft_id"):
            self._validate_artifact_draft_refs(project, [item["source_artifact_draft_id"]], "source_artifact_draft_id")
        insight_ids = self._validate_string_list(item, "source_insight_ids")
        evidence_ids = self._validate_string_list(item, "source_evidence_ids")
        matrix_ids = self._validate_string_list(item, "source_matrix_row_ids")
        self._validate_insight_refs(project.id, insight_ids)
        item["traceability_warnings"] = self._validate_evidence_refs(project, evidence_ids)
        self._validate_matrix_row_refs(project, matrix_ids, "source_matrix_row_ids")
        if not isinstance(item.get("visual_intent") or {}, dict):
            raise ResearchProjectStoreError("visual_intent must be an object")

    def _validate_artifact_pack_file_ref(self, project: ResearchProject, pack: dict[str, Any], item: dict[str, Any]) -> None:
        item.setdefault("linked_page_ids", [])
        item.setdefault("linked_artifact_draft_ids", [])
        self._require_text(item, "file_kind", "title")
        self._validate_choice(item.get("file_kind"), "file_kind", {
            "pptx",
            "pdf",
            "drawio",
            "png",
            "jpg",
            "md",
            "docx",
            "xlsx",
            "other",
        })
        relative_path = str(item.get("relative_path") or "")
        external_uri = str(item.get("external_uri") or "")
        if not relative_path and not external_uri:
            raise ResearchProjectStoreError("relative_path or external_uri is required")
        if relative_path:
            self._validate_safe_relative_path(relative_path)
        linked_pages = self._validate_string_list(item, "linked_page_ids")
        existing_pages = {page.get("page_id") for page in pack.get("pages") or []}
        missing_pages = [page_id for page_id in linked_pages if page_id not in existing_pages]
        if missing_pages:
            raise ResearchProjectStoreError(f"linked_page_ids not found in pack: {', '.join(missing_pages)}")
        linked_drafts = self._validate_string_list(item, "linked_artifact_draft_ids")
        self._validate_artifact_draft_refs(project, linked_drafts, "linked_artifact_draft_ids")

    def _validate_safe_relative_path(self, value: str) -> None:
        if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
            raise ResearchProjectStoreError("relative_path must not be absolute")
        parts = [part for part in value.split("/") if part]
        if not parts or any(part == ".." for part in parts):
            raise ResearchProjectStoreError("relative_path must stay inside the project artifact area")
        if parts[0] != "artifact_files":
            raise ResearchProjectStoreError("relative_path must start with artifact_files/")

    def _validate_artifact_pack_review_round(self, project: ResearchProject, pack: dict[str, Any], item: dict[str, Any]) -> None:
        item.setdefault("status", "completed")
        item.setdefault("scope", {"pack_id": pack.get("pack_id")})
        item.setdefault("decisions", [])
        self._require_text(item, "round_name", "reviewer")
        self._validate_choice(item.get("status"), "status", {"draft", "completed"})
        decisions = item.get("decisions") or []
        if not isinstance(decisions, list) or not decisions:
            raise ResearchProjectStoreError("decisions must be a non-empty array")
        page_ids = {page.get("page_id") for page in pack.get("pages") or []}
        file_ref_ids = {ref.get("file_ref_id") for ref in pack.get("file_refs") or []}
        item["decisions"] = []
        for raw in decisions:
            if not isinstance(raw, dict):
                raise ResearchProjectStoreError("review decisions must be objects")
            decision = dict(raw)
            decision.setdefault("decision_id", _new_prefixed_id("rd"))
            decision.setdefault("severity", "minor")
            decision.setdefault("resolved", False)
            decision.setdefault("created_at", _now_iso())
            self._require_text(decision, "target_type", "target_id", "decision")
            self._validate_choice(decision.get("target_type"), "target_type", {"pack", "page", "file_ref", "pack_item"})
            self._validate_choice(decision.get("decision"), "decision", {
                "accepted",
                "needs_revision",
                "rejected",
                "comment_only",
            })
            self._validate_choice(decision.get("severity"), "severity", {"minor", "major", "blocking"})
            target_type = decision["target_type"]
            target_id = decision["target_id"]
            if target_type == "pack" and target_id != pack.get("pack_id"):
                raise ResearchProjectStoreError("review decision pack target_id does not match pack")
            if target_type == "page" and target_id not in page_ids:
                raise ResearchProjectStoreError(f"review decision page not found: {target_id}")
            if target_type == "file_ref" and target_id not in file_ref_ids:
                raise ResearchProjectStoreError(f"review decision file_ref not found: {target_id}")
            item["decisions"].append(decision)
        self._apply_review_decisions(pack, item["decisions"])

    def _apply_review_decisions(self, pack: dict[str, Any], decisions: list[dict[str, Any]]) -> None:
        pages = pack.get("pages") or []
        for decision in decisions:
            if decision.get("target_type") != "page":
                continue
            target_id = decision.get("target_id")
            for page in pages:
                if page.get("page_id") == target_id and decision.get("decision") in {"accepted", "needs_revision", "rejected"}:
                    page["review_status"] = decision["decision"]

    def _has_unresolved_blocking_decision(self, pack: dict[str, Any]) -> bool:
        for review in pack.get("review_rounds") or []:
            for decision in review.get("decisions") or []:
                if (
                    decision.get("severity") == "blocking"
                    and decision.get("decision") in {"needs_revision", "rejected"}
                    and not decision.get("resolved")
                ):
                    return True
        return False

    def _normalize_leadership_review_rounds(self, item: dict[str, Any]) -> None:
        rounds = item.get("review_rounds") or []
        if not isinstance(rounds, list):
            raise ResearchProjectStoreError("review_rounds must be an array")
        normalized = []
        now = _now_iso()
        for raw in rounds:
            if not isinstance(raw, dict):
                raise ResearchProjectStoreError("review_rounds must contain objects")
            review = dict(raw)
            review.setdefault("round_id", _new_prefixed_id("lrr"))
            review.setdefault("decision", "comment_only")
            review.setdefault("blocking", False)
            review.setdefault("resolved", False)
            review.setdefault("created_at", now)
            review.setdefault("updated_at", now)
            self._require_text(review, "reviewer", "decision")
            self._validate_choice(review.get("decision"), "review decision", {
                "approved",
                "needs_revision",
                "rejected",
                "comment_only",
            })
            normalized.append(review)
        item["review_rounds"] = normalized

    def _has_unresolved_blocking_leadership_review(self, item: dict[str, Any]) -> bool:
        for review in item.get("review_rounds") or []:
            if (
                review.get("blocking") is True
                and review.get("decision") in {"needs_revision", "rejected"}
                and not review.get("resolved")
            ):
                return True
        return False

    def _has_unresolved_blocking_briefing_review(self, item: dict[str, Any]) -> bool:
        for review in item.get("review_rounds") or []:
            if (
                review.get("blocking") is True
                and review.get("decision") in {"changes_requested", "rejected"}
                and not review.get("resolved")
            ):
                return True
        return False

    def _build_leadership_briefing_readiness_checks(self, item: dict[str, Any]) -> dict[str, Any]:
        summary = item.get("executive_summary") or {}
        required_refs = [
            ref for ref in item.get("source_asset_refs") or []
            if ref.get("required") is True
        ]
        for section in item.get("sections") or []:
            required_refs.extend(
                ref for ref in section.get("source_refs") or []
                if ref.get("required") is True
            )
        return {
            "has_executive_summary": bool(
                str(summary.get("headline") or "").strip()
                and str(summary.get("key_message") or "").strip()
                and str(summary.get("leadership_ask") or "").strip()
            ),
            "has_decision_ask": bool(item.get("decision_asks")),
            "all_required_sources_resolved": all(
                ref.get("asset_type") and ref.get("asset_id")
                for ref in required_refs
            ),
            "has_unresolved_section_issues": any(
                section.get("review_state") == "blocked"
                for section in item.get("sections") or []
            ),
            "has_blocking_review_decisions": self._has_unresolved_blocking_briefing_review(item),
        }

    def _leadership_briefing_source_counts(self, item: dict[str, Any]) -> dict[str, int]:
        labels = {
            "evidence_item": "evidence_items",
            "evidence_matrix_row": "evidence_matrix_rows",
            "insight_card": "insight_cards",
            "artifact_draft": "artifact_drafts",
            "artifact_pack": "artifact_packs",
            "strategic_option": "strategic_options",
            "validation_plan": "validation_plans",
            "leadership_decision_record": "leadership_decision_records",
        }
        counts = {value: 0 for value in labels.values()}
        seen: set[tuple[str, str]] = set()
        refs = list(item.get("source_asset_refs") or [])
        for section in item.get("sections") or []:
            refs.extend(section.get("source_refs") or [])
        for ref in refs:
            key = (ref.get("asset_type", ""), ref.get("asset_id", ""))
            if key in seen:
                continue
            seen.add(key)
            label = labels.get(ref.get("asset_type"))
            if label:
                counts[label] += 1
        return counts

    def _leadership_briefing_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "briefing_id": item["briefing_id"],
            "title": item.get("title", ""),
            "briefing_type": item.get("briefing_type", ""),
            "audience": item.get("audience", ""),
            "status": item.get("status", ""),
            "readiness": item.get("readiness", ""),
            "section_count": len(item.get("sections") or []),
            "source_counts": self._leadership_briefing_source_counts(item),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _strategic_option_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "option_id": item["option_id"],
            "title": item.get("title", ""),
            "status": item.get("status", ""),
            "recommendation_level": item.get("recommendation_level", ""),
            "decision_posture": item.get("decision_posture", ""),
            "source_insight_count": len(item.get("source_insight_ids") or []),
            "risk_count": len(item.get("risks") or []),
            "success_metric_count": len(item.get("success_metrics") or []),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _validation_plan_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "plan_id": item["plan_id"],
            "title": item.get("title", ""),
            "status": item.get("status", ""),
            "plan_type": item.get("plan_type", ""),
            "approval_state": item.get("approval_state", ""),
            "linked_option_ids": item.get("linked_option_ids") or [],
            "validation_question_count": len(item.get("validation_questions") or []),
            "milestone_count": len(item.get("milestones") or []),
            "metric_count": len(item.get("metrics") or []),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _leadership_decision_record_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision_id": item["decision_id"],
            "title": item.get("title", ""),
            "decision_status": item.get("decision_status", ""),
            "decision_type": item.get("decision_type", ""),
            "linked_option_ids": item.get("linked_option_ids") or [],
            "linked_validation_plan_ids": item.get("linked_validation_plan_ids") or [],
            "chosen_option_id": item.get("chosen_option_id", ""),
            "rationale_count": len(item.get("rationale") or []),
            "blocking_review_open": self._has_unresolved_blocking_leadership_review(item),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _governance_review_index(self, item: dict[str, Any]) -> dict[str, Any]:
        summary = item.get("review_summary") or {}
        return {
            "review_id": item["review_id"],
            "title": item.get("title", ""),
            "review_type": item.get("review_type", ""),
            "status": item.get("status", ""),
            "gate_decision": item.get("gate_decision", ""),
            "readiness": item.get("readiness", ""),
            "checklist_count": len(item.get("checklist_items") or []),
            "finding_count": len(item.get("findings") or []),
            "signoff_count": len(item.get("signoffs") or []),
            "blocker_count": summary.get("blocker_count", 0),
            "major_open_count": summary.get("major_open_count", 0),
            "failed_required_count": summary.get("failed_required_count", 0),
            "ready_for_next_stage": summary.get("ready_for_next_stage", False),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _evidence_matrix_row_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item["id"],
            "question": item.get("question", ""),
            "claim": item.get("claim", ""),
            "claim_type": item.get("claim_type", ""),
            "confidence": item.get("confidence", ""),
            "material_readiness": item.get("material_readiness", ""),
            "status": item.get("status", ""),
            "supporting_evidence_count": len(item.get("supporting_evidence_ids") or []),
            "counter_evidence_count": len(item.get("counter_evidence_ids") or []),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _insight_card_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item["id"],
            "title": item.get("title", ""),
            "claim": item.get("claim", ""),
            "confidence": item.get("confidence", ""),
            "status": item.get("status", ""),
            "supporting_evidence_count": len(item.get("supporting_evidence_ids") or []),
            "counter_evidence_count": len(item.get("counter_evidence_ids") or []),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _artifact_draft_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item["id"],
            "artifact_type": item.get("artifact_type", ""),
            "title": item.get("title", ""),
            "audience": item.get("audience", ""),
            "status": item.get("status", ""),
            "material_readiness": item.get("material_readiness", ""),
            "source_insight_count": len(item.get("source_insight_ids") or []),
            "source_evidence_count": len(item.get("source_evidence_ids") or []),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _artifact_pack_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "pack_id": item["pack_id"],
            "title": item.get("title", ""),
            "pack_type": item.get("pack_type", ""),
            "status": item.get("status", ""),
            "readiness": item.get("readiness", ""),
            "item_count": len(item.get("items") or []),
            "page_count": len(item.get("pages") or []),
            "file_ref_count": len(item.get("file_refs") or []),
            "review_round_count": len(item.get("review_rounds") or []),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _update_artifact_pack(
        self,
        project_id: str,
        pack_id: str,
        updates: dict[str, Any],
        *,
        allowed: set[str],
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise ResearchProjectStoreError(f"unsupported fields: {', '.join(unknown)}")
        pack = self._read_asset(project_id, "artifact_packs", pack_id)
        if pack is None:
            raise ResearchProjectStoreError(f"artifact pack not found: {pack_id}")
        clean = {**pack, **updates}
        self._validate_artifact_pack(project, clean)
        return self._save_artifact_pack(project, clean)

    def _append_artifact_pack_child(
        self,
        project_id: str,
        pack_id: str,
        *,
        list_field: str,
        id_field: str,
        id_prefix: str,
        payload: dict[str, Any],
        validator,
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        pack = self._read_asset(project_id, "artifact_packs", pack_id)
        if pack is None:
            raise ResearchProjectStoreError(f"artifact pack not found: {pack_id}")
        child = dict(payload)
        child[id_field] = child.get(id_field) or _new_prefixed_id(id_prefix)
        child.setdefault("created_at", _now_iso())
        child["updated_at"] = _now_iso()
        validator(project, pack, child)
        values = list(pack.get(list_field) or [])
        values.append(child)
        pack[list_field] = values
        self._validate_artifact_pack(project, pack)
        return self._save_artifact_pack(project, pack)

    def _update_artifact_pack_child(
        self,
        project_id: str,
        pack_id: str,
        *,
        list_field: str,
        id_field: str,
        child_id: str,
        updates: dict[str, Any],
        allowed: set[str],
        validator,
    ) -> Optional[dict[str, Any]]:
        project = self.get(project_id)
        if project is None:
            return None
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise ResearchProjectStoreError(f"unsupported fields: {', '.join(unknown)}")
        pack = self._read_asset(project_id, "artifact_packs", pack_id)
        if pack is None:
            raise ResearchProjectStoreError(f"artifact pack not found: {pack_id}")
        values = list(pack.get(list_field) or [])
        updated = False
        for idx, value in enumerate(values):
            if value.get(id_field) == child_id:
                child = {**value, **updates, "updated_at": _now_iso()}
                validator(project, pack, child)
                values[idx] = child
                updated = True
                break
        if not updated:
            raise ResearchProjectStoreError(f"artifact pack child not found: {child_id}")
        pack[list_field] = values
        self._validate_artifact_pack(project, pack)
        return self._save_artifact_pack(project, pack)

    def _save_artifact_pack(self, project: ResearchProject, pack: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        pack["updated_at"] = now
        pack["payload_hash"] = _payload_hash({
            key: value
            for key, value in pack.items()
            if key not in {"created_at", "updated_at", "payload_hash"}
        })
        self._atomic_write(self._asset_path(project.id, "artifact_packs", pack["pack_id"]), pack)
        self._write_index_item(project, "artifact_packs", "pack_id", self._artifact_pack_index(pack))
        project.updated_at = now
        self.save(project)
        return pack

    def _external_pack_index(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "pack_id": item["pack_id"],
            "title": item.get("title", ""),
            "source_type": item.get("source_type", ""),
            "scope": item.get("scope", ""),
            "status": item.get("status", ""),
            "candidate_count": len(item.get("evidence_candidates") or []),
            "accepted_count": sum(
                1 for candidate in item.get("evidence_candidates") or []
                if candidate.get("review_status") == "accepted"
            ),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _candidate_id(self, candidate: dict[str, Any]) -> str:
        key = str(candidate.get("external_id") or candidate.get("claim") or candidate.get("evidence_text") or "")
        return f"ec_{sha256(key.encode('utf-8')).hexdigest()[:12]}"

    def _external_evidence_id(self, pack: dict[str, Any], candidate: dict[str, Any]) -> str:
        key = f"{pack.get('pack_id','')}:{candidate.get('candidate_id') or candidate.get('external_id','')}"
        return f"ei_{sha256(key.encode('utf-8')).hexdigest()[:12]}"

    def _upsert_external_evidence_item(
        self,
        project: ResearchProject,
        pack: dict[str, Any],
        candidate: dict[str, Any],
        *,
        accepted_at: str,
    ) -> None:
        evidence_id = self._external_evidence_id(pack, candidate)
        item = {
            "evidence_id": evidence_id,
            "origin": "external_research_pack",
            "source_type": pack.get("source_type", ""),
            "scope": pack.get("scope", "C2_external"),
            "pack_id": pack.get("pack_id", ""),
            "run_id": pack.get("run_id", ""),
            "candidate_id": candidate.get("candidate_id", ""),
            "claim": candidate.get("claim", ""),
            "title": candidate.get("claim", ""),
            "summary": candidate.get("evidence_text", ""),
            "evidence_text": candidate.get("evidence_text", ""),
            "source_refs": candidate.get("source_refs") or [],
            "confidence": candidate.get("confidence"),
            "review_status": "accepted",
            "status": "accepted",
            "created_by": "codex",
            "accepted_at": accepted_at,
            "provenance": {
                "producer_kind": (pack.get("producer") or {}).get("kind", ""),
                "producer_name": (pack.get("producer") or {}).get("name", ""),
                "model": (pack.get("producer") or {}).get("model", ""),
                "idempotency_key": pack.get("idempotency_key", ""),
            },
        }
        existing = [
            old for old in project.evidence_items
            if old.get("evidence_id") != evidence_id
        ]
        existing.append(item)
        project.evidence_items = existing

    def _build_pack_summary(self, pack: dict[str, Any]) -> dict[str, Any]:
        candidates = pack.get("candidates") or []
        accepted = [item for item in candidates if item.get("status") == "accepted"]
        degraded_count = sum(
            1 for item in candidates
            if any(ref.get("degraded") for ref in item.get("source_refs") or [])
        )
        source_projects = {
            ref.get("project_id")
            for item in candidates
            for ref in item.get("source_refs") or []
            if ref.get("project_id")
        }
        concept_count = sum(1 for item in candidates if item.get("evidence_type") == "concept")
        theme_count = sum(1 for item in candidates if item.get("evidence_type") == "theme")
        return {
            "candidate_count": len(candidates),
            "accepted_count": len(accepted),
            "degraded_count": degraded_count,
            "source_project_count": len(source_projects),
            "concept_count": concept_count,
            "theme_count": theme_count,
        }
