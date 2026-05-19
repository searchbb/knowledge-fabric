"""TopicCluster proposal review store.

Proposal packs are external artifacts. KFC may review and explicitly apply
selected supported actions, but it never generates proposals or starts runners.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .topic_cluster_store import TopicClusterStore, TopicClusterStoreError


_DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
_SAFE_PROPOSAL_ID = re.compile(r"^tcp_[A-Za-z0-9_-]{3,160}$")
_SUPPORTED_APPLY_TYPES = {"create_cluster", "add_link"}


class TopicClusterProposalStoreError(ValueError):
    def __init__(self, message: str, *, code: str = "validation_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


class TopicClusterProposalStore:
    PROPOSAL_DIR: Path = _DEFAULT_DATA_ROOT / "topic_cluster_proposals"
    APPLICATION_DIR: Path = _DEFAULT_DATA_ROOT / "topic_cluster_proposal_applications"

    def __init__(
        self,
        proposal_dir: str | Path | None = None,
        application_dir: str | Path | None = None,
        topic_cluster_store: TopicClusterStore | None = None,
    ) -> None:
        self.proposal_dir = Path(proposal_dir or self.PROPOSAL_DIR).expanduser().resolve()
        self.application_dir = Path(application_dir or self.APPLICATION_DIR).expanduser().resolve()
        self.topic_cluster_store = topic_cluster_store or TopicClusterStore()

    def list_proposals(self) -> dict[str, Any]:
        proposals, warnings = self._load_proposals()
        applications = self._load_applications_by_proposal()
        items = []
        for proposal in proposals:
            actions = self._actions_for(proposal)
            supported = [action for action in actions if action.get("action_type") in _SUPPORTED_APPLY_TYPES]
            proposal_apps = applications.get(proposal["proposal_id"], [])
            latest = proposal_apps[0] if proposal_apps else None
            items.append(
                {
                    "proposal_id": proposal["proposal_id"],
                    "request_id": proposal.get("request_id") or proposal.get("source_request_id"),
                    "status": proposal.get("status", "ready_for_review"),
                    "created_at": proposal.get("created_at") or proposal.get("generated_at", ""),
                    "summary": proposal.get("summary", {}),
                    "action_count": len(actions),
                    "supported_action_count": len(supported),
                    "unsupported_action_count": len(actions) - len(supported),
                    "warning_count": len(proposal.get("warnings") or []),
                    "latest_application": latest,
                }
            )
        items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return {"items": items, "total": len(items), "warnings": warnings}

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        self._validate_proposal_id(proposal_id)
        path = self._proposal_path(proposal_id)
        if not path.exists():
            return None
        proposal = self._read_file(path, "proposal")
        proposal = self._normalized_proposal(proposal)
        return {"proposal": proposal, "applications": self._load_applications_by_proposal().get(proposal_id, [])}

    def apply_proposal(
        self,
        proposal_id: str,
        accepted_actions: list[str],
        rejected_actions: list[str] | None = None,
    ) -> dict[str, Any] | None:
        detail = self.get_proposal(proposal_id)
        if detail is None:
            return None
        proposal = detail["proposal"]
        rejected_actions = rejected_actions or []
        self._validate_apply_payload(proposal, accepted_actions, rejected_actions)

        actions_by_id = {action["action_id"]: action for action in proposal["actions"]}
        created_cluster_ids: list[str] = []
        created_link_ids: list[str] = []
        skipped_existing_cluster_ids: list[str] = []
        skipped_existing_link_ids: list[str] = []

        # Apply in dependency-aware order regardless of checkbox order.
        ordered_ids = sorted(
            accepted_actions,
            key=lambda action_id: 0 if actions_by_id[action_id]["action_type"] == "create_cluster" else 1,
        )
        for action_id in ordered_ids:
            action = actions_by_id[action_id]
            if action["action_type"] == "create_cluster":
                cluster_id = action["payload"]["cluster_id"]
                if self.topic_cluster_store.get_cluster(cluster_id) is not None:
                    skipped_existing_cluster_ids.append(cluster_id)
                    continue
                result = self.topic_cluster_store.create_cluster(
                    {
                        "cluster_id": cluster_id,
                        "title": action["payload"]["title"],
                        "description": action["payload"].get("description", ""),
                        "status": action["payload"].get("status", "candidate"),
                        "strategic_relevance": action["payload"].get("strategic_relevance", "unknown"),
                        "created_source": "codex_proposal",
                    }
                )
                created_cluster_ids.append(result["cluster"]["cluster_id"])
            elif action["action_type"] == "add_link":
                link_payload = action["payload"]
                link_id = link_payload.get("link_id")
                if link_id and (self.topic_cluster_store.link_dir / f"{link_id}.json").exists():
                    skipped_existing_link_ids.append(link_id)
                    continue
                result = self.topic_cluster_store.create_cluster_link(
                    link_payload["cluster_id"],
                    {
                        "link_id": link_id,
                        "target_type": self._normalize_target_type(link_payload.get("target_type") or link_payload.get("target_kind")),
                        "target_id": link_payload["target_id"],
                        "target_title": link_payload.get("target_title") or link_payload.get("target_label") or link_payload["target_id"],
                        "role": link_payload.get("role", "candidate"),
                        "status": self._normalize_link_status(link_payload.get("status", "candidate")),
                        "source": "codex_proposal",
                        "confidence": action.get("confidence"),
                        "rationale": action.get("rationale", ""),
                    },
                )
                if result is None:
                    raise TopicClusterProposalStoreError(
                        f"cluster not found for add_link action: {link_payload['cluster_id']}",
                        code="missing_target_cluster",
                    )
                created_link_ids.append(result["link"]["link_id"])

        now = _now_iso()
        application = {
            "application_id": f"tcpa_{proposal_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}",
            "proposal_id": proposal_id,
            "proposal_version": proposal.get("proposal_version") or proposal.get("schema_version", 1),
            "request_id": proposal.get("request_id") or proposal.get("source_request_id"),
            "applied_at": now,
            "accepted_actions": accepted_actions,
            "rejected_actions": rejected_actions,
            "created_cluster_ids": created_cluster_ids,
            "created_link_ids": created_link_ids,
            "skipped_existing_cluster_ids": skipped_existing_cluster_ids,
            "skipped_existing_link_ids": skipped_existing_link_ids,
            "unsupported_actions": [],
            "errors": [],
        }
        self._atomic_write(self.application_dir / f"{application['application_id']}.json", application)
        return application

    def _validate_apply_payload(self, proposal: dict[str, Any], accepted: list[str], rejected: list[str]) -> None:
        if not isinstance(accepted, list) or not all(isinstance(item, str) for item in accepted):
            raise TopicClusterProposalStoreError("accepted_actions must be an array of strings")
        if not isinstance(rejected, list) or not all(isinstance(item, str) for item in rejected):
            raise TopicClusterProposalStoreError("rejected_actions must be an array of strings")
        if len(set(accepted)) != len(accepted):
            raise TopicClusterProposalStoreError("accepted_actions contains duplicates")
        overlap = set(accepted) & set(rejected)
        if overlap:
            raise TopicClusterProposalStoreError(f"action cannot be both accepted and rejected: {sorted(overlap)[0]}")
        actions = proposal["actions"]
        if len({action["action_id"] for action in actions}) != len(actions):
            raise TopicClusterProposalStoreError("proposal contains duplicate action_id", code="invalid_proposal")
        actions_by_id = {action["action_id"]: action for action in actions}
        for action_id in accepted:
            action = actions_by_id.get(action_id)
            if action is None:
                raise TopicClusterProposalStoreError(f"unknown action_id: {action_id}")
            if action.get("action_type") not in _SUPPORTED_APPLY_TYPES:
                raise TopicClusterProposalStoreError(
                    f"unsupported action type for Phase 3 MVP: {action.get('action_type')}",
                    code="unsupported_action_type",
                )
        created_clusters = {
            actions_by_id[action_id]["payload"]["cluster_id"]
            for action_id in accepted
            if actions_by_id[action_id]["action_type"] == "create_cluster"
        }
        for action_id in accepted:
            action = actions_by_id[action_id]
            if action["action_type"] != "add_link":
                continue
            cluster_id = action["payload"].get("cluster_id")
            if cluster_id in created_clusters or self.topic_cluster_store.get_cluster(cluster_id) is not None:
                continue
            raise TopicClusterProposalStoreError(
                f"cluster not found for add_link action: {cluster_id}",
                code="missing_target_cluster",
            )

    def _load_proposals(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        if not self.proposal_dir.exists():
            return [], []
        proposals = []
        warnings = []
        for path in sorted(self.proposal_dir.glob("tcp_*.json")):
            try:
                proposals.append(self._normalized_proposal(self._read_file(path, "proposal")))
            except TopicClusterProposalStoreError as exc:
                warnings.append({"type": exc.code, "file": path.name, "error": str(exc)})
        return proposals, warnings

    def _normalized_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        proposal_id = proposal.get("proposal_id")
        self._validate_proposal_id(proposal_id)
        normalized = dict(proposal)
        normalized.setdefault("status", "ready_for_review")
        normalized.setdefault("warnings", [])
        normalized["actions"] = self._actions_for(proposal)
        return normalized

    def _actions_for(self, proposal: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(proposal.get("actions"), list):
            return [dict(action) for action in proposal["actions"] if isinstance(action, dict)]
        actions: list[dict[str, Any]] = []
        for item in proposal.get("proposed_clusters") or []:
            if not isinstance(item, dict):
                continue
            cluster_id = item.get("cluster_id_suggested") or item.get("cluster_id")
            if not cluster_id:
                continue
            actions.append(
                {
                    "action_id": f"create_cluster:{cluster_id}",
                    "action_type": "create_cluster",
                    "confidence": item.get("confidence"),
                    "rationale": item.get("rationale", ""),
                    "payload": {
                        "cluster_id": cluster_id,
                        "title": item.get("title") or cluster_id,
                        "description": item.get("description", ""),
                        "status": item.get("status", "candidate"),
                        "strategic_relevance": item.get("strategic_relevance", "unknown"),
                    },
                }
            )
        for item in proposal.get("proposed_links") or []:
            if not isinstance(item, dict):
                continue
            link_id = item.get("link_id") or f"tcl_{secrets.token_hex(5)}"
            actions.append(
                {
                    "action_id": f"add_link:{link_id}",
                    "action_type": "add_link",
                    "confidence": item.get("confidence"),
                    "rationale": item.get("rationale", ""),
                    "payload": {
                        "link_id": link_id,
                        "cluster_id": item.get("cluster_id"),
                        "target_type": item.get("target_type"),
                        "target_id": item.get("target_id"),
                        "target_title": item.get("target_title"),
                        "role": item.get("role", "candidate"),
                        "status": item.get("status", "candidate"),
                    },
                }
            )
        for item in proposal.get("possible_merges") or []:
            action_id = item.get("action_id") if isinstance(item, dict) else str(item)
            actions.append({"action_id": action_id, "action_type": "merge_cluster", "payload": item})
        for item in proposal.get("possible_splits") or []:
            action_id = item.get("action_id") if isinstance(item, dict) else str(item)
            actions.append({"action_id": action_id, "action_type": "split_cluster", "payload": item})
        return actions

    def _load_applications_by_proposal(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        if not self.application_dir.exists():
            return grouped
        for path in sorted(self.application_dir.glob("tcpa_*.json")):
            try:
                item = self._read_file(path, "application")
            except TopicClusterProposalStoreError:
                continue
            grouped.setdefault(item.get("proposal_id", ""), []).append(item)
        for items in grouped.values():
            items.sort(key=lambda item: item.get("applied_at", ""), reverse=True)
        return grouped

    def _normalize_target_type(self, value: str) -> str:
        if value in {"vt_topic", "wiki_topic"}:
            return "wiki_topic"
        return value

    def _normalize_link_status(self, value: str) -> str:
        if value == "proposed":
            return "candidate"
        return value

    def _validate_proposal_id(self, proposal_id: str) -> None:
        if not _SAFE_PROPOSAL_ID.match(proposal_id or ""):
            raise TopicClusterProposalStoreError("invalid proposal_id")

    def _proposal_path(self, proposal_id: str) -> Path:
        self._validate_proposal_id(proposal_id)
        return self.proposal_dir / f"{proposal_id}.json"

    def _read_file(self, path: Path, kind: str) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            raise TopicClusterProposalStoreError(f"malformed {kind} json", code=f"malformed_{kind}_json") from exc
        if not isinstance(payload, dict):
            raise TopicClusterProposalStoreError(f"{kind} payload must be an object", code=f"invalid_{kind}_json")
        return payload

    def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
