"""TopicCluster refresh request sidecar store.

This records a human request for an external proposal pack. It must not start
models, shell commands, workers, schedulers, or proposal generation.
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


_DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
_SAFE_ID_PATTERN = re.compile(r"^tcr_[A-Za-z0-9_-]{8,120}$")
_INPUT_KEYS = {
    "include_wiki_topics",
    "include_kfc_themes",
    "include_kfc_concepts",
    "include_research_projects",
}
_REQUEST_FIELDS = {
    "scope",
    "inputs",
    "topic_id",
    "topic_title",
    "suggested_title",
    "rationale",
    "source",
}


class TopicClusterRefreshRequestStoreError(ValueError):
    def __init__(self, message: str, *, code: str = "validation_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _new_request_id() -> str:
    return f"tcr_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"


class TopicClusterRefreshRequestStore:
    ROOT_DIR: Path = _DEFAULT_DATA_ROOT / "topic_cluster_refresh_requests"

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root_dir = Path(root_dir or self.ROOT_DIR).expanduser().resolve()

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self._validate_create_payload(payload)
        now = _now_iso()
        request_id = _new_request_id()
        request_obj = {
            "request_id": request_id,
            "type": "topic_cluster_recluster",
            "object_type": "topic_cluster_refresh_request",
            "schema_version": 1,
            "scope": clean["scope"],
            "status": "requested",
            "created_by": "human",
            "created_at": now,
            "updated_at": now,
            "inputs": clean["inputs"],
            **clean.get("topic_context", {}),
            "rules": {
                "do_not_auto_apply": True,
                "proposal_only": True,
                "preserve_human_accepted_links": True,
                "human_review_required": True,
                "kfc_must_not_execute_model": True,
                "kfc_must_not_start_external_process": True,
                "kfc_must_not_auto_create_research_project": True,
            },
        }
        self._atomic_write(self._path(request_id), request_obj)
        return request_obj

    def list(self, *, limit: int = 20) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        warnings: list[dict[str, str]] = []
        if self.root_dir.exists():
            for path in sorted(self.root_dir.glob("tcr_*.json")):
                try:
                    payload = self._read_file(path)
                except TopicClusterRefreshRequestStoreError as exc:
                    warnings.append({"type": exc.code, "file": path.name, "error": str(exc)})
                    continue
                items.append(payload)
        items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return {"items": items[:limit], "total": len(items), "warnings": warnings}

    def get(self, request_id: str) -> dict[str, Any] | None:
        self._validate_request_id(request_id)
        path = self._path(request_id)
        if not path.exists():
            return None
        return self._read_file(path)

    def _validate_create_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TopicClusterRefreshRequestStoreError("JSON body must be an object")
        unknown = sorted(set(payload) - _REQUEST_FIELDS)
        if unknown:
            raise TopicClusterRefreshRequestStoreError(f"unsupported fields: {', '.join(unknown)}")
        scope = payload.get("scope")
        if scope not in {"all", "wiki_topic"}:
            raise TopicClusterRefreshRequestStoreError("scope must be all or wiki_topic")
        inputs = payload.get("inputs")
        if not isinstance(inputs, dict):
            raise TopicClusterRefreshRequestStoreError("inputs must be an object")
        unknown_inputs = sorted(set(inputs) - _INPUT_KEYS)
        if unknown_inputs:
            raise TopicClusterRefreshRequestStoreError(f"unsupported input fields: {', '.join(unknown_inputs)}")
        clean_inputs = {}
        for key in sorted(_INPUT_KEYS):
            value = inputs.get(key, False)
            if not isinstance(value, bool):
                raise TopicClusterRefreshRequestStoreError(f"{key} must be boolean")
            clean_inputs[key] = value
        if not any(clean_inputs.values()):
            raise TopicClusterRefreshRequestStoreError("at least one input source must be selected")
        topic_context: dict[str, Any] = {}
        if scope == "wiki_topic":
            topic_id = str(payload.get("topic_id") or "").strip()
            if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$", topic_id):
                raise TopicClusterRefreshRequestStoreError("valid topic_id is required for wiki_topic scope")
            topic_context["topic_id"] = topic_id
            for field in ("topic_title", "suggested_title", "rationale", "source"):
                if field not in payload:
                    continue
                value = payload.get(field)
                if value is not None and not isinstance(value, str):
                    raise TopicClusterRefreshRequestStoreError(f"{field} must be a string")
                topic_context[field] = value or ""
        return {"scope": scope, "inputs": clean_inputs, "topic_context": topic_context}

    def _validate_request_id(self, request_id: str) -> None:
        if not _SAFE_ID_PATTERN.match(request_id or ""):
            raise TopicClusterRefreshRequestStoreError("invalid request_id")

    def _path(self, request_id: str) -> Path:
        self._validate_request_id(request_id)
        return self.root_dir / f"{request_id}.json"

    def _read_file(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            raise TopicClusterRefreshRequestStoreError(
                "malformed refresh request json",
                code="malformed_refresh_request_json",
                status_code=500,
            ) from exc
        if not isinstance(payload, dict):
            raise TopicClusterRefreshRequestStoreError(
                "refresh request payload must be an object",
                code="invalid_refresh_request_json",
                status_code=500,
            )
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
