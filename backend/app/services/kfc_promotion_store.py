"""KFC promotion sidecar store.

This store persists the human-reviewed bridge from Wiki rough-processing
outputs into KFC candidate assets. It only reads and writes JSON sidecars; it
does not call models, workers, schedulers, Codex, or external processes.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..models.research_project import ResearchProjectStore, ResearchProjectStoreError
from ..services.workspace.concept_normalization import normalize_concept_name
from .topic_cluster_store import TopicClusterStore


_DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_UPLOAD_PROJECTS_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "projects"
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")
SLICE_TYPES = {"concept_lead", "evidence_slice"}
PROMOTION_STATUSES = {
    "pending",
    "reviewed",
    "confirmed",
    "linked",
    "materialized_concept",
    "candidate_created",
    "added_to_project_evidence",
    "ignored",
    "deprecated",
    "unlinked",
}
PROMOTION_ACTIONS = {
    "link_existing_registry_entry",
    "switch_registry_match",
    "deposit_as_new_concept",
    "create_concept_from_lead",
    "materialize_concept",
    "create_new_registry_candidate",
    "add_as_project_evidence",
    "review_quote",
    "replace_quote",
    "confirm_review",
    "mark_reviewed",
    "ignore",
    "deprecate_materialized_concept",
    "unlink_promotion_target",
}
RELATION_CANDIDATE_ACTIONS = {"confirm", "reject", "change_relation_type"}
QUOTE_REVIEW_STATUSES = {"weak", "wrong", "needs_verification", "replace_requested", "replaced"}
RELATION_CANDIDATE_STATUSES = {"pending_review", "confirmed", "rejected", "needs_revision"}
PROCESSED_REVIEW_STATUSES = {
    "reviewed",
    "confirmed",
    "rejected",
    "linked",
    "materialized_concept",
    "candidate_created",
    "added_to_project_evidence",
    "ignored",
    "deprecated",
    "unlinked",
}
ARTICLE_REVIEW_GROUPS = [
    {
        "group_id": "pending_review",
        "title": "待审核",
        "description": "尚未形成明确 reviewer decision 的候选。",
    },
    {
        "group_id": "high_confidence_quick_confirm",
        "title": "高置信可快速确认",
        "description": "置信度较高、无阻断风险，适合显式勾选后批量确认。",
    },
    {
        "group_id": "low_confidence_manual_judgment",
        "title": "低置信 / 需人工判断",
        "description": "置信度低或关系类型/匹配存在歧义，需要逐项判断。",
    },
    {
        "group_id": "weak_quote_review",
        "title": "证据弱 / 引文需核对",
        "description": "quote 缺失、偏弱、被标记错误或需要替换。",
    },
    {
        "group_id": "relation_pending",
        "title": "关系候选待确认",
        "description": "需要确认、拒绝或修正 relation_type 的关系候选。",
    },
    {
        "group_id": "processed",
        "title": "已处理",
        "description": "已经产生本地 reviewer decision 的候选。",
    },
]


class KfcPromotionStoreError(ValueError):
    """Raised for invalid KFC promotion sidecar operations."""

    def __init__(self, message: str, *, code: str = "validation_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d')}_{secrets.token_hex(4)}"


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(raw.encode('utf-8')).hexdigest()}"


def _trim(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


class KfcPromotionStore:
    """Persists MaterialSlice, LeadPromotion, and registry-candidate sidecars."""

    MATERIAL_SLICE_DIR: Path = _DEFAULT_DATA_ROOT / "material_slices"
    LEAD_PROMOTION_DIR: Path = _DEFAULT_DATA_ROOT / "lead_promotions"
    CONCEPT_REGISTRY_CANDIDATE_DIR: Path = _DEFAULT_DATA_ROOT / "concept_registry_candidates"
    KFC_RELATION_DIR: Path = _DEFAULT_DATA_ROOT / "kfc_asset_relations"
    RELATION_CANDIDATE_DIR: Path = _DEFAULT_DATA_ROOT / "relation_candidates"
    KFC_CHANGE_LOG_DIR: Path = _DEFAULT_DATA_ROOT / "kfc_change_log"
    CONCEPT_REGISTRY_PATH: Path = _DEFAULT_UPLOAD_PROJECTS_ROOT / "concept_registry.json"

    def __init__(
        self,
        *,
        material_slice_dir: str | Path | None = None,
        lead_promotion_dir: str | Path | None = None,
        concept_registry_candidate_dir: str | Path | None = None,
        kfc_relation_dir: str | Path | None = None,
        relation_candidate_dir: str | Path | None = None,
        kfc_change_log_dir: str | Path | None = None,
        concept_registry_path: str | Path | None = None,
        topic_cluster_store: TopicClusterStore | None = None,
        research_project_store: ResearchProjectStore | None = None,
    ) -> None:
        self.material_slice_dir = Path(material_slice_dir or self.MATERIAL_SLICE_DIR).expanduser().resolve()
        self.lead_promotion_dir = Path(lead_promotion_dir or self.LEAD_PROMOTION_DIR).expanduser().resolve()
        self.concept_registry_candidate_dir = Path(
            concept_registry_candidate_dir or self.CONCEPT_REGISTRY_CANDIDATE_DIR
        ).expanduser().resolve()
        self.kfc_relation_dir = Path(kfc_relation_dir or self.KFC_RELATION_DIR).expanduser().resolve()
        self.relation_candidate_dir = Path(relation_candidate_dir or self.RELATION_CANDIDATE_DIR).expanduser().resolve()
        self.kfc_change_log_dir = Path(kfc_change_log_dir or self.KFC_CHANGE_LOG_DIR).expanduser().resolve()
        self.concept_registry_path = Path(concept_registry_path or self.CONCEPT_REGISTRY_PATH).expanduser().resolve()
        self.topic_cluster_store = topic_cluster_store or TopicClusterStore()
        self.research_project_store = research_project_store or ResearchProjectStore()

    def create_material_slice(self, cluster_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_cluster(cluster_id)
        clean = self._validate_slice_payload(payload)
        now = _now_iso()
        slice_id = clean.get("slice_id") or _new_id("ms")
        self._validate_identifier(slice_id, "slice_id")
        slice_path = self._slice_path(slice_id)
        if slice_path.exists():
            raise KfcPromotionStoreError(
                f"material slice already exists: {slice_id}",
                code="duplicate_material_slice",
                status_code=409,
            )

        material_slice = {
            "slice_id": slice_id,
            "slice_type": clean["slice_type"],
            "title": clean["title"],
            "display_title": clean.get("display_title") or clean["title"],
            "summary": clean.get("summary", ""),
            "source_quote": clean.get("source_quote", ""),
            "source_excerpt": clean.get("source_excerpt", ""),
            "source_context": clean.get("source_context", ""),
            "source_span": clean.get("source_span") or {},
            "source_article_id": clean.get("source_article_id", ""),
            "source_markdown_path": clean.get("source_markdown_path", ""),
            "source_content_hash": clean.get("source_content_hash", ""),
            "source_title": clean.get("source_title", ""),
            "source_url": clean.get("source_url", ""),
            "linked_topic_cluster": cluster_id,
            "linked_wiki_topic": clean.get("linked_wiki_topic", ""),
            "linked_research_project": clean.get("linked_research_project") or "",
            "extraction_reason": clean.get("extraction_reason", ""),
            "confidence": clean.get("confidence"),
            "recommended_action": clean.get("recommended_action", ""),
            "why_this_is_a_concept": clean.get("why_this_is_a_concept", ""),
            "risk": clean.get("risk") or [],
            "alternative_matches": clean.get("alternative_matches") or [],
            "created_from": clean.get("created_from", "topic_cluster_detail"),
            "created_by": clean.get("created_by", "human"),
            "review_status": "promoted" if clean.get("create_promotion", True) else "draft",
            "payload_hash": _payload_hash(clean),
            "created_at": now,
            "updated_at": now,
        }
        self._atomic_write(slice_path, material_slice)

        promotion = None
        if clean.get("create_promotion", True):
            promotion = self._create_promotion_for_slice(material_slice, now=now)
        return {"slice": material_slice, "promotion": promotion}

    def list_promotion_basket(self, cluster_id: str) -> dict[str, Any]:
        self._require_cluster(cluster_id)
        slices = {item["slice_id"]: item for item in self._list_json(self.material_slice_dir, "ms_*.json")}
        items: list[dict[str, Any]] = []
        for promotion in self._list_json(self.lead_promotion_dir, "lp_*.json"):
            if promotion.get("linked_topic_cluster") != cluster_id:
                continue
            material_slice = slices.get(str(promotion.get("slice_id") or "")) or {}
            items.append(self._basket_item(promotion, material_slice))
        items.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
        counts = {status: 0 for status in PROMOTION_STATUSES}
        for item in items:
            status = item.get("review_status") or "pending"
            if status in counts:
                counts[status] += 1
        return {
            "cluster_id": cluster_id,
            "counts": counts,
            "items": items,
            "provenance": {
                "material_slices_source": "backend/data/material_slices",
                "lead_promotions_source": "backend/data/lead_promotions",
                "concept_registry_candidates_source": "backend/data/concept_registry_candidates",
                "concept_registry_source": str(self.concept_registry_path),
                "relation_source": "backend/data/kfc_asset_relations",
                "change_log_source": "backend/data/kfc_change_log/kfc_changes.jsonl",
                "mutation": "kfc_asset_store",
            },
        }

    def get_promotion_trace(self, cluster_id: str, promotion_id: str) -> dict[str, Any] | None:
        self._require_cluster(cluster_id)
        promotion = self._read_optional(self._promotion_path(promotion_id))
        if not promotion or promotion.get("linked_topic_cluster") != cluster_id:
            return None
        material_slice = self._read_optional(self._slice_path(str(promotion.get("slice_id") or ""))) or {}
        registry_candidate = None
        candidate_id = ((promotion.get("candidate") or {}).get("candidate_id") or "")
        if candidate_id:
            registry_candidate = self._read_optional(self._registry_candidate_path(candidate_id))
        concept = None
        concept_id = ((promotion.get("concept") or {}).get("concept_id") or "")
        if concept_id:
            concept = self._load_registry().get("entries", {}).get(concept_id)
        target = promotion.get("target") or {}
        return {
            "promotion": promotion,
            "slice": material_slice,
            "registry_candidate": registry_candidate,
            "concept": concept,
            "relations": self._relations_for_promotion(promotion_id),
            "trace": {
                "article_id": material_slice.get("source_article_id", ""),
                "slice_id": material_slice.get("slice_id", ""),
                "promotion_id": promotion.get("promotion_id", ""),
                "target_type": target.get("target_type", ""),
                "target_id": target.get("target_id", ""),
            },
        }

    def list_recent_changes(self, cluster_id: str, *, limit: int = 30) -> dict[str, Any]:
        self._require_cluster(cluster_id)
        changes = [
            item
            for item in self._read_change_log()
            if item.get("cluster_id") == cluster_id
        ]
        changes.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return {
            "cluster_id": cluster_id,
            "items": changes[: max(1, min(limit, 100))],
            "total": len(changes),
        }

    def get_article_processing_review(self, cluster_id: str, article_id: str) -> dict[str, Any]:
        self._require_cluster(cluster_id)
        article_id = _trim(article_id, 200)
        if not article_id:
            raise KfcPromotionStoreError("article_id is required")
        basket = self.list_promotion_basket(cluster_id)
        candidate_items = [
            item for item in basket.get("items", [])
            if (item.get("source") or {}).get("source_article_id") == article_id
        ]
        relation_candidates = [
            item for item in self._list_relation_candidates(cluster_id)
            if item.get("source_article_id") == article_id
        ]
        candidate_cards = [
            self._candidate_card_from_promotion(item)
            for item in candidate_items
        ] + [
            self._candidate_card_from_relation_candidate(item)
            for item in relation_candidates
        ]
        candidate_cards = [self._enrich_article_review_card(card) for card in candidate_cards]
        review_groups = self._article_review_groups(candidate_cards)
        review_trail = self._article_review_trail(candidate_cards)
        status_counts: dict[str, int] = {}
        type_counts = {"concept_lead": 0, "evidence_lead": 0, "relation_candidate": 0}
        high_risk = 0
        low_quality = 0
        needs_review = 0
        processed_count = 0
        changed_count = 0
        rejected_count = 0
        unresolved_risk_count = 0
        relation_pending_count = 0
        quote_issues_pending = 0
        for card in candidate_cards:
            status = card.get("status") or "pending"
            status_counts[status] = status_counts.get(status, 0) + 1
            card_type = card.get("candidate_type")
            if card_type in type_counts:
                type_counts[card_type] += 1
            if card.get("risk_flags"):
                high_risk += 1
            if card.get("quality_state") in {"weak", "wrong", "needs_verification", "low_quality"}:
                low_quality += 1
            if status in {"pending", "pending_review", "needs_revision"} or card.get("risk_flags"):
                needs_review += 1
            if status in PROCESSED_REVIEW_STATUSES:
                processed_count += 1
            if card.get("current_review_state", {}).get("latest_action_type"):
                changed_count += 1
            if status == "rejected":
                rejected_count += 1
            if card.get("review_group_ids") and "processed" not in card.get("review_group_ids", []):
                if card.get("risk_flags"):
                    unresolved_risk_count += 1
            if "relation_pending" in card.get("review_group_ids", []):
                relation_pending_count += 1
            if card.get("needs_quote_review") and status not in PROCESSED_REVIEW_STATUSES:
                quote_issues_pending += 1
        pending_count = max(0, len(candidate_cards) - processed_count)
        completion_status = self._article_completion_status(
            len(candidate_cards),
            processed_count,
            unresolved_risk_count,
            relation_pending_count,
            quote_issues_pending,
        )
        article_title = next(
            (
                (item.get("source") or {}).get("source_title")
                for item in candidate_items
                if (item.get("source") or {}).get("source_title")
            ),
            next((item.get("source_title") for item in relation_candidates if item.get("source_title")), ""),
        )
        return {
            "cluster_id": cluster_id,
            "article_id": article_id,
            "article_title": article_title,
            "summary": {
                "candidate_count": len(candidate_cards),
                "total_candidates": len(candidate_cards),
                "concept_leads": type_counts["concept_lead"],
                "evidence_leads": type_counts["evidence_lead"],
                "relation_candidates": type_counts["relation_candidate"],
                "needs_review": needs_review,
                "high_risk": high_risk,
                "low_quality": low_quality,
                "pending_count": pending_count,
                "reviewed_count": processed_count,
                "processed_count": processed_count,
                "changed_count": changed_count,
                "rejected_count": rejected_count,
                "unresolved_risk_count": unresolved_risk_count,
                "relation_candidates_pending": relation_pending_count,
                "quote_issues_pending": quote_issues_pending,
                "completion_status": completion_status["status_code"],
                "completion_status_label": completion_status["status_label"],
                "completion_ratio": round(processed_count / len(candidate_cards), 2) if candidate_cards else 0,
                "status_counts": status_counts,
            },
            "article_completion": {
                **completion_status,
                "total_candidates": len(candidate_cards),
                "pending_count": pending_count,
                "reviewed_count": processed_count,
                "changed_count": changed_count,
                "rejected_count": rejected_count,
                "unresolved_risk_count": unresolved_risk_count,
                "relation_candidates_pending": relation_pending_count,
                "quote_issues_pending": quote_issues_pending,
            },
            "review_groups": review_groups,
            "candidate_cards": candidate_cards,
            "review_trail": {
                "compact_items": review_trail,
                "total": len(review_trail),
                "source": "append_only_sidecars",
            },
            "provenance": {
                "material_slices_source": "backend/data/material_slices",
                "lead_promotions_source": "backend/data/lead_promotions",
                "relation_candidates_source": "backend/data/relation_candidates",
                "review_trail_source": "backend/data/kfc_change_log/kfc_changes.jsonl",
                "mutation": "front_half_review_sidecars",
            },
        }

    def apply_article_processing_batch_action(
        self,
        cluster_id: str,
        article_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_cluster(cluster_id)
        article_id = _trim(article_id, 200)
        if not article_id:
            raise KfcPromotionStoreError("article_id is required")
        if not isinstance(payload, dict):
            raise KfcPromotionStoreError("JSON body must be an object")
        if payload.get("group_id") or payload.get("review_group_id"):
            raise KfcPromotionStoreError("batch action requires explicit card_ids; group_id is not accepted")
        action_type = _trim(payload.get("action_type") or payload.get("action"), 80)
        allowed_actions = {
            "confirm_high_confidence_concepts",
            "mark_evidence_reviewed",
            "reject_weak_relations",
        }
        if action_type not in allowed_actions:
            raise KfcPromotionStoreError(f"unsupported batch action_type: {action_type}")
        card_ids = payload.get("card_ids")
        if not isinstance(card_ids, list) or not card_ids:
            raise KfcPromotionStoreError("card_ids must be a non-empty explicit list")
        card_ids = [_trim(card_id, 200) for card_id in card_ids if _trim(card_id, 200)]
        if not card_ids:
            raise KfcPromotionStoreError("card_ids must include at least one valid id")
        review = self.get_article_processing_review(cluster_id, article_id)
        cards_by_id = {card.get("card_id") or card.get("candidate_id"): card for card in review.get("candidate_cards", [])}
        batch_id = _new_id("batch")
        actor = _trim(payload.get("actor") or payload.get("reviewer") or "human", 80)
        note = _trim(payload.get("note"), 500)
        applied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for card_id in card_ids:
            card = cards_by_id.get(card_id)
            if not card:
                skipped.append({"card_id": card_id, "reason": "not_found_in_article"})
                continue
            if action_type not in (card.get("batch_action_types") or []):
                skipped.append({"card_id": card_id, "reason": "not_batch_eligible"})
                continue
            if card.get("status") in PROCESSED_REVIEW_STATUSES:
                skipped.append({"card_id": card_id, "reason": "already_processed"})
                continue
            if action_type == "confirm_high_confidence_concepts":
                updated = self.apply_promotion_action(
                    cluster_id,
                    card_id,
                    {
                        "action": "confirm_review",
                        "actor": actor,
                        "batch_id": batch_id,
                        "note": note or "Batch confirmed high-confidence Concept Lead.",
                    },
                )
            elif action_type == "mark_evidence_reviewed":
                updated = self.apply_promotion_action(
                    cluster_id,
                    card_id,
                    {
                        "action": "mark_reviewed",
                        "actor": actor,
                        "batch_id": batch_id,
                        "note": note or "Batch marked Evidence Lead reviewed.",
                    },
                )
            else:
                updated = self.apply_relation_candidate_action(
                    cluster_id,
                    card_id,
                    {
                        "action": "reject",
                        "actor": actor,
                        "batch_id": batch_id,
                        "relation_type": card.get("relation_type") or "related_to",
                        "note": note or "Batch rejected weak Relation Candidate.",
                    },
                )
            if not updated:
                skipped.append({"card_id": card_id, "reason": "not_found"})
                continue
            applied.append(
                {
                    "card_id": card_id,
                    "candidate_type": card.get("candidate_type"),
                    "action_type": action_type,
                    "status": updated.get("review_status"),
                    "batch_id": batch_id,
                }
            )
        return {
            "cluster_id": cluster_id,
            "article_id": article_id,
            "batch_id": batch_id,
            "action_type": action_type,
            "applied": applied,
            "skipped": skipped,
            "summary": {
                "requested": len(card_ids),
                "applied": len(applied),
                "skipped": len(skipped),
            },
        }

    def create_relation_candidate(self, cluster_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_cluster(cluster_id)
        if not isinstance(payload, dict):
            raise KfcPromotionStoreError("JSON body must be an object")
        now = _now_iso()
        candidate_id = payload.get("relation_candidate_id") or _new_id("relcand")
        self._validate_identifier(candidate_id, "relation_candidate_id")
        path = self._relation_candidate_path(candidate_id)
        if path.exists():
            raise KfcPromotionStoreError(
                f"relation candidate already exists: {candidate_id}",
                code="duplicate_relation_candidate",
                status_code=409,
            )
        subject = _trim(payload.get("subject_concept") or payload.get("subject") or payload.get("source_label"), 200)
        obj = _trim(payload.get("object_concept") or payload.get("object") or payload.get("target_label"), 200)
        relation_type = _trim(payload.get("relation_type") or "related_to", 80)
        if not subject or not obj:
            raise KfcPromotionStoreError("subject_concept and object_concept are required")
        if not relation_type:
            raise KfcPromotionStoreError("relation_type is required")
        candidate = {
            "relation_candidate_id": candidate_id,
            "candidate_type": "relation_candidate",
            "linked_topic_cluster": cluster_id,
            "source_article_id": _trim(payload.get("source_article_id"), 200),
            "source_title": _trim(payload.get("source_title"), 300),
            "source_markdown_path": str(payload.get("source_markdown_path") or ""),
            "source_content_hash": _trim(payload.get("source_content_hash"), 200),
            "source_quote": _trim(payload.get("source_quote"), 1000),
            "source_context": _trim(payload.get("source_context"), 2000),
            "subject_concept": subject,
            "subject_concept_id": _trim(payload.get("subject_concept_id"), 200),
            "relation_type": relation_type,
            "object_concept": obj,
            "object_concept_id": _trim(payload.get("object_concept_id"), 200),
            "why_relation_exists": _trim(payload.get("why_relation_exists") or payload.get("reason"), 1000),
            "confidence": payload.get("confidence") if isinstance(payload.get("confidence"), (int, float)) else 0.72,
            "possible_alternative_relation_types": payload.get("possible_alternative_relation_types") if isinstance(payload.get("possible_alternative_relation_types"), list) else [],
            "review_status": "pending_review",
            "action_history": [],
            "created_from": _trim(payload.get("created_from") or "article_processing_review", 120),
            "created_by": _trim(payload.get("created_by") or "human", 80),
            "created_at": now,
            "updated_at": now,
        }
        self._atomic_write(path, candidate)
        self._record_change(
            action="create_relation_candidate",
            actor=candidate["created_by"],
            cluster_id=cluster_id,
            source_ids={
                "relation_candidate_id": candidate_id,
                "source_article_id": candidate.get("source_article_id", ""),
                "source_content_hash": candidate.get("source_content_hash", ""),
            },
            after={"relation_candidate": candidate},
            confidence=float(candidate.get("confidence") or 0),
            reason="Relation Candidate created for front-half article processing review.",
        )
        return candidate

    def apply_relation_candidate_action(
        self,
        cluster_id: str,
        relation_candidate_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        self._require_cluster(cluster_id)
        self._validate_identifier(relation_candidate_id, "relation_candidate_id")
        path = self._relation_candidate_path(relation_candidate_id)
        candidate = self._read_optional(path)
        if not candidate or candidate.get("linked_topic_cluster") != cluster_id:
            return None
        action = _trim(payload.get("action"), 80)
        if action not in RELATION_CANDIDATE_ACTIONS:
            raise KfcPromotionStoreError(f"unsupported relation candidate action: {action}")
        before = dict(candidate)
        now = _now_iso()
        next_relation_type = _trim(payload.get("relation_type") or candidate.get("relation_type") or "related_to", 80)
        if action == "change_relation_type":
            status = "needs_revision"
        elif action == "confirm":
            status = "confirmed"
        else:
            status = "rejected"
        history = list(candidate.get("action_history") or [])
        history.append(
            {
                "action_id": _new_id("act"),
                "action": action,
                "actor": _trim(payload.get("actor") or "human", 80),
                "batch_id": _trim(payload.get("batch_id"), 120),
                "created_at": now,
                "relation_type_before": before.get("relation_type", ""),
                "relation_type_after": next_relation_type,
                "note": _trim(payload.get("note") or payload.get("reason"), 500),
            }
        )
        candidate.update({
            "relation_type": next_relation_type,
            "review_status": status,
            "action_history": history,
            "updated_at": now,
        })
        self._atomic_write(path, candidate)
        self._record_change(
            action=f"relation_candidate_{action}",
            actor=history[-1]["actor"],
            cluster_id=cluster_id,
            source_ids={
                "relation_candidate_id": relation_candidate_id,
                "source_article_id": candidate.get("source_article_id", ""),
                "source_content_hash": candidate.get("source_content_hash", ""),
            },
            before=before,
            after={"relation_candidate": candidate},
            confidence=float(candidate.get("confidence") or 0),
            reason=history[-1]["note"] or f"Relation Candidate {action}.",
        )
        return candidate

    def apply_promotion_action(self, cluster_id: str, promotion_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        self._require_cluster(cluster_id)
        self._validate_identifier(promotion_id, "promotion_id")
        promotion_path = self._promotion_path(promotion_id)
        promotion = self._read_optional(promotion_path)
        if not promotion or promotion.get("linked_topic_cluster") != cluster_id:
            return None
        material_slice = self._read_optional(self._slice_path(str(promotion.get("slice_id") or ""))) or {}
        action = str(payload.get("action") or "").strip()
        if action not in PROMOTION_ACTIONS:
            raise KfcPromotionStoreError(f"unsupported promotion action: {action}")

        now = _now_iso()
        if action in {"link_existing_registry_entry", "switch_registry_match"}:
            updated = self._apply_link_existing(promotion, material_slice, payload, now)
            if action == "switch_registry_match":
                updated["decision"] = "switch_registry_match"
                if updated.get("action_history"):
                    updated["action_history"][-1]["action"] = "switch_registry_match"
                self._record_change(
                    action="switch_registry_match",
                    actor=_trim(payload.get("actor") or "human", 80),
                    cluster_id=promotion.get("linked_topic_cluster", ""),
                    source_ids=self._source_ids(
                        promotion,
                        material_slice,
                        concept_id=(updated.get("target") or {}).get("target_id", ""),
                    ),
                    before=promotion,
                    after={"promotion": updated},
                    confidence=self._confidence(payload, material_slice),
                    reason=_trim(payload.get("note") or "Reviewer switched the registry match.", 500),
                )
        elif action in {"deposit_as_new_concept", "create_concept_from_lead", "materialize_concept"}:
            updated = self._apply_deposit_as_new_concept(promotion, material_slice, payload, now)
        elif action == "create_new_registry_candidate":
            updated = self._apply_create_registry_candidate(promotion, material_slice, payload, now)
        elif action == "add_as_project_evidence":
            updated = self._apply_add_project_evidence(promotion, material_slice, payload, now)
        elif action in {"review_quote", "replace_quote"}:
            updated = self._apply_quote_review(promotion, material_slice, payload, now, action=action)
        elif action in {"confirm_review", "mark_reviewed"}:
            updated = self._apply_review_marker(promotion, material_slice, payload, now, action=action)
        elif action == "deprecate_materialized_concept":
            updated = self._apply_deprecate_materialized_concept(promotion, payload, now)
        elif action == "unlink_promotion_target":
            updated = self._apply_unlink_promotion_target(promotion, payload, now)
        else:
            updated = self._apply_ignore(promotion, material_slice, payload, now)

        self._atomic_write(promotion_path, updated)
        return updated

    def update_concept(self, concept_id: str, payload: dict[str, Any], *, actor: str = "human") -> dict[str, Any]:
        registry = self._load_registry()
        entry = registry.get("entries", {}).get(concept_id)
        if not entry:
            raise KfcPromotionStoreError(f"concept not found: {concept_id}", code="concept_not_found", status_code=404)
        before = dict(entry)
        allowed = {"label", "canonical_name", "aliases", "definition", "description", "quality_state", "review_state"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise KfcPromotionStoreError(f"unsupported fields: {', '.join(unknown)}")
        if "label" in payload or "canonical_name" in payload:
            label = _trim(payload.get("label") or payload.get("canonical_name"), 200)
            if not label:
                raise KfcPromotionStoreError("label is required")
            entry["canonical_name"] = label
            entry["label"] = label
        if "aliases" in payload:
            aliases = payload.get("aliases") or []
            if not isinstance(aliases, list):
                raise KfcPromotionStoreError("aliases must be an array")
            entry["aliases"] = [str(item)[:120] for item in aliases if item]
        if "definition" in payload or "description" in payload:
            definition = _trim(payload.get("definition") or payload.get("description"), 2000)
            entry["definition"] = definition
            entry["description"] = definition
        for field in ("quality_state", "review_state"):
            if field in payload:
                entry[field] = _trim(payload.get(field), 80)
        entry["updated_at"] = _now_iso()
        entry["version"] = int(entry.get("version") or 1) + 1
        registry["entries"][concept_id] = entry
        self._save_registry(registry)
        self._record_change(
            action="update_concept",
            actor=actor,
            cluster_id=(entry.get("linked_topic_cluster_ids") or [""])[0],
            source_ids={"concept_id": concept_id},
            before=before,
            after=entry,
            confidence=entry.get("confidence"),
            reason="Concept corrected through KFC governance API.",
        )
        return entry

    def deprecate_concept(self, concept_id: str, payload: dict[str, Any] | None = None, *, actor: str = "human") -> dict[str, Any]:
        payload = payload or {}
        registry = self._load_registry()
        entry = registry.get("entries", {}).get(concept_id)
        if not entry:
            raise KfcPromotionStoreError(f"concept not found: {concept_id}", code="concept_not_found", status_code=404)
        before = dict(entry)
        entry["lifecycle_status"] = _trim(payload.get("lifecycle_status") or "deprecated", 80)
        entry["quality_state"] = _trim(payload.get("quality_state") or "needs_review", 80)
        entry["review_state"] = _trim(payload.get("review_state") or "disputed", 80)
        entry["deprecated_reason"] = _trim(payload.get("reason") or payload.get("note"), 500)
        entry["updated_at"] = _now_iso()
        entry["version"] = int(entry.get("version") or 1) + 1
        registry["entries"][concept_id] = entry
        self._save_registry(registry)
        self._record_change(
            action="deprecate_concept",
            actor=actor,
            cluster_id=(entry.get("linked_topic_cluster_ids") or [""])[0],
            source_ids={"concept_id": concept_id},
            before=before,
            after=entry,
            confidence=entry.get("confidence"),
            reason=entry.get("deprecated_reason") or "Concept deprecated through KFC governance API.",
        )
        return entry

    def unlink_concept_relation(
        self,
        concept_id: str,
        *,
        relation_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        actor: str = "human",
    ) -> dict[str, Any]:
        removed: list[dict[str, Any]] = []
        for relation in self._relations_for_concept(concept_id):
            if relation_id and relation.get("relation_id") != relation_id:
                continue
            if target_type and relation.get("target_type") != target_type:
                continue
            if target_id and relation.get("target_id") != target_id:
                continue
            relation["deleted"] = True
            relation["deleted_at"] = _now_iso()
            relation["updated_at"] = relation["deleted_at"]
            self._atomic_write(self._relation_path(str(relation["relation_id"])), relation)
            removed.append(relation)
        if not removed:
            raise KfcPromotionStoreError("concept relation not found", code="relation_not_found", status_code=404)
        self._record_change(
            action="unlink_concept_relation",
            actor=actor,
            cluster_id=removed[0].get("cluster_id", ""),
            source_ids={"concept_id": concept_id, "relation_ids": [item.get("relation_id") for item in removed]},
            after={"removed": removed},
            reason="Relation unlinked through KFC governance API.",
        )
        return {"concept_id": concept_id, "removed": removed}

    def attach_concept_to_research_project(
        self,
        concept_id: str,
        project_id: str,
        *,
        evidence_id: str = "",
        actor: str = "human",
        reason: str = "Accepted local evidence candidate into ResearchProject evidence.",
    ) -> dict[str, Any]:
        registry = self._load_registry()
        entry = registry.get("entries", {}).get(concept_id)
        if not entry:
            raise KfcPromotionStoreError(f"concept not found: {concept_id}", code="concept_not_found", status_code=404)
        before = dict(entry)
        project_ids = list(entry.get("linked_research_project_ids") or [])
        if project_id and project_id not in project_ids:
            project_ids.append(project_id)
            entry["linked_research_project_ids"] = project_ids
            entry["updated_at"] = _now_iso()
            entry["version"] = int(entry.get("version") or 1) + 1
            registry["entries"][concept_id] = entry
            self._save_registry(registry)

        existing_relation = next(
            (
                relation
                for relation in self._relations_for_concept(concept_id)
                if relation.get("source_type") == "concept_registry_entry"
                and relation.get("source_id") == concept_id
                and relation.get("target_type") == "research_project"
                and relation.get("target_id") == project_id
                and not relation.get("deleted")
            ),
            None,
        )
        now = _now_iso()
        relation = existing_relation or self._create_relation(
            source_type="concept_registry_entry",
            source_id=concept_id,
            target_type="research_project",
            target_id=project_id,
            relation_type="supports",
            cluster_id=(entry.get("linked_topic_cluster_ids") or [""])[0],
            project_id=project_id,
            promotion_id=entry.get("source_lead_id", ""),
            material_slice={
                "slice_id": entry.get("source_material_slice_id", ""),
                "source_article_id": entry.get("source_article_id", ""),
                "source_markdown_path": entry.get("source_markdown_path", ""),
                "source_content_hash": entry.get("source_content_hash", ""),
                "source_quote": entry.get("source_quote", ""),
                "source_context": entry.get("source_context", ""),
            },
            quality_state=entry.get("quality_state") or "machine_generated",
            review_state=entry.get("review_state") or "unreviewed",
            confidence=float(entry.get("confidence") or 0.72),
            now=now,
        )
        change = self._record_change(
            action="accept_local_evidence_candidate",
            actor=actor,
            cluster_id=(entry.get("linked_topic_cluster_ids") or [""])[0],
            source_ids={
                "concept_id": concept_id,
                "project_id": project_id,
                "evidence_id": evidence_id,
                "relation_id": relation.get("relation_id", ""),
                "source_article_id": entry.get("source_article_id", ""),
                "source_material_slice_id": entry.get("source_material_slice_id", ""),
                "source_lead_id": entry.get("source_lead_id", ""),
                "source_content_hash": entry.get("source_content_hash", ""),
            },
            before=before,
            after={"concept": entry, "relation": relation, "evidence_id": evidence_id},
            confidence=entry.get("confidence"),
            reason=reason,
        )
        return {"concept": entry, "relation": relation, "change": change}

    def _create_promotion_for_slice(self, material_slice: dict[str, Any], *, now: str) -> dict[str, Any]:
        promotion_id = _new_id("lp")
        promotion = {
            "promotion_id": promotion_id,
            "slice_id": material_slice["slice_id"],
            "lead_type": material_slice["slice_type"],
            "title": material_slice.get("title", ""),
            "summary": material_slice.get("summary", ""),
            "linked_topic_cluster": material_slice.get("linked_topic_cluster", ""),
            "linked_research_project": material_slice.get("linked_research_project", ""),
            "review_status": "pending",
            "decision": None,
            "target": None,
            "candidate": None,
            "action_history": [],
            "created_from": "material_slice",
            "created_by": material_slice.get("created_by", "human"),
            "created_at": now,
            "updated_at": now,
        }
        self._atomic_write(self._promotion_path(promotion_id), promotion)
        return promotion

    def _apply_link_existing(
        self,
        promotion: dict[str, Any],
        material_slice: dict[str, Any],
        payload: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        target = payload.get("target") or {}
        registry_entry_id = str(target.get("registry_entry_id") or target.get("target_id") or "").strip()
        if not registry_entry_id:
            raise KfcPromotionStoreError("target.registry_entry_id is required")
        registry_label = str(target.get("registry_entry_label") or target.get("target_label") or registry_entry_id).strip()
        confidence = self._confidence(payload, material_slice)
        relation = self._create_relation(
            source_type="material_slice",
            source_id=material_slice.get("slice_id", ""),
            target_type="concept_registry_entry",
            target_id=registry_entry_id,
            relation_type=_trim((payload.get("relation") or {}).get("relation_type") or "mention", 80),
            cluster_id=promotion.get("linked_topic_cluster", ""),
            project_id=promotion.get("linked_research_project", ""),
            promotion_id=promotion.get("promotion_id", ""),
            material_slice=material_slice,
            quality_state=_trim(payload.get("quality_state") or "human_confirmed", 80),
            review_state=_trim(payload.get("review_state") or "reviewed", 80),
            confidence=confidence,
            now=now,
        )
        self._record_change(
            action="link_lead_to_existing_concept",
            actor=_trim(payload.get("actor") or "human", 80),
            cluster_id=promotion.get("linked_topic_cluster", ""),
            source_ids=self._source_ids(promotion, material_slice, concept_id=registry_entry_id, relation_id=relation["relation_id"]),
            after={"target_id": registry_entry_id, "target_label": registry_label, "relation": relation},
            confidence=confidence,
            reason=_trim(payload.get("note") or "Lead linked to existing concept.", 500),
        )
        try:
            from .kfc_material_graph_store import KfcMaterialGraphStore

            KfcMaterialGraphStore(
                material_slice_dir=self.material_slice_dir,
                kfc_relation_dir=self.kfc_relation_dir,
                concept_registry_path=self.concept_registry_path,
            ).ensure_snapshot_for_concept(
                registry_entry_id,
                actor=_trim(payload.get("actor") or "human", 80),
                force=True,
            )
        except Exception:
            # The promotion link is the source of truth. The deterministic
            # graph snapshot can be refreshed later from the stored relation.
            pass
        return self._with_action(
            promotion,
            now,
            review_status="linked",
            decision="link_existing_registry_entry",
            target={
                "target_type": "concept_registry_entry",
                "target_id": registry_entry_id,
                "target_label": registry_label,
            },
            history_extra={
                "target_id": registry_entry_id,
                "target_label": registry_label,
                "relation_id": relation["relation_id"],
                "note": _trim(payload.get("note"), 500),
            },
        )

    def _apply_deposit_as_new_concept(
        self,
        promotion: dict[str, Any],
        material_slice: dict[str, Any],
        payload: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        existing_concept_id = ((promotion.get("concept") or {}).get("concept_id") or (promotion.get("target") or {}).get("target_id") or "")
        if existing_concept_id:
            registry = self._load_registry()
            existing = registry.get("entries", {}).get(existing_concept_id)
            if existing:
                self._record_change(
                    action="deposit_concept_idempotent",
                    actor=_trim(payload.get("actor") or payload.get("created_by") or "human", 80),
                    cluster_id=promotion.get("linked_topic_cluster", ""),
                    source_ids=self._source_ids(promotion, material_slice, concept_id=existing_concept_id),
                    after={"concept": existing, "promotion_id": promotion.get("promotion_id", "")},
                    confidence=existing.get("confidence"),
                    reason="Repeated deposit request returned the already materialized concept.",
                )
                return self._with_action(
                    promotion,
                    now,
                    review_status="materialized_concept",
                    decision="deposit_as_new_concept",
                    target={
                        "target_type": "concept_registry_entry",
                        "target_id": existing_concept_id,
                        "target_label": existing.get("canonical_name") or existing.get("label") or existing_concept_id,
                    },
                    concept={"concept_id": existing_concept_id, "asset_type": "concept"},
                    history_extra={"concept_id": existing_concept_id, "idempotent": True},
                )
        concept_payload = payload.get("concept") or payload.get("candidate") or {}
        label = _trim(concept_payload.get("label") or concept_payload.get("canonical_name") or promotion.get("title"), 200)
        if not label:
            raise KfcPromotionStoreError("concept.label is required")
        if self._looks_like_bad_concept_lead(label):
            raise KfcPromotionStoreError(
                "concept lead looks like a file name or low-quality title, not a concept",
                code="low_quality_concept_lead",
            )
        registry = self._load_registry()
        entries = registry.setdefault("entries", {})
        duplicate = self._find_registry_duplicate(registry, label, "Concept")
        if duplicate:
            self._record_change(
                action="deposit_concept_duplicate_rejected",
                actor=_trim(payload.get("actor") or payload.get("created_by") or "human", 80),
                cluster_id=promotion.get("linked_topic_cluster", ""),
                source_ids=self._source_ids(promotion, material_slice, concept_id=duplicate.get("entry_id", "")),
                after={"duplicate_concept": duplicate, "requested_label": label},
                confidence=self._confidence(payload, material_slice),
                reason="Deposit rejected because a matching active concept already exists.",
            )
            raise KfcPromotionStoreError(
                f"concept already exists: {duplicate.get('entry_id')}",
                code="duplicate_concept",
                status_code=409,
            )
        confidence = self._confidence(payload, material_slice)
        related_existing = self._related_registry_entries(registry, label, material_slice)
        concept_id = _new_id("canon")
        source_quote = material_slice.get("source_quote") or material_slice.get("source_excerpt") or promotion.get("summary", "")
        source_context = material_slice.get("source_context") or source_quote or material_slice.get("summary", "")
        digest_input_text = "\n".join(
            item
            for item in [
                f"Concept Lead: {label}",
                f"Article: {material_slice.get('source_title', '')}",
                f"Summary: {material_slice.get('summary', '')}",
                f"Quote: {source_quote}",
                f"Context: {source_context}",
            ]
            if item.split(":", 1)[-1].strip()
        )
        definition = _trim(
            concept_payload.get("definition") or concept_payload.get("description") or material_slice.get("summary") or source_quote,
            2000,
        )
        linked_research_project_ids = [
            item for item in [promotion.get("linked_research_project") or material_slice.get("linked_research_project")] if item
        ]
        concept = {
            "entry_id": concept_id,
            "concept_id": concept_id,
            "canonical_name": label,
            "label": label,
            "concept_type": "Concept",
            "asset_type": "concept",
            "aliases": [str(item)[:120] for item in (concept_payload.get("aliases") or []) if item],
            "definition": definition,
            "description": definition,
            "source_links": [],
            "lifecycle_status": "active",
            "quality_state": "machine_generated",
            "review_state": "unreviewed",
            "confidence": confidence,
            "created_from": _trim(payload.get("created_from") or "concept_lead", 80),
            "created_by": _trim(payload.get("created_by") or payload.get("actor") or "system", 80),
            "source_article_id": material_slice.get("source_article_id", ""),
            "source_markdown_path": material_slice.get("source_markdown_path", ""),
            "source_content_hash": material_slice.get("source_content_hash", ""),
            "source_quote": source_quote,
            "source_excerpt": material_slice.get("source_excerpt") or source_quote,
            "source_context": source_context,
            "source_article_title": material_slice.get("source_title", ""),
            "digest_input_text": digest_input_text,
            "digested_text": definition,
            "related_existing_concepts": related_existing,
            "source_lead_id": promotion.get("promotion_id", ""),
            "source_material_slice_id": material_slice.get("slice_id", ""),
            "linked_topic_cluster_ids": [promotion.get("linked_topic_cluster", "")],
            "linked_research_project_ids": linked_research_project_ids,
            "linked_wiki_topic_ids": [item for item in [material_slice.get("linked_wiki_topic", "")] if item],
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        entries[concept_id] = concept
        self._save_registry(registry)
        relations = [
            self._create_relation(
                source_type="article",
                source_id=material_slice.get("source_article_id", ""),
                target_type="concept_registry_entry",
                target_id=concept_id,
                relation_type="mentions",
                cluster_id=promotion.get("linked_topic_cluster", ""),
                project_id=promotion.get("linked_research_project", ""),
                promotion_id=promotion.get("promotion_id", ""),
                material_slice=material_slice,
                quality_state="machine_generated",
                review_state="unreviewed",
                confidence=confidence,
                now=now,
            ),
            self._create_relation(
                source_type="concept_registry_entry",
                source_id=concept_id,
                target_type="topic_cluster",
                target_id=promotion.get("linked_topic_cluster", ""),
                relation_type="belongs_to",
                cluster_id=promotion.get("linked_topic_cluster", ""),
                project_id="",
                promotion_id=promotion.get("promotion_id", ""),
                material_slice=material_slice,
                quality_state="machine_generated",
                review_state="unreviewed",
                confidence=confidence,
                now=now,
            ),
            self._create_relation(
                source_type="concept_registry_entry",
                source_id=concept_id,
                target_type="material_slice",
                target_id=material_slice.get("slice_id", ""),
                relation_type="created_from",
                cluster_id=promotion.get("linked_topic_cluster", ""),
                project_id=promotion.get("linked_research_project", ""),
                promotion_id=promotion.get("promotion_id", ""),
                material_slice=material_slice,
                quality_state="machine_generated",
                review_state="unreviewed",
                confidence=confidence,
                now=now,
            ),
        ]
        if linked_research_project_ids:
            relations.append(
                self._create_relation(
                    source_type="concept_registry_entry",
                    source_id=concept_id,
                    target_type="research_project",
                    target_id=linked_research_project_ids[0],
                    relation_type="supports",
                    cluster_id=promotion.get("linked_topic_cluster", ""),
                    project_id=linked_research_project_ids[0],
                    promotion_id=promotion.get("promotion_id", ""),
                    material_slice=material_slice,
                    quality_state="machine_generated",
                    review_state="unreviewed",
                    confidence=confidence,
                    now=now,
                )
            )
        for related in related_existing[:5]:
            relations.append(
                self._create_relation(
                    source_type="concept_registry_entry",
                    source_id=concept_id,
                    target_type="concept_registry_entry",
                    target_id=related["concept_id"],
                    relation_type="related_to",
                    cluster_id=promotion.get("linked_topic_cluster", ""),
                    project_id=linked_research_project_ids[0] if linked_research_project_ids else "",
                    promotion_id=promotion.get("promotion_id", ""),
                    material_slice=material_slice,
                    quality_state="machine_generated",
                    review_state="unreviewed",
                    confidence=min(float(related.get("score") or confidence), confidence),
                    now=now,
                )
            )
        self._record_change(
            action="create_concept_from_lead",
            actor=concept["created_by"],
            cluster_id=promotion.get("linked_topic_cluster", ""),
            source_ids=self._source_ids(
                promotion,
                material_slice,
                concept_id=concept_id,
                relation_ids=[item["relation_id"] for item in relations],
            ),
            after={"concept": concept, "relations": relations},
            confidence=confidence,
            reason=_trim(payload.get("note") or "Materialized Concept Lead into KFC concept asset.", 500),
        )
        try:
            from .kfc_material_graph_store import KfcMaterialGraphStore

            KfcMaterialGraphStore(
                material_slice_dir=self.material_slice_dir,
                kfc_relation_dir=self.kfc_relation_dir,
                concept_registry_path=self.concept_registry_path,
            ).ensure_snapshot_for_concept(concept_id, actor=concept["created_by"])
        except Exception:
            # Material graph snapshots are deterministic derived assets. A
            # snapshot failure must not roll back the already-reviewed concept
            # materialization; the graph endpoint can backfill later.
            pass
        return self._with_action(
            promotion,
            now,
            review_status="materialized_concept",
            decision="deposit_as_new_concept",
            target={"target_type": "concept_registry_entry", "target_id": concept_id, "target_label": label},
            concept={"concept_id": concept_id, "asset_type": "concept"},
            history_extra={
                "concept_id": concept_id,
                "label": label,
                "relation_ids": [item["relation_id"] for item in relations],
                "note": _trim(payload.get("note"), 500),
            },
        )

    def _apply_create_registry_candidate(
        self,
        promotion: dict[str, Any],
        material_slice: dict[str, Any],
        payload: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        candidate_payload = payload.get("candidate") or {}
        label = _trim(candidate_payload.get("label") or promotion.get("title"), 200)
        if not label:
            raise KfcPromotionStoreError("candidate.label is required")
        candidate_id = _new_id("crc")
        candidate = {
            "candidate_id": candidate_id,
            "candidate_type": "concept",
            "label": label,
            "proposed_key": _trim(candidate_payload.get("proposed_key") or self._slug(label), 120),
            "description": _trim(candidate_payload.get("description") or promotion.get("summary"), 2000),
            "aliases": [str(item)[:120] for item in (candidate_payload.get("aliases") or []) if item],
            "source_promotion_id": promotion["promotion_id"],
            "source_slice_id": promotion.get("slice_id", ""),
            "source_article_id": material_slice.get("source_article_id", ""),
            "source_markdown_path": material_slice.get("source_markdown_path", ""),
            "source_content_hash": material_slice.get("source_content_hash", ""),
            "linked_topic_cluster": promotion.get("linked_topic_cluster", ""),
            "review_status": "proposed",
            "created_from": "lead_promotion.create_new_registry_candidate",
            "created_by": "human",
            "created_at": now,
            "updated_at": now,
        }
        self._atomic_write(self._registry_candidate_path(candidate_id), candidate)
        self._record_change(
            action="create_registry_candidate_legacy",
            actor=_trim(payload.get("actor") or "human", 80),
            cluster_id=promotion.get("linked_topic_cluster", ""),
            source_ids=self._source_ids(promotion, material_slice, candidate_id=candidate_id),
            after={"candidate": candidate},
            confidence=self._confidence(payload, material_slice),
            reason="Legacy candidate sidecar created; main path should use deposit_as_new_concept.",
        )
        return self._with_action(
            promotion,
            now,
            review_status="candidate_created",
            decision="create_new_registry_candidate",
            candidate={"candidate_id": candidate_id, "candidate_type": "concept_registry_candidate"},
            history_extra={"candidate_id": candidate_id, "label": label, "note": _trim(payload.get("note"), 500)},
        )

    def _apply_add_project_evidence(
        self,
        promotion: dict[str, Any],
        material_slice: dict[str, Any],
        payload: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        target = payload.get("target") or {}
        project_id = str(target.get("research_project_id") or target.get("target_id") or "").strip()
        if not project_id:
            raise KfcPromotionStoreError("target.research_project_id is required")
        project = self.research_project_store.get(project_id)
        if project is None:
            raise KfcPromotionStoreError(
                f"research project not found: {project_id}",
                code="research_project_not_found",
                status_code=404,
            )
        evidence_payload = payload.get("evidence") or {}
        evidence_id = _new_id("ev")
        evidence_item = {
            "evidence_id": evidence_id,
            "evidence_type": _trim(evidence_payload.get("evidence_type") or "quote", 80),
            "title": _trim(evidence_payload.get("title") or promotion.get("title"), 200),
            "claim": _trim(evidence_payload.get("claim") or promotion.get("summary") or material_slice.get("summary"), 2000),
            "quote": material_slice.get("source_quote", ""),
            "summary": _trim(evidence_payload.get("summary") or material_slice.get("summary"), 2000),
            "status": "active",
            "quality_state": _trim(payload.get("quality_state") or "human_selected", 80),
            "review_state": _trim(payload.get("review_state") or "unreviewed", 80),
            "source_slice_id": material_slice.get("slice_id", ""),
            "linked_material_slice_id": material_slice.get("slice_id", ""),
            "source_promotion_id": promotion.get("promotion_id", ""),
            "linked_concept_lead_id": promotion.get("promotion_id", ""),
            "source_article_id": material_slice.get("source_article_id", ""),
            "source_markdown_path": material_slice.get("source_markdown_path", ""),
            "source_content_hash": material_slice.get("source_content_hash", ""),
            "source_quote": material_slice.get("source_quote", ""),
            "source_context": material_slice.get("source_context") or material_slice.get("source_quote", ""),
            "linked_concept_ids": list(evidence_payload.get("linked_concept_ids") or []),
            "topic_cluster_id": promotion.get("linked_topic_cluster", ""),
            "linked_topic_cluster": promotion.get("linked_topic_cluster", ""),
            "created_from": "lead_promotion.add_as_project_evidence",
            "created_by": _trim(payload.get("actor") or "human", 80),
            "created_at": now,
        }
        existing = [
            item for item in list(project.evidence_items or [])
            if item.get("source_promotion_id") != promotion.get("promotion_id")
        ]
        existing.append(evidence_item)
        project.evidence_items = existing
        project.updated_at = now
        try:
            self.research_project_store.save(project)
        except (OSError, ResearchProjectStoreError) as exc:
            raise KfcPromotionStoreError(str(exc), code="research_project_write_failed", status_code=500) from exc
        self._record_change(
            action="add_lead_as_project_evidence",
            actor=evidence_item["created_by"],
            cluster_id=promotion.get("linked_topic_cluster", ""),
            source_ids=self._source_ids(promotion, material_slice, evidence_id=evidence_id, project_id=project_id),
            after={"evidence": evidence_item},
            confidence=self._confidence(payload, material_slice),
            reason=_trim(payload.get("note") or "Material Slice added as ResearchProject evidence.", 500),
        )
        return self._with_action(
            promotion,
            now,
            review_status="added_to_project_evidence",
            decision="add_as_project_evidence",
            target={
                "target_type": "research_project",
                "target_id": project_id,
                "evidence_item_id": evidence_id,
            },
            history_extra={"target_id": project_id, "evidence_item_id": evidence_id, "note": _trim(payload.get("note"), 500)},
        )

    def _apply_quote_review(
        self,
        promotion: dict[str, Any],
        material_slice: dict[str, Any],
        payload: dict[str, Any],
        now: str,
        *,
        action: str,
    ) -> dict[str, Any]:
        requested_status = _trim(payload.get("quote_status") or payload.get("status"), 80)
        if action == "replace_quote":
            requested_status = "replaced" if payload.get("replacement_quote") else "replace_requested"
        if requested_status not in QUOTE_REVIEW_STATUSES:
            raise KfcPromotionStoreError(f"quote status must be one of {sorted(QUOTE_REVIEW_STATUSES)}")
        before = dict(promotion)
        quote_review = {
            "status": requested_status,
            "note": _trim(payload.get("note") or payload.get("reason"), 500),
            "replacement_quote": _trim(payload.get("replacement_quote"), 1000),
            "replacement_context": _trim(payload.get("replacement_context"), 2000),
            "actor": _trim(payload.get("actor") or "human", 80),
            "updated_at": now,
        }
        history_extra = {
            "quote_status": quote_review["status"],
            "note": quote_review["note"],
        }
        if quote_review["replacement_quote"]:
            history_extra["replacement_quote"] = quote_review["replacement_quote"]
        updated = self._with_action(
            promotion,
            now,
            review_status=promotion.get("review_status") or "pending",
            decision=action,
            target=promotion.get("target"),
            candidate=promotion.get("candidate"),
            concept=promotion.get("concept"),
            history_extra=history_extra,
        )
        updated["quote_review"] = quote_review
        self._record_change(
            action="quote_review_updated",
            actor=quote_review["actor"],
            cluster_id=promotion.get("linked_topic_cluster", ""),
            source_ids=self._source_ids(promotion, material_slice),
            before=before,
            after={
                "quote_review": quote_review,
                "original_quote_preserved": material_slice.get("source_quote", ""),
            },
            confidence=self._confidence(payload, material_slice),
            reason=quote_review["note"] or f"Quote marked {quote_review['status']}.",
        )
        return updated

    def _apply_review_marker(
        self,
        promotion: dict[str, Any],
        material_slice: dict[str, Any],
        payload: dict[str, Any],
        now: str,
        *,
        action: str,
    ) -> dict[str, Any]:
        before = dict(promotion)
        review_status = "confirmed" if action == "confirm_review" else "reviewed"
        updated = self._with_action(
            promotion,
            now,
            review_status=review_status,
            decision=action,
            target=promotion.get("target"),
            candidate=promotion.get("candidate"),
            concept=promotion.get("concept"),
            history_extra={
                "batch_id": _trim(payload.get("batch_id"), 120),
                "note": _trim(payload.get("note") or payload.get("reason"), 500),
            },
            actor=_trim(payload.get("actor") or "human", 80),
        )
        self._record_change(
            action=action,
            actor=_trim(payload.get("actor") or "human", 80),
            cluster_id=promotion.get("linked_topic_cluster", ""),
            source_ids=self._source_ids(promotion, material_slice),
            before=before,
            after={"promotion": updated},
            confidence=self._confidence(payload, material_slice),
            reason=_trim(payload.get("note") or f"Article review {review_status}.", 500),
        )
        return updated

    def _apply_ignore(
        self,
        promotion: dict[str, Any],
        material_slice: dict[str, Any],
        payload: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        reason = _trim(payload.get("reason") or payload.get("note"), 500)
        self._record_change(
            action="ignore_lead",
            actor=_trim(payload.get("actor") or "human", 80),
            cluster_id=promotion.get("linked_topic_cluster", ""),
            source_ids=self._source_ids(promotion, material_slice),
            after={"review_decision": {"action": "ignore_lead", "reason": reason, "timestamp": now}},
            reason=reason,
        )
        return self._with_action(
            promotion,
            now,
            review_status="ignored",
            decision="ignore",
            target=None,
            history_extra={"reason": reason},
        )

    def _apply_deprecate_materialized_concept(
        self,
        promotion: dict[str, Any],
        payload: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        concept_id = ((promotion.get("concept") or {}).get("concept_id") or (promotion.get("target") or {}).get("target_id") or "")
        if not concept_id:
            raise KfcPromotionStoreError("promotion has no materialized concept")
        self.deprecate_concept(concept_id, payload, actor=_trim(payload.get("actor") or "human", 80))
        return self._with_action(
            promotion,
            now,
            review_status="deprecated",
            decision="deprecate_materialized_concept",
            target=promotion.get("target"),
            concept=promotion.get("concept"),
            history_extra={"concept_id": concept_id, "reason": _trim(payload.get("reason") or payload.get("note"), 500)},
        )

    def _apply_unlink_promotion_target(
        self,
        promotion: dict[str, Any],
        payload: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        concept_id = ((promotion.get("concept") or {}).get("concept_id") or (promotion.get("target") or {}).get("target_id") or "")
        if not concept_id:
            raise KfcPromotionStoreError("promotion has no target concept")
        removed = self.unlink_concept_relation(
            concept_id,
            target_type=payload.get("target_type"),
            target_id=payload.get("target_id"),
            actor=_trim(payload.get("actor") or "human", 80),
        )
        return self._with_action(
            promotion,
            now,
            review_status="unlinked",
            decision="unlink_promotion_target",
            target=promotion.get("target"),
            concept=promotion.get("concept"),
            history_extra={"concept_id": concept_id, "removed_relation_count": len(removed.get("removed") or [])},
        )

    def _with_action(
        self,
        promotion: dict[str, Any],
        now: str,
        *,
        review_status: str,
        decision: str,
        target: dict[str, Any] | None = None,
        candidate: dict[str, Any] | None = None,
        concept: dict[str, Any] | None = None,
        history_extra: dict[str, Any] | None = None,
        actor: str = "human",
    ) -> dict[str, Any]:
        history = list(promotion.get("action_history") or [])
        history.append(
            {
                "action_id": _new_id("act"),
                "action": decision,
                "actor": actor,
                "created_at": now,
                **(history_extra or {}),
            }
        )
        updated = {
            **promotion,
            "review_status": review_status,
            "decision": decision,
            "action_history": history,
            "updated_at": now,
        }
        if target is not None or decision in {"link_existing_registry_entry", "add_as_project_evidence", "ignore"}:
            updated["target"] = target
        if candidate is not None:
            updated["candidate"] = candidate
        if concept is not None:
            updated["concept"] = concept
        return updated

    def _basket_item(self, promotion: dict[str, Any], material_slice: dict[str, Any]) -> dict[str, Any]:
        concept_id = ((promotion.get("concept") or {}).get("concept_id") or "")
        concept = self._load_registry().get("entries", {}).get(concept_id) if concept_id else None
        return {
            "promotion_id": promotion.get("promotion_id", ""),
            "slice_id": promotion.get("slice_id", ""),
            "lead_type": promotion.get("lead_type", ""),
            "title": promotion.get("title", ""),
            "display_title": material_slice.get("display_title") or promotion.get("title", ""),
            "summary": promotion.get("summary", ""),
            "source_quote": material_slice.get("source_quote", ""),
            "source_excerpt": material_slice.get("source_excerpt", ""),
            "source_context": material_slice.get("source_context", ""),
            "extraction_reason": material_slice.get("extraction_reason", ""),
            "confidence": material_slice.get("confidence"),
            "recommended_action": material_slice.get("recommended_action", ""),
            "why_this_is_a_concept": material_slice.get("why_this_is_a_concept", ""),
            "risk": material_slice.get("risk") or [],
            "alternative_matches": material_slice.get("alternative_matches") or [],
            "quote_review": promotion.get("quote_review") or {},
            "action_history": promotion.get("action_history") or [],
            "source": {
                "source_material_slice_id": material_slice.get("slice_id", ""),
                "source_article_id": material_slice.get("source_article_id", ""),
                "source_title": material_slice.get("source_title", ""),
                "source_markdown_path": material_slice.get("source_markdown_path", ""),
                "source_content_hash": material_slice.get("source_content_hash", ""),
                "source_url": material_slice.get("source_url", ""),
                "linked_wiki_topic": material_slice.get("linked_wiki_topic", ""),
            },
            "linked_topic_cluster": promotion.get("linked_topic_cluster", ""),
            "linked_research_project": promotion.get("linked_research_project", ""),
            "review_status": promotion.get("review_status", "pending"),
            "decision": promotion.get("decision"),
            "target": promotion.get("target"),
            "candidate": promotion.get("candidate"),
            "concept": promotion.get("concept"),
            "materialized_concept": concept,
            "created_at": promotion.get("created_at", ""),
            "updated_at": promotion.get("updated_at", ""),
        }

    def _validate_slice_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise KfcPromotionStoreError("JSON body must be an object")
        slice_type = str(payload.get("slice_type") or "").strip()
        if slice_type not in SLICE_TYPES:
            raise KfcPromotionStoreError(f"slice_type must be one of {sorted(SLICE_TYPES)}")
        title = _trim(payload.get("title"), 200)
        if not title:
            raise KfcPromotionStoreError("title is required")
        if slice_type == "concept_lead" and self._looks_like_bad_concept_lead(title):
            raise KfcPromotionStoreError(
                "concept lead looks like a file name or low-quality title, not a concept",
                code="low_quality_concept_lead",
            )
        source_span = payload.get("source_span") or {}
        if not isinstance(source_span, dict):
            raise KfcPromotionStoreError("source_span must be an object when provided")
        confidence = payload.get("confidence")
        if confidence is not None and not isinstance(confidence, (int, float)):
            raise KfcPromotionStoreError("confidence must be a number")
        if isinstance(confidence, (int, float)) and not 0 <= confidence <= 1:
            raise KfcPromotionStoreError("confidence must be between 0 and 1")
        clean = {
            "slice_type": slice_type,
            "title": title,
            "display_title": _trim(payload.get("display_title") or title, 220),
            "summary": _trim(payload.get("summary"), 2000),
            "source_quote": _trim(payload.get("source_quote"), 1000),
            "source_excerpt": _trim(payload.get("source_excerpt"), 1200),
            "source_context": _trim(payload.get("source_context"), 2000),
            "source_span": source_span,
            "source_article_id": _trim(payload.get("source_article_id"), 200),
            "source_markdown_path": str(payload.get("source_markdown_path") or ""),
            "source_content_hash": _trim(payload.get("source_content_hash"), 200),
            "source_title": _trim(payload.get("source_title"), 300),
            "source_url": str(payload.get("source_url") or ""),
            "linked_wiki_topic": _trim(payload.get("linked_wiki_topic"), 160),
            "linked_research_project": _trim(payload.get("linked_research_project"), 160),
            "extraction_reason": _trim(payload.get("extraction_reason") or "来自 Wiki 粗加工的概念/证据线索。", 500),
            "confidence": confidence if confidence is not None else 0.72,
            "recommended_action": _trim(payload.get("recommended_action"), 120),
            "why_this_is_a_concept": _trim(payload.get("why_this_is_a_concept"), 1000),
            "risk": [str(item)[:300] for item in (payload.get("risk") or []) if item] if isinstance(payload.get("risk") or [], list) else [],
            "alternative_matches": self._clean_alternative_matches(payload.get("alternative_matches")),
            "created_from": _trim(payload.get("created_from") or "topic_cluster_detail", 200),
            "created_by": _trim(payload.get("created_by") or "human", 80),
            "create_promotion": payload.get("create_promotion", True) is not False,
        }
        if not clean["source_quote"] and not clean["source_excerpt"] and not clean["source_context"] and not clean["source_span"] and not clean["summary"]:
            raise KfcPromotionStoreError("source_quote, source_excerpt, source_context, source_span, or summary is required")
        return clean

    def _require_cluster(self, cluster_id: str) -> None:
        self._validate_identifier(cluster_id, "cluster_id")
        if self.topic_cluster_store.get_cluster(cluster_id) is None:
            raise KfcPromotionStoreError(
                f"topic cluster not found: {cluster_id}",
                code="topic_cluster_not_found",
                status_code=404,
            )

    def _validate_identifier(self, value: str, field: str) -> None:
        if not _SAFE_ID_PATTERN.match(value or ""):
            raise KfcPromotionStoreError(f"invalid {field}: {value}", code=f"invalid_{field}")

    def _list_json(self, directory: Path, pattern: str) -> list[dict[str, Any]]:
        if not directory.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in sorted(directory.glob(pattern)):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise KfcPromotionStoreError(f"invalid JSON sidecar: {path}") from exc
            if isinstance(payload, dict):
                items.append(payload)
        return items

    def _read_optional(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KfcPromotionStoreError(f"invalid JSON sidecar: {path}") from exc
        return payload if isinstance(payload, dict) else None

    def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def _slice_path(self, slice_id: str) -> Path:
        return self.material_slice_dir / f"{slice_id}.json"

    def _promotion_path(self, promotion_id: str) -> Path:
        return self.lead_promotion_dir / f"{promotion_id}.json"

    def _registry_candidate_path(self, candidate_id: str) -> Path:
        return self.concept_registry_candidate_dir / f"{candidate_id}.json"

    def _relation_path(self, relation_id: str) -> Path:
        return self.kfc_relation_dir / f"{relation_id}.json"

    def _relation_candidate_path(self, relation_candidate_id: str) -> Path:
        return self.relation_candidate_dir / f"{relation_candidate_id}.json"

    def _change_log_path(self) -> Path:
        return self.kfc_change_log_dir / "kfc_changes.jsonl"

    def _clean_alternative_matches(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        items: list[dict[str, Any]] = []
        for raw in value[:5]:
            if not isinstance(raw, dict):
                continue
            concept_id = _trim(raw.get("concept_id") or raw.get("entry_id") or raw.get("target_id"), 200)
            concept_name = _trim(raw.get("concept_name") or raw.get("canonical_name") or raw.get("label") or raw.get("target_label"), 200)
            reason = _trim(raw.get("reason") or raw.get("match_reason"), 500)
            if concept_id or concept_name:
                items.append({"concept_id": concept_id, "concept_name": concept_name, "reason": reason})
        return items

    def _list_relation_candidates(self, cluster_id: str) -> list[dict[str, Any]]:
        return [
            item
            for item in self._list_json(self.relation_candidate_dir, "relcand_*.json")
            if item.get("linked_topic_cluster") == cluster_id
        ]

    def _candidate_card_from_promotion(self, item: dict[str, Any]) -> dict[str, Any]:
        lead_type = item.get("lead_type") or "concept_lead"
        candidate_type = "evidence_lead" if lead_type == "evidence_slice" else "concept_lead"
        status = item.get("review_status") or "pending"
        quote_status = (item.get("quote_review") or {}).get("status") or ""
        risk_flags = list(item.get("risk") or [])
        if quote_status in {"weak", "wrong", "needs_verification", "replace_requested"}:
            risk_flags.append(f"quote:{quote_status}")
        if isinstance(item.get("confidence"), (int, float)) and item["confidence"] < 0.7:
            risk_flags.append("low_confidence")
        return {
            "candidate_id": item.get("promotion_id", ""),
            "candidate_type": candidate_type,
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "status": status,
            "quality_state": quote_status or ("needs_review" if risk_flags else "normal"),
            "recommended_action": item.get("recommended_action") or self._default_recommended_action(item),
            "recommended_match": item.get("target") or {},
            "alternative_matches": (item.get("alternative_matches") or [])[:3],
            "quote": item.get("source_quote", ""),
            "context": item.get("source_context") or item.get("source_excerpt") or "",
            "why": item.get("why_this_is_a_concept") or item.get("extraction_reason") or "",
            "confidence": item.get("confidence"),
            "risk_flags": risk_flags,
            "source": item.get("source") or {},
            "review_trail": item.get("action_history") or [],
            "quote_review": item.get("quote_review") or {},
        }

    def _candidate_card_from_relation_candidate(self, item: dict[str, Any]) -> dict[str, Any]:
        status = item.get("review_status") or "pending_review"
        risk_flags = []
        if status == "needs_revision":
            risk_flags.append("relation_type_needs_revision")
        if isinstance(item.get("confidence"), (int, float)) and item["confidence"] < 0.7:
            risk_flags.append("low_confidence")
        return {
            "candidate_id": item.get("relation_candidate_id", ""),
            "candidate_type": "relation_candidate",
            "title": f"{item.get('subject_concept', '')} - {item.get('relation_type', '')} - {item.get('object_concept', '')}",
            "summary": item.get("why_relation_exists", ""),
            "status": status,
            "quality_state": "needs_review" if risk_flags else "normal",
            "subject_concept": item.get("subject_concept", ""),
            "relation_type": item.get("relation_type", ""),
            "object_concept": item.get("object_concept", ""),
            "alternative_relation_types": item.get("possible_alternative_relation_types") or [],
            "quote": item.get("source_quote", ""),
            "context": item.get("source_context", ""),
            "why": item.get("why_relation_exists", ""),
            "confidence": item.get("confidence"),
            "risk_flags": risk_flags,
            "source": {
                "source_article_id": item.get("source_article_id", ""),
                "source_title": item.get("source_title", ""),
                "source_markdown_path": item.get("source_markdown_path", ""),
                "source_content_hash": item.get("source_content_hash", ""),
            },
            "review_trail": item.get("action_history") or [],
        }

    def _enrich_article_review_card(self, card: dict[str, Any]) -> dict[str, Any]:
        candidate_type = card.get("candidate_type") or ""
        status = card.get("status") or "pending"
        confidence = card.get("confidence")
        confidence_bucket = self._confidence_bucket(confidence)
        risk_flags = self._dedupe_strings(card.get("risk_flags") or [])
        alternative_matches = card.get("alternative_matches") or []
        relation_type_suggestions = card.get("alternative_relation_types") or []
        quote = _trim(card.get("quote"), 1000)
        quote_status = ((card.get("quote_review") or {}).get("status") or "").strip()
        processed = status in PROCESSED_REVIEW_STATUSES
        if alternative_matches and candidate_type == "concept_lead":
            risk_flags.append("registry_alternative_available")
            if len(alternative_matches) > 1:
                risk_flags.append("duplicate_concept_possible")
        if candidate_type in {"concept_lead", "evidence_lead"}:
            if not quote:
                risk_flags.append("weak_quote")
            if quote_status in {"weak", "wrong", "needs_verification", "replace_requested"}:
                risk_flags.append("weak_quote")
            if confidence_bucket == "low":
                risk_flags.append("low_confidence_match")
        if candidate_type == "relation_candidate":
            if relation_type_suggestions:
                risk_flags.append("ambiguous_relation_type")
            if not card.get("subject_concept") or not card.get("object_concept"):
                risk_flags.append("relation_target_missing")
            if not quote:
                risk_flags.append("weak_quote")
            if confidence_bucket == "low":
                risk_flags.append("low_confidence_match")
        source = card.get("source") or {}
        if not source.get("source_content_hash") and not source.get("source_markdown_path"):
            risk_flags.append("missing_source_slice")
        if processed:
            risk_flags.append("reviewer_changed")
        risk_flags = self._dedupe_strings(risk_flags)
        needs_quote_review = any(flag in risk_flags for flag in {"weak_quote", "quote:weak", "quote:wrong", "quote:needs_verification", "quote:replace_requested"})
        group_ids = self._article_review_group_ids(
            candidate_type=candidate_type,
            status=status,
            confidence_bucket=confidence_bucket,
            risk_flags=risk_flags,
            needs_quote_review=needs_quote_review,
            processed=processed,
        )
        batch_action_types = self._batch_action_types_for_card(
            candidate_type=candidate_type,
            status=status,
            confidence_bucket=confidence_bucket,
            risk_flags=risk_flags,
            group_ids=group_ids,
        )
        latest = self._latest_review_event(card.get("review_trail") or [])
        original_snapshot = {
            "title": card.get("title", ""),
            "summary": card.get("summary", ""),
            "quote": quote,
            "relation_type": card.get("relation_type", ""),
            "status": "pending_review" if candidate_type == "relation_candidate" else "pending",
        }
        quote_review = card.get("quote_review") or {}
        current_snapshot = {
            "title": card.get("title", ""),
            "quote": quote_review.get("replacement_quote") or quote,
            "quote_status": quote_review.get("status") or "",
            "relation_type": card.get("relation_type", ""),
            "status": status,
        }
        return {
            **card,
            "card_id": card.get("candidate_id", ""),
            "candidate_kind": self._candidate_kind(candidate_type),
            "review_status": status,
            "confidence_bucket": confidence_bucket,
            "confidence_band": confidence_bucket,
            "risk_flags": risk_flags,
            "risk_flag_details": [self._risk_flag_detail(flag) for flag in risk_flags],
            "needs_quote_review": needs_quote_review,
            "has_alternative_matches": bool(alternative_matches),
            "has_relation_type_suggestion": bool(relation_type_suggestions),
            "review_group_ids": group_ids,
            "batch_eligible": bool(batch_action_types),
            "batch_action_types": batch_action_types,
            "original_snapshot": original_snapshot,
            "current_snapshot": current_snapshot,
            "current_review_state": {
                "latest_action_id": latest.get("action_id", ""),
                "latest_action_type": latest.get("action", ""),
                "reviewer": latest.get("actor", ""),
                "updated_at": latest.get("created_at", ""),
                "batch_id": latest.get("batch_id", ""),
            },
            "display": {
                "title": card.get("title", ""),
                "subtitle": card.get("summary", ""),
                "why": card.get("why", ""),
                "quote": quote,
                "context": card.get("context", ""),
            },
            "relation": {
                "source_label": card.get("subject_concept", ""),
                "target_label": card.get("object_concept", ""),
                "relation_type": card.get("relation_type", ""),
                "evidence_quote": quote,
                "source_slice_id": source.get("source_material_slice_id") or source.get("source_article_id") or "",
                "rationale": card.get("why", "") or card.get("summary", ""),
            } if candidate_type == "relation_candidate" else {},
        }

    def _article_review_group_ids(
        self,
        *,
        candidate_type: str,
        status: str,
        confidence_bucket: str,
        risk_flags: list[str],
        needs_quote_review: bool,
        processed: bool,
    ) -> list[str]:
        if processed:
            return ["processed"]
        group_ids = ["pending_review"]
        if (
            candidate_type in {"concept_lead", "evidence_lead"}
            and confidence_bucket == "high"
            and not self._has_blocking_risk(risk_flags)
        ):
            group_ids.append("high_confidence_quick_confirm")
        if confidence_bucket == "low" or any(flag in risk_flags for flag in {"low_confidence_match", "ambiguous_relation_type", "duplicate_concept_possible"}):
            group_ids.append("low_confidence_manual_judgment")
        if needs_quote_review:
            group_ids.append("weak_quote_review")
        if candidate_type == "relation_candidate" and status in {"pending_review", "needs_revision", "pending"}:
            group_ids.append("relation_pending")
        return self._dedupe_strings(group_ids)

    def _article_review_groups(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups = []
        for group in ARTICLE_REVIEW_GROUPS:
            group_id = group["group_id"]
            card_ids = [
                card.get("card_id") or card.get("candidate_id")
                for card in cards
                if group_id in (card.get("review_group_ids") or [])
            ]
            groups.append({**group, "count": len(card_ids), "card_ids": card_ids})
        return groups

    def _article_review_trail(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for card in cards:
            for event in card.get("review_trail") or []:
                action_type = event.get("action", "")
                before: dict[str, Any] = {"status": (card.get("original_snapshot") or {}).get("status", "")}
                after: dict[str, Any] = {"status": card.get("status", "")}
                if "quote" in action_type or event.get("quote_status"):
                    before["quote"] = (card.get("original_snapshot") or {}).get("quote", "")
                    after["quote"] = (card.get("current_snapshot") or {}).get("quote", "")
                    after["quote_status"] = event.get("quote_status") or (card.get("quote_review") or {}).get("status", "")
                if "relation" in action_type or event.get("relation_type_before") or event.get("relation_type_after"):
                    before["relation_type"] = event.get("relation_type_before") or (card.get("original_snapshot") or {}).get("relation_type", "")
                    after["relation_type"] = event.get("relation_type_after") or card.get("relation_type", "")
                items.append(
                    {
                        "action_id": event.get("action_id", ""),
                        "batch_id": event.get("batch_id", ""),
                        "card_id": card.get("card_id") or card.get("candidate_id", ""),
                        "candidate_type": card.get("candidate_type", ""),
                        "action_type": action_type,
                        "reviewer": event.get("actor", ""),
                        "timestamp": event.get("created_at", ""),
                        "note": event.get("note") or event.get("reason") or "",
                        "before": before,
                        "after": after,
                        "source_article_id": (card.get("source") or {}).get("source_article_id", ""),
                    }
                )
        items.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return items[:30]

    def _batch_action_types_for_card(
        self,
        *,
        candidate_type: str,
        status: str,
        confidence_bucket: str,
        risk_flags: list[str],
        group_ids: list[str],
    ) -> list[str]:
        if status in PROCESSED_REVIEW_STATUSES:
            return []
        if candidate_type == "concept_lead" and "high_confidence_quick_confirm" in group_ids:
            return ["confirm_high_confidence_concepts"]
        if candidate_type == "evidence_lead" and confidence_bucket in {"high", "medium"} and not self._has_blocking_risk(risk_flags):
            return ["mark_evidence_reviewed"]
        if candidate_type == "relation_candidate" and (
            confidence_bucket == "low" or "weak_quote" in risk_flags or "relation_target_missing" in risk_flags
        ):
            return ["reject_weak_relations"]
        return []

    def _article_completion_status(
        self,
        total: int,
        processed_count: int,
        unresolved_risk_count: int,
        relation_pending_count: int,
        quote_issues_pending: int,
    ) -> dict[str, Any]:
        if total == 0:
            return {"status_code": "not_started", "status_label": "未开始", "can_finish": False, "is_completed_marker": False}
        pending = total - processed_count
        if pending <= 0 and unresolved_risk_count == 0:
            return {"status_code": "ready_to_finish", "status_label": "可完成", "can_finish": True, "is_completed_marker": False}
        if relation_pending_count or quote_issues_pending or unresolved_risk_count:
            return {"status_code": "at_risk", "status_label": "有风险待处理", "can_finish": False, "is_completed_marker": False}
        return {"status_code": "in_review", "status_label": "审核中", "can_finish": False, "is_completed_marker": False}

    def _confidence_bucket(self, value: Any) -> str:
        if not isinstance(value, (int, float)):
            return "unknown"
        if value >= 0.8:
            return "high"
        if value >= 0.65:
            return "medium"
        return "low"

    def _candidate_kind(self, candidate_type: str) -> str:
        if candidate_type == "concept_lead":
            return "concept"
        if candidate_type == "evidence_lead":
            return "evidence"
        if candidate_type == "relation_candidate":
            return "relation"
        return candidate_type or "candidate"

    def _has_blocking_risk(self, risk_flags: list[str]) -> bool:
        blocking = {
            "weak_quote",
            "missing_source_slice",
            "low_confidence_match",
            "ambiguous_relation_type",
            "relation_target_missing",
            "quote:weak",
            "quote:wrong",
            "quote:needs_verification",
            "quote:replace_requested",
        }
        return any(flag in blocking for flag in risk_flags)

    def _risk_flag_detail(self, flag: str) -> dict[str, str]:
        labels = {
            "duplicate_concept_possible": ("可能重复概念", "warning"),
            "weak_quote": ("引文需核对", "warning"),
            "missing_source_slice": ("来源切片不足", "danger"),
            "low_confidence_match": ("低置信匹配", "warning"),
            "ambiguous_relation_type": ("关系类型待判断", "warning"),
            "relation_target_missing": ("关系端点缺失", "danger"),
            "registry_alternative_available": ("存在备选匹配", "info"),
            "already_linked": ("已关联", "info"),
            "reviewer_changed": ("Reviewer 已改动", "info"),
        }
        label, severity = labels.get(flag, (flag, "warning" if "quote" in flag or "low" in flag else "info"))
        return {"code": flag, "label": label, "severity": severity, "reason": label}

    def _latest_review_event(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {}
        return sorted(events, key=lambda event: event.get("created_at", ""))[-1]

    def _dedupe_strings(self, values: list[Any]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            text = _trim(value, 160)
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    def _default_recommended_action(self, item: dict[str, Any]) -> str:
        if item.get("lead_type") == "evidence_slice":
            return "review_evidence_quote"
        if item.get("alternative_matches"):
            return "select_best_registry_match"
        return "confirm_or_deposit_concept_lead"

    def _slug(self, label: str) -> str:
        value = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", label.strip().lower()).strip("-")
        return value[:80] or "concept-candidate"

    def _load_registry(self) -> dict[str, Any]:
        if not self.concept_registry_path.exists():
            return {"version": 1, "entries": {}}
        try:
            payload = json.loads(self.concept_registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KfcPromotionStoreError("concept registry JSON is corrupted", status_code=500) from exc
        if not isinstance(payload, dict):
            raise KfcPromotionStoreError("concept registry must be an object", status_code=500)
        payload.setdefault("version", 1)
        payload.setdefault("entries", {})
        return payload

    def _save_registry(self, registry: dict[str, Any]) -> None:
        self._atomic_write(self.concept_registry_path, registry)

    def _find_registry_duplicate(self, registry: dict[str, Any], label: str, concept_type: str) -> dict[str, Any] | None:
        norm = normalize_concept_name(label)
        for entry in registry.get("entries", {}).values():
            if (
                normalize_concept_name(entry.get("canonical_name") or entry.get("label") or "") == norm
                and entry.get("concept_type", "Concept") == concept_type
                and entry.get("lifecycle_status") not in {"deleted_soft"}
            ):
                return entry
        return None

    def _related_registry_entries(
        self,
        registry: dict[str, Any],
        label: str,
        material_slice: dict[str, Any],
    ) -> list[dict[str, Any]]:
        haystack = " ".join(
            str(value or "")
            for value in [
                label,
                material_slice.get("summary"),
                material_slice.get("source_quote"),
                material_slice.get("source_excerpt"),
                material_slice.get("source_context"),
                material_slice.get("source_title"),
            ]
        ).lower()
        related = []
        for entry in registry.get("entries", {}).values():
            entry_id = str(entry.get("entry_id") or entry.get("concept_id") or "")
            if not entry_id or entry.get("lifecycle_status") in {"deleted_soft", "deprecated"}:
                continue
            names = [
                str(entry.get("canonical_name") or ""),
                str(entry.get("label") or ""),
                *[str(alias or "") for alias in (entry.get("aliases") or [])],
            ]
            hits = [name for name in names if name and name.lower() in haystack]
            if not hits:
                continue
            related.append(
                {
                    "concept_id": entry_id,
                    "label": entry.get("canonical_name") or entry.get("label") or entry_id,
                    "match_reason": f"source_text_mentions_existing_concept:{hits[0]}",
                    "score": 0.74,
                }
            )
        return related[:10]

    def _create_relation(
        self,
        *,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relation_type: str,
        cluster_id: str,
        project_id: str,
        promotion_id: str,
        material_slice: dict[str, Any],
        quality_state: str,
        review_state: str,
        confidence: float,
        now: str,
    ) -> dict[str, Any]:
        relation_id = _new_id("rel")
        relation = {
            "relation_id": relation_id,
            "source_type": source_type,
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "relation_type": relation_type,
            "cluster_id": cluster_id,
            "project_id": project_id,
            "promotion_id": promotion_id,
            "source_article_id": material_slice.get("source_article_id", ""),
            "source_markdown_path": material_slice.get("source_markdown_path", ""),
            "source_content_hash": material_slice.get("source_content_hash", ""),
            "source_quote": material_slice.get("source_quote", ""),
            "source_context": material_slice.get("source_context") or material_slice.get("source_quote", ""),
            "source_lead_id": promotion_id,
            "source_material_slice_id": material_slice.get("slice_id", ""),
            "quality_state": quality_state,
            "review_state": review_state,
            "confidence": confidence,
            "created_at": now,
            "updated_at": now,
        }
        self._atomic_write(self._relation_path(relation_id), relation)
        return relation

    def _relations_for_promotion(self, promotion_id: str) -> list[dict[str, Any]]:
        return [
            relation
            for relation in self._list_json(self.kfc_relation_dir, "rel_*.json")
            if relation.get("promotion_id") == promotion_id and not relation.get("deleted")
        ]

    def _relations_for_concept(self, concept_id: str) -> list[dict[str, Any]]:
        return [
            relation
            for relation in self._list_json(self.kfc_relation_dir, "rel_*.json")
            if concept_id in {relation.get("source_id"), relation.get("target_id")} and not relation.get("deleted")
        ]

    def _record_change(
        self,
        *,
        action: str,
        actor: str,
        cluster_id: str,
        source_ids: dict[str, Any],
        after: dict[str, Any],
        reason: str,
        confidence: float | None = None,
        before: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "change_id": _new_id("chg"),
            "action": action,
            "actor": actor,
            "timestamp": _now_iso(),
            "cluster_id": cluster_id,
            "source_ids": source_ids,
            "before": before,
            "after": after,
            "confidence": confidence,
            "reason": reason,
        }
        path = self._change_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def _read_change_log(self) -> list[dict[str, Any]]:
        path = self._change_log_path()
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    def _source_ids(self, promotion: dict[str, Any], material_slice: dict[str, Any], **extra: Any) -> dict[str, Any]:
        ids = {
            "source_article_id": material_slice.get("source_article_id", ""),
            "source_material_slice_id": material_slice.get("slice_id", ""),
            "source_lead_id": promotion.get("promotion_id", ""),
            "source_markdown_path": material_slice.get("source_markdown_path", ""),
            "source_content_hash": material_slice.get("source_content_hash", ""),
        }
        ids.update({key: value for key, value in extra.items() if value})
        return ids

    def _confidence(self, payload: dict[str, Any], material_slice: dict[str, Any]) -> float:
        value = payload.get("confidence", material_slice.get("confidence"))
        if isinstance(value, (int, float)) and 0 <= value <= 1:
            return float(value)
        return 0.72

    def _looks_like_bad_concept_lead(self, label: str) -> bool:
        text = str(label or "").strip()
        if re.search(r"\.(md|markdown|pdf|docx?|pptx?|xlsx?|json|yaml|yml|txt)$", text, re.IGNORECASE):
            return True
        if "/" in text or "\\" in text:
            return True
        return False
