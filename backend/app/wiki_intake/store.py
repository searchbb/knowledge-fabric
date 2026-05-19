"""Repo-local state store for Wiki intake sidecars."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote

from ..services.topic_cluster_store import TopicClusterStore, TopicClusterStoreError
from ..services.topic_cluster_refresh_request_store import (
    TopicClusterRefreshRequestStore,
    TopicClusterRefreshRequestStoreError,
)
from .scanner import scan_clippings


DEFAULT_CLIPPINGS_ROOT = Path("/Users/mac/Downloads/OB笔记/Clippings")
DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "wiki_intake"
DEFAULT_WIKI_HUB_ROOT = Path(__file__).resolve().parents[2] / "data" / "wiki_hub"
DECISION_STATUSES = {"accepted", "deferred", "rejected", "duplicate", "needs_human_review", "promote_to_kfc_queue"}
DESTINATIONS = {"wiki", "kfc", "both", "neither", "llm_wiki_only", "kfc_only"}
COVERAGE_OVERRIDE_STATUSES = {"needs_cluster", "watch", "ignored"}
SAFE_TOPIC_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")
LOCAL_ASSET_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


class WikiIntakeStoreError(ValueError):
    def __init__(self, message: str, *, code: str = "validation_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WikiIntakeStoreError(f"malformed jsonl at {path.name}:{line_no}", code="malformed_jsonl") from exc
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def _latest_by(rows: list[dict[str, Any]], key: str, stamp_key: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_key = str(row.get(key) or row.get("source_id") or "")
        if not item_key:
            continue
        current = latest.get(item_key)
        if current is None or str(row.get(stamp_key) or row.get("updated_at") or "") >= str(current.get(stamp_key) or current.get("updated_at") or ""):
            latest[item_key] = row
    return latest


def _compact_list(values: list[Any], *, limit: int = 8) -> list[str]:
    seen: set[str] = set()
    compact: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        compact.append(text)
        if len(compact) >= limit:
            break
    return compact


class WikiIntakeStore:
    DATA_ROOT = DEFAULT_DATA_ROOT
    CLIPPINGS_ROOT = DEFAULT_CLIPPINGS_ROOT

    def __init__(self, *, data_root: Path | None = None, clippings_root: Path | None = None) -> None:
        self.data_root = Path(
            data_root
            or os.environ.get("KFC_WIKI_INTAKE_DATA_ROOT", "")
            or self.DATA_ROOT
        ).expanduser().resolve()
        self.clippings_root = Path(
            clippings_root
            or os.environ.get("KFC_WIKI_INTAKE_CLIPPINGS_ROOT", "")
            or self.CLIPPINGS_ROOT
        ).expanduser().resolve()
        self.wiki_hub_root = Path(
            os.environ.get("KFC_WIKI_HUB_ROOT", "")
            or DEFAULT_WIKI_HUB_ROOT
        ).expanduser().resolve()

    @property
    def manifest_path(self) -> Path:
        return self.data_root / "manifest.jsonl"

    @property
    def decisions_path(self) -> Path:
        return self.data_root / "decisions.jsonl"

    @property
    def processing_path(self) -> Path:
        return self.data_root / "processing_results.jsonl"

    @property
    def topic_cluster_coverage_path(self) -> Path:
        return self.data_root / "topic_cluster_coverage.jsonl"

    @property
    def auto_processed_path(self) -> Path:
        return self.data_root / "auto_processed_manifest.jsonl"

    @property
    def topic_association_events_path(self) -> Path:
        return self.data_root / "topic_association_events.jsonl"

    @property
    def events_path(self) -> Path:
        return self.data_root / "events.jsonl"

    @property
    def pre_digest_dir(self) -> Path:
        return self.data_root / "pre_digest"

    @property
    def kfc_queue_dir(self) -> Path:
        return self.data_root / "kfc_queue"

    def config(self) -> dict[str, Any]:
        return {
            "clippings_root": str(self.clippings_root),
            "data_root": str(self.data_root),
            "manifest_path": str(self.manifest_path),
            "decisions_path": str(self.decisions_path),
            "wiki_hub_root": str(self.wiki_hub_root),
            "clippings_readonly": True,
            "runner_enabled": True,
            "default_adapter": os.environ.get("KFC_AUTO_INTAKE_ADAPTER") or os.environ.get("AUTO_INTAKE_ADAPTER", "chatgpt_app_attachment"),
            "default_behavior": "scan_enqueue_process_with_gpt_predigest",
        }

    def ensure_dirs(self) -> None:
        for path in [
            self.data_root,
            self.data_root / "auto_jobs",
            self.data_root / "auto_runs",
            self.wiki_hub_root,
            self.pre_digest_dir,
            self.kfc_queue_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def scan(self, *, allow_empty_overwrite: bool = False) -> dict[str, Any]:
        self.ensure_dirs()
        records = scan_clippings(self.clippings_root)
        previous_count = len(_read_jsonl(self.manifest_path))
        if not records and previous_count > 0 and not allow_empty_overwrite:
            raise WikiIntakeStoreError(
                f"refusing to overwrite non-empty manifest ({previous_count} records) with empty scan",
                code="empty_scan_refused",
            )
        _atomic_write_jsonl(self.manifest_path, records)
        topic_counter = Counter()
        for record in records:
            guessed = record.get("guessed_topics") or []
            if guessed:
                topic_counter[str(guessed[0].get("topic_id") or "")] += 1
        duplicate_count = sum(1 for record in records if record.get("duplicate_status") != "none")
        event = {
            "schema_version": "event.v1",
            "tool_version": "kfc-wiki-intake-store-0.1",
            "event_type": "scan_completed",
            "event_at": now_iso(),
            "clippings_root": str(self.clippings_root),
            "manifest_path": str(self.manifest_path),
            "markdown_count": len(records),
            "duplicate_count": duplicate_count,
            "topic_guess_counts": dict(sorted(topic_counter.items())),
            "side_effects": {
                "modified_obsidian_source": False,
                "copied_to_llm_wiki": False,
                "created_kfc_project": False,
                "called_llm": False,
            },
        }
        _append_jsonl(self.events_path, event)
        return {
            "markdown_count": len(records),
            "duplicate_count": duplicate_count,
            "manifest_path": str(self.manifest_path),
            "event": event,
        }

    def enqueue_new(self, *, since_previous_scan: bool = True, limit: int = 0) -> dict[str, Any]:
        self.ensure_dirs()
        _ensure_runner_scripts_on_path()
        from auto_intake_enqueue import enqueue_from_manifest

        return enqueue_from_manifest(
            self.data_root,
            limit=limit,
            since_previous_scan=since_previous_scan,
        )

    def enqueue_candidate(self, candidate_id: str) -> dict[str, Any]:
        self.ensure_dirs()
        candidate_id = str(candidate_id or "").strip()
        if not candidate_id:
            raise WikiIntakeStoreError("candidate_id is required")
        manifest_records = {
            str(record.get("candidate_id") or record.get("source_id") or ""): record
            for record in _read_jsonl(self.manifest_path)
        }
        record = manifest_records.get(candidate_id)
        if record is None:
            raise WikiIntakeStoreError(f"candidate not found: {candidate_id}", code="not_found", status_code=404)

        _ensure_runner_scripts_on_path()
        import auto_intake_job_store

        source_key = auto_intake_job_store.source_key(record)
        processed_keys = {
            str(row.get("source_key") or "")
            for row in _read_jsonl(self.auto_processed_path)
            if str(row.get("source_key") or "")
        }
        active_keys = auto_intake_job_store.active_source_keys(self.data_root) | processed_keys
        if source_key in active_keys:
            return {
                "ok": True,
                "status": "skipped",
                "reason": "already_active_or_processed",
                "candidate_id": candidate_id,
                "source_key": source_key,
            }
        job = auto_intake_job_store.create_job(self.data_root, record, status="queued")
        return {
            "ok": True,
            "status": "queued",
            "candidate_id": candidate_id,
            "job_id": job.get("job_id"),
            "job_path": job.get("job_path"),
            "source_key": source_key,
        }

    def recover_stuck_jobs(self, *, stale_seconds: int = 1800) -> list[dict[str, Any]]:
        self.ensure_dirs()
        _ensure_runner_scripts_on_path()
        import auto_intake_job_store

        return auto_intake_job_store.recover_stuck(self.data_root, stale_seconds=stale_seconds)

    def process_next(
        self,
        *,
        adapter: str | None = None,
        timeout_seconds: int = 1500,
        image_limit: int = 4,
        codex_bin: str | None = None,
        model: str = "",
        enqueue_first: bool = True,
        since_previous_scan: bool = True,
    ) -> dict[str, Any]:
        self.ensure_dirs()
        _ensure_runner_scripts_on_path()
        from auto_intake_fresh_runner import process_one

        selected_adapter = (
            adapter
            or os.environ.get("KFC_AUTO_INTAKE_ADAPTER")
            or os.environ.get("AUTO_INTAKE_ADAPTER")
            or "chatgpt_app_attachment"
        )
        enqueue_result = self.enqueue_new(since_previous_scan=since_previous_scan) if enqueue_first else None
        recovered = self.recover_stuck_jobs(stale_seconds=int(os.environ.get("AUTO_INTAKE_STALE_SECONDS", "1800")))
        result = process_one(
            SimpleNamespace(
                intake_dir=self.data_root,
                wiki_hub=self.wiki_hub_root,
                clippings_root=self.clippings_root,
                adapter=selected_adapter,
                timeout_seconds=timeout_seconds,
                image_limit=image_limit,
                codex_bin=codex_bin or os.environ.get("CODEX_BIN", "/opt/homebrew/bin/codex"),
                model=model or os.environ.get("CODEX_AUTO_INTAKE_MODEL", ""),
            )
        )
        topic_cluster_sync = self._sync_topic_cluster_link(result)
        _append_jsonl(
            self.events_path,
            {
                "schema_version": "event.v1",
                "tool_version": "kfc-wiki-intake-runner-0.1",
                "event_type": "process_next_completed",
                "event_at": now_iso(),
                "adapter": selected_adapter,
                "enqueue": enqueue_result,
                "recovered_count": len(recovered),
                "result_status": result.get("status"),
                "topic_cluster_sync": topic_cluster_sync,
                "side_effects": {
                    "modified_obsidian_source": False,
                    "copied_to_llm_wiki": True,
                    "created_kfc_project": False,
                    "called_llm": selected_adapter not in {"deterministic", "manual_file"},
                },
            },
        )
        return {
            "ok": True,
            "adapter": selected_adapter,
            "enqueue": enqueue_result,
            "recovered": recovered,
            "result": result,
            "topic_cluster_sync": topic_cluster_sync,
        }

    def process_batch(
        self,
        *,
        max_runs: int = 1,
        adapter: str | None = None,
        timeout_seconds: int = 1500,
        image_limit: int = 4,
        since_previous_scan: bool = True,
    ) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        for index in range(max(1, min(max_runs, 20))):
            result = self.process_next(
                adapter=adapter,
                timeout_seconds=timeout_seconds,
                image_limit=image_limit,
                enqueue_first=index == 0,
                since_previous_scan=since_previous_scan,
            )
            runs.append(result)
            if (result.get("result") or {}).get("status") == "no_queued_jobs":
                break
        return {"ok": True, "runs": runs, "total_runs": len(runs)}

    def _annotated_candidates(self) -> list[dict[str, Any]]:
        records = _read_jsonl(self.manifest_path)
        decisions = _latest_by(_read_jsonl(self.decisions_path), "candidate_id", "decided_at")
        processing = _latest_by(_read_jsonl(self.processing_path), "candidate_id", "processed_at")
        auto_processed = _latest_by(_read_jsonl(self.auto_processed_path), "candidate_id", "processed_at")
        annotated: list[dict[str, Any]] = []
        for record in records:
            candidate_id = str(record.get("candidate_id") or record.get("source_id") or "")
            decision = decisions.get(candidate_id)
            processing_result = processing.get(candidate_id)
            auto_record = auto_processed.get(candidate_id)
            status = "pending"
            if auto_record and not str(auto_record.get("topic_id") or "").strip():
                status = "needs_human_review"
            elif auto_record:
                status = "completed"
            elif decision:
                status = str(decision.get("decision_status") or decision.get("decision") or "pending")
            elif processing_result and str(processing_result.get("status") or "") == "needs_human_review":
                status = "needs_human_review"
            elif record.get("duplicate_status") not in (None, "", "none"):
                status = "duplicate"
            item = dict(record)
            item["candidate_id"] = candidate_id
            item["status"] = status
            item["latest_decision"] = decision
            item["latest_processing"] = processing_result
            item["auto_processed"] = auto_record
            item["has_processing_result"] = bool(processing_result or auto_record)
            item["has_digest"] = self._has_digest(candidate_id)
            item["needs_human_review"] = status == "needs_human_review"
            annotated.append(item)
        annotated.sort(key=lambda item: str(item.get("mtime") or ""), reverse=True)
        return annotated

    def _has_digest(self, candidate_id: str) -> bool:
        if not candidate_id:
            return False
        return any(self.pre_digest_dir.glob(f"{candidate_id}*decision_digest.*"))

    def list_candidates(self, *, status: str | None = None) -> dict[str, Any]:
        items = self._annotated_candidates()
        if status and status != "all":
            items = [item for item in items if item.get("status") == status]
        return {
            "items": items,
            "total": len(items),
            "stats": self.stats(items=self._annotated_candidates()),
            "source_manifest": str(self.manifest_path),
            "clippings_root": str(self.clippings_root),
        }

    def get_candidate(self, candidate_id: str) -> dict[str, Any]:
        for item in self._annotated_candidates():
            if item.get("candidate_id") == candidate_id:
                content = ""
                path = Path(str(item.get("source_file_path") or "")).expanduser()
                try:
                    resolved = path.resolve()
                    resolved.relative_to(self.clippings_root)
                    if resolved.exists() and resolved.is_file():
                        content = resolved.read_text(encoding="utf-8", errors="replace")
                except (OSError, ValueError):
                    content = ""
                return {
                    "candidate": item,
                    "content": content,
                    "decision_digest": self._candidate_decision_digest(candidate_id),
                    "topic_context": self.get_topic_context_for_candidate(candidate_id),
                }
        raise WikiIntakeStoreError(f"candidate not found: {candidate_id}", code="not_found", status_code=404)

    def get_processed_result(self, candidate_id: str) -> dict[str, Any]:
        detail = self.get_candidate(candidate_id)
        candidate = detail.get("candidate") or {}
        auto_processed = candidate.get("auto_processed") if isinstance(candidate.get("auto_processed"), dict) else {}
        result: dict[str, Any] = {
            "status": "missing",
            "auto_processed": auto_processed or None,
            "verified_digest": {"json": None, "md": ""},
            "claim_ledger": [],
            "sources": None,
            "raw_article_preview": "",
            "read_errors": {},
        }
        if not auto_processed:
            return result

        read_errors: dict[str, str] = {}
        digest_json, error = self._read_json_sidecar(auto_processed.get("verified_digest_json_path"))
        if error:
            read_errors["verified_digest_json_path"] = error
        digest_md, error = self._read_text_sidecar(auto_processed.get("verified_digest_md_path"))
        if error:
            read_errors["verified_digest_md_path"] = error
        claim_ledger, error = self._read_jsonl_sidecar(auto_processed.get("claim_ledger_path"))
        if error:
            read_errors["claim_ledger_path"] = error
        sources, error = self._read_json_sidecar(auto_processed.get("sources_path"))
        if error:
            read_errors["sources_path"] = error
        raw_preview, error = self._read_text_sidecar(auto_processed.get("raw_article_path"), limit=2400)
        if error:
            read_errors["raw_article_path"] = error

        has_review_payload = bool(digest_json or digest_md or claim_ledger or sources)
        result.update(
            {
                "status": "complete" if has_review_payload else "manifest_only",
                "verified_digest": {"json": digest_json, "md": digest_md or ""},
                "claim_ledger": claim_ledger,
                "sources": sources,
                "raw_article_preview": raw_preview or "",
                "read_errors": read_errors,
            }
        )
        result["semantic_result"] = self._semantic_processed_result(result)
        return result

    def _semantic_processed_result(self, result: dict[str, Any]) -> dict[str, Any]:
        digest = result.get("verified_digest", {}).get("json") or {}
        source_digest = digest.get("source_digest") if isinstance(digest.get("source_digest"), dict) else digest
        routing = digest.get("routing_decision") if isinstance(digest.get("routing_decision"), dict) else {}
        auto_processed = result.get("auto_processed") if isinstance(result.get("auto_processed"), dict) else {}
        claims = result.get("claim_ledger") if isinstance(result.get("claim_ledger"), list) else []
        candidate_concepts = self._semantic_candidate_concepts(
            source_digest.get("core_concepts")
            or digest.get("core_concepts")
            or digest.get("top_concepts")
            or []
        )
        safe_wiki = digest.get("safe_wiki") if isinstance(digest.get("safe_wiki"), dict) else {}
        do_not_state_as_fact = self._semantic_text_list(
            safe_wiki.get("do_not_state_as_fact")
            or digest.get("do_not_state_as_fact")
            or digest.get("research_gaps")
            or []
        )
        verification_counts = self._semantic_verification_counts(digest, claims)
        topic_id = (
            routing.get("resolved_topic_id")
            or routing.get("original_recommended_topic")
            or digest.get("recommended_topic")
            or auto_processed.get("topic_id")
            or ""
        )
        route_mode = routing.get("route_mode") or auto_processed.get("route_mode") or ""
        concept_names = [item["name"] for item in candidate_concepts]
        return {
            "status": result.get("status") or "missing",
            "recommended_topic": {
                "topic_id": topic_id,
                "label": routing.get("resolved_topic_label")
                or routing.get("original_recommended_topic_label")
                or digest.get("recommended_topic_label")
                or topic_id,
                "route_mode": route_mode,
                "auto_created_topic": route_mode == "auto_created_topic",
                "needs_human_review": bool(auto_processed.get("needs_topic_review") or result.get("read_errors")),
            },
            "article_digest": {
                "one_sentence_summary": source_digest.get("one_sentence_summary")
                or source_digest.get("source_summary")
                or digest.get("source_summary")
                or digest.get("summary")
                or "",
                "main_claim": source_digest.get("main_claim") or digest.get("main_claim") or "",
                "mechanism_summary": source_digest.get("mechanism_summary") or digest.get("mechanism_summary") or "",
                "author_position": source_digest.get("author_position") or digest.get("author_position") or "",
                "key_points": self._semantic_text_list(source_digest.get("key_points") or digest.get("key_points") or []),
            },
            "candidate_concepts": candidate_concepts,
            "verification": {
                **verification_counts,
                "do_not_state_as_fact": do_not_state_as_fact,
            },
            "safe_wiki": {
                "summary": safe_wiki.get("safe_summary")
                or digest.get("safe_summary")
                or digest.get("safe_wiki_wording")
                or digest.get("verified_summary")
                or "",
                "wording": safe_wiki.get("wording") or digest.get("safe_wiki_wording") or "",
                "follow_up_questions": self._semantic_text_list(
                    safe_wiki.get("follow_up_questions")
                    or digest.get("follow_up_questions")
                    or digest.get("recommended_followups")
                    or []
                ),
            },
            "kfc_action_hints": {
                "match_existing_concept": concept_names,
                "review_as_new_concept": [
                    item["name"]
                    for item in candidate_concepts
                    if item.get("kfc_action_hint") == "review_for_kfc"
                ],
                "keep_as_article_clue": concept_names,
                "readonly": True,
            },
            "audit": {
                "paths": {
                    key: auto_processed.get(key) or ""
                    for key in [
                        "raw_article_path",
                        "verified_digest_json_path",
                        "verified_digest_md_path",
                        "claim_ledger_path",
                        "sources_path",
                    ]
                },
                "manifest": auto_processed,
                "read_errors": result.get("read_errors") or {},
            },
        }

    def _semantic_candidate_concepts(self, concepts: Any) -> list[dict[str, str]]:
        if not isinstance(concepts, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in concepts:
            if isinstance(item, str):
                name = item.strip()
                summary = ""
                hint = "keep_as_article_clue"
            elif isinstance(item, dict):
                name = str(item.get("concept") or item.get("name") or item.get("title") or "").strip()
                summary = str(item.get("summary") or item.get("body") or item.get("description") or "").strip()
                hint = str(item.get("kfc_action_hint") or item.get("action_hint") or "review_for_kfc").strip()
            else:
                continue
            if not name:
                continue
            normalized.append(
                {
                    "name": name,
                    "summary": summary,
                    "candidate_status": "candidate_only",
                    "kfc_action_hint": hint or "review_for_kfc",
                }
            )
        return normalized[:12]

    def _semantic_text_list(self, value: Any, *, limit: int = 8) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(
                    item.get("text")
                    or item.get("title")
                    or item.get("summary")
                    or item.get("claim")
                    or item.get("reason")
                    or ""
                ).strip()
            else:
                text = ""
            if text:
                items.append(text)
        return items[:limit]

    def _semantic_verification_counts(self, digest: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, int]:
        summary = digest.get("verification_summary") if isinstance(digest.get("verification_summary"), dict) else {}
        counts = {
            "verified_count": int(summary.get("verified_facts_count") or 0),
            "uncertain_count": int(summary.get("uncertain_claims_count") or 0),
            "source_only_count": 0,
            "stale_contradicted_count": 0,
        }
        for claim in claims:
            status = str(claim.get("verification_status") or claim.get("status") or "source_only")
            if status == "verified":
                counts["verified_count"] += 1
            elif status == "uncertain":
                counts["uncertain_count"] += 1
            elif status in {"contradicted", "stale", "contradicted_or_stale", "stale_contradicted"}:
                counts["stale_contradicted_count"] += 1
            else:
                counts["source_only_count"] += 1
        return counts

    def _candidate_decision_digest(self, candidate_id: str) -> dict[str, Any] | None:
        if not candidate_id:
            return None
        json_path = self.pre_digest_dir / f"{candidate_id}.decision_digest.json"
        markdown_path = self.pre_digest_dir / f"{candidate_id}.decision_digest.md"
        if not json_path.exists() and not markdown_path.exists():
            return None
        result: dict[str, Any] = {}
        if json_path.exists() and json_path.is_file():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    result["payload"] = payload
                    result["json_path"] = str(json_path)
            except (OSError, json.JSONDecodeError):
                result["json_read_error"] = "unreadable_decision_digest_json"
        if markdown_path.exists() and markdown_path.is_file():
            try:
                result["markdown"] = markdown_path.read_text(encoding="utf-8", errors="replace")
                result["markdown_path"] = str(markdown_path)
            except OSError:
                result["markdown_read_error"] = "unreadable_decision_digest_markdown"
        return result or None

    def _resolve_sidecar_path(self, path_value: Any) -> tuple[Path | None, str | None]:
        path_text = str(path_value or "").strip()
        if not path_text:
            return None, "missing_path"
        try:
            path = Path(path_text).expanduser().resolve()
        except OSError:
            return None, "invalid_path"
        allowed_roots = [self.data_root, self.wiki_hub_root, self.clippings_root]
        if not any(self._is_relative_to(path, root) for root in allowed_roots):
            return None, "outside_allowed_roots"
        return path, None

    def _read_json_sidecar(self, path_value: Any) -> tuple[dict[str, Any] | None, str | None]:
        path, error = self._resolve_sidecar_path(path_value)
        if error:
            return None, error
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, "missing_file"
        except (OSError, json.JSONDecodeError):
            return None, "invalid_json"
        if not isinstance(payload, dict):
            return None, "invalid_json"
        return payload, None

    def _read_jsonl_sidecar(self, path_value: Any) -> tuple[list[dict[str, Any]], str | None]:
        path, error = self._resolve_sidecar_path(path_value)
        if error:
            return [], error
        try:
            rows = _read_jsonl(path)
        except FileNotFoundError:
            return [], "missing_file"
        except WikiIntakeStoreError:
            return [], "invalid_jsonl"
        return rows, None

    def _read_text_sidecar(self, path_value: Any, *, limit: int | None = None) -> tuple[str, str | None]:
        path, error = self._resolve_sidecar_path(path_value)
        if error:
            return "", error
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return "", "missing_file"
        except OSError:
            return "", "unreadable_text"
        if limit is not None and len(text) > limit:
            return text[:limit].rstrip() + "\n...", None
        return text, None

    def _is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    def resolve_candidate_asset(self, candidate_id: str, relative_path: str) -> tuple[Path, str]:
        candidate_id = str(candidate_id or "").strip()
        if not candidate_id:
            raise WikiIntakeStoreError("candidate_id is required")
        record = next(
            (item for item in self._annotated_candidates() if item.get("candidate_id") == candidate_id),
            None,
        )
        if record is None:
            raise WikiIntakeStoreError(f"candidate not found: {candidate_id}", code="not_found", status_code=404)

        safe_relative = self._normalize_asset_relative_path(relative_path)
        source_path = Path(str(record.get("source_file_path") or "")).expanduser()
        try:
            source_resolved = source_path.resolve()
            source_resolved.relative_to(self.clippings_root)
        except (OSError, ValueError):
            raise WikiIntakeStoreError("candidate source path is invalid", code="not_found", status_code=404)

        base_dir = source_resolved.parent
        asset_path = (base_dir / Path(*safe_relative.parts)).resolve()
        try:
            asset_path.relative_to(base_dir)
            asset_path.relative_to(self.clippings_root)
        except ValueError:
            raise WikiIntakeStoreError("invalid asset path", code="invalid_asset_path", status_code=400)

        mime_type = LOCAL_ASSET_MIME_TYPES.get(asset_path.suffix.lower())
        if not mime_type:
            raise WikiIntakeStoreError("unsupported asset type", code="unsupported_asset_type", status_code=400)
        if not asset_path.exists() or not asset_path.is_file():
            raise WikiIntakeStoreError("asset not found", code="not_found", status_code=404)
        return asset_path, mime_type

    def _normalize_asset_relative_path(self, relative_path: str) -> PurePosixPath:
        value = str(relative_path or "").strip()
        if not value:
            raise WikiIntakeStoreError("asset path is required", code="invalid_asset_path", status_code=400)
        try:
            value = unquote(value)
        except ValueError:
            raise WikiIntakeStoreError("invalid asset path", code="invalid_asset_path", status_code=400)
        if "\x00" in value or "\\" in value or "://" in value:
            raise WikiIntakeStoreError("invalid asset path", code="invalid_asset_path", status_code=400)
        if value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value):
            raise WikiIntakeStoreError("invalid asset path", code="invalid_asset_path", status_code=400)
        normalized = PurePosixPath(value)
        if normalized.is_absolute() or str(normalized) in {"", "."}:
            raise WikiIntakeStoreError("invalid asset path", code="invalid_asset_path", status_code=400)
        if any(part in {"", ".", ".."} for part in normalized.parts):
            raise WikiIntakeStoreError("invalid asset path", code="invalid_asset_path", status_code=400)
        return normalized

    def list_topics(self, *, include_coverage: bool = False) -> list[dict[str, Any]] | dict[str, Any]:
        records = self._topic_rows()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in records:
            topic_id = str(row.get("topic_id") or "").strip()
            if topic_id:
                grouped.setdefault(topic_id, []).append(row)

        items = []
        annotated = self._annotated_candidates()
        for topic_id, rows in grouped.items():
            profile = self._topic_profile(topic_id)
            cluster_links = self._cluster_links_for_topic(topic_id)
            articles = [self._topic_article(row, include_digest=True) for row in rows]
            articles.sort(key=lambda item: str(item.get("processed_at") or ""), reverse=True)
            top_concepts = _compact_list(
                list(profile.get("concept_seeds") or [])
                + [concept for article in articles for concept in article.get("top_concepts", [])]
                + list(profile.get("topic_keywords") or []),
                limit=8,
            )
            topic = {
                    "topic_id": topic_id,
                    "title": str(profile.get("display_name") or profile.get("title") or topic_id),
                    "display_name": str(profile.get("display_name") or profile.get("title") or topic_id),
                    "article_count": len(articles),
                    "completed_count": len(articles),
                    "needs_review_count": self._needs_review_count_for_topic(topic_id, annotated, rows),
                    "last_processed_at": max((str(row.get("processed_at") or "") for row in rows), default=""),
                    "top_concepts": top_concepts,
                    "topic_keywords": _compact_list(list(profile.get("topic_keywords") or []), limit=12),
                    "cluster_ids": [link["cluster_id"] for link in cluster_links],
                    "cluster_links": cluster_links,
                    "representative_articles": articles[:5],
                }
            if include_coverage:
                topic["cluster_coverage"] = self._cluster_coverage_for_topic(topic)
                topic["cluster_coverage_status"] = topic["cluster_coverage"]["status"]
            items.append(topic)

        items.sort(key=lambda item: (-(item["article_count"] or 0), str(item.get("last_processed_at") or "")), reverse=False)
        if include_coverage:
            counts = Counter(str(item.get("cluster_coverage_status") or "watch") for item in items)
            return {
                "topics": items,
                "items": items,
                "total": len(items),
                "coverage_counts": {status: counts.get(status, 0) for status in ["linked", "candidate", "needs_cluster", "watch", "ignored"]},
            }
        return items

    def get_topic_articles(self, topic_id: str) -> dict[str, Any]:
        self._validate_topic_id(topic_id)
        topics = {topic["topic_id"]: topic for topic in self.list_topics()}
        topic = topics.get(topic_id)
        if topic is None:
            profile = self._topic_profile(topic_id)
            cluster_links = self._cluster_links_for_topic(topic_id)
            topic = {
                "topic_id": topic_id,
                "title": str(profile.get("display_name") or profile.get("title") or topic_id),
                "display_name": str(profile.get("display_name") or profile.get("title") or topic_id),
                "article_count": 0,
                "completed_count": 0,
                "needs_review_count": self._needs_review_count_for_topic(topic_id, self._annotated_candidates(), []),
                "last_processed_at": "",
                "top_concepts": _compact_list(list(profile.get("concept_seeds") or []) + list(profile.get("topic_keywords") or [])),
                "topic_keywords": _compact_list(list(profile.get("topic_keywords") or []), limit=12),
                "cluster_ids": [link["cluster_id"] for link in cluster_links],
                "cluster_links": cluster_links,
                "representative_articles": [],
            }
        articles = [
            self._topic_article(row, include_digest=True)
            for row in self._topic_rows()
            if str(row.get("topic_id") or "") == topic_id
        ]
        articles.sort(key=lambda item: str(item.get("processed_at") or ""), reverse=True)
        topic = {**topic, "article_count": len(articles), "completed_count": len(articles)}
        topic["cluster_coverage"] = self._cluster_coverage_for_topic(topic)
        topic["cluster_coverage_status"] = topic["cluster_coverage"]["status"]
        return {
            "topic": topic,
            "articles": articles,
        }

    def get_topic_cluster_coverage(self, topic_id: str) -> dict[str, Any]:
        self._validate_topic_id(topic_id)
        topics = {topic["topic_id"]: topic for topic in self.list_topics()}
        topic = topics.get(topic_id)
        if topic is None:
            profile = self._topic_profile(topic_id)
            cluster_links = self._cluster_links_for_topic(topic_id)
            topic = {
                "topic_id": topic_id,
                "title": str(profile.get("display_name") or profile.get("title") or topic_id),
                "display_name": str(profile.get("display_name") or profile.get("title") or topic_id),
                "article_count": 0,
                "completed_count": 0,
                "needs_review_count": 0,
                "last_processed_at": "",
                "top_concepts": _compact_list(list(profile.get("concept_seeds") or []) + list(profile.get("topic_keywords") or [])),
                "topic_keywords": _compact_list(list(profile.get("topic_keywords") or []), limit=12),
                "cluster_ids": [link["cluster_id"] for link in cluster_links],
                "cluster_links": cluster_links,
                "representative_articles": [],
            }
        return self._cluster_coverage_for_topic(topic)

    def set_topic_cluster_coverage_override(self, topic_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_topic_id(topic_id)
        if not isinstance(payload, dict):
            raise WikiIntakeStoreError("JSON body must be an object")
        status = str(payload.get("status") or "").strip()
        if status not in COVERAGE_OVERRIDE_STATUSES:
            raise WikiIntakeStoreError(f"status must be one of {sorted(COVERAGE_OVERRIDE_STATUSES)}")
        row = {
            "schema_version": "topic-cluster-coverage-override.v1",
            "topic_id": topic_id,
            "status": status,
            "note": str(payload.get("note") or ""),
            "operator": str(payload.get("operator") or "human"),
            "updated_at": now_iso(),
            "side_effects": {
                "modified_obsidian_source": False,
                "created_topic_cluster": False,
                "created_topic_cluster_link": False,
                "created_kfc_project": False,
                "called_llm": False,
            },
        }
        _append_jsonl(self.topic_cluster_coverage_path, row)
        return {"override": row, "coverage": self.get_topic_cluster_coverage(topic_id)}

    def link_topic_to_cluster(self, topic_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_topic_id(topic_id)
        if not isinstance(payload, dict):
            raise WikiIntakeStoreError("JSON body must be an object")
        cluster_id = str(payload.get("cluster_id") or "").strip()
        if not SAFE_TOPIC_ID_PATTERN.match(cluster_id):
            raise WikiIntakeStoreError("cluster_id is required")
        topic = self.get_topic_articles(topic_id)["topic"]
        store = TopicClusterStore()
        if store.get_cluster(cluster_id) is None:
            raise WikiIntakeStoreError(f"topic cluster not found: {cluster_id}", code="not_found", status_code=404)
        existing = store.find_by_target("wiki_topic", topic_id).get("items", [])
        for item in existing:
            link = item.get("link") or {}
            if link.get("cluster_id") != cluster_id:
                continue
            if link.get("status") == "accepted":
                return {"link": link, "coverage": self.get_topic_cluster_coverage(topic_id), "created": False}
            updated = store.update_cluster_link(
                str(link.get("link_id") or ""),
                {
                    "role": str(payload.get("role") or link.get("role") or "primary"),
                    "status": "accepted",
                    "rationale": str(payload.get("rationale") or "Human confirmed Wiki Topic Cluster Coverage link."),
                    "review_decision": {
                        "decision": "accepted",
                        "reviewed_by": str(payload.get("operator") or "human"),
                        "reason": str(payload.get("rationale") or "Accepted from Wiki Topic Cluster Coverage panel."),
                        "reviewed_at": now_iso(),
                    },
                },
            )
            return {"link": updated["link"], "coverage": self.get_topic_cluster_coverage(topic_id), "created": False}
        try:
            created = store.create_cluster_link(
                cluster_id,
                {
                    "target_type": "wiki_topic",
                    "target_id": topic_id,
                    "target_title": topic.get("title") or topic_id,
                    "role": str(payload.get("role") or "primary"),
                    "status": "accepted",
                    "source": "human_topic_cluster_coverage",
                    "confidence": payload.get("confidence"),
                    "rationale": str(payload.get("rationale") or "Human confirmed from Wiki Topic Cluster Coverage panel."),
                    "review_decision": {
                        "decision": "accepted",
                        "reviewed_by": str(payload.get("operator") or "human"),
                        "reason": str(payload.get("rationale") or "Accepted from Wiki Topic Cluster Coverage panel."),
                        "reviewed_at": now_iso(),
                    },
                },
            )
        except TopicClusterStoreError as exc:
            raise WikiIntakeStoreError(str(exc), code=getattr(exc, "code", "validation_error"), status_code=getattr(exc, "status_code", 400)) from exc
        return {"link": created["link"], "warnings": created.get("warnings", []), "coverage": self.get_topic_cluster_coverage(topic_id), "created": True}

    def request_topic_cluster_proposal(self, topic_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_topic_id(topic_id)
        if not isinstance(payload, dict):
            raise WikiIntakeStoreError("JSON body must be an object")
        topic = self.get_topic_articles(topic_id)["topic"]
        request_payload = {
            "scope": "wiki_topic",
            "topic_id": topic_id,
            "topic_title": topic.get("title") or topic_id,
            "suggested_title": str(payload.get("suggested_title") or topic.get("title") or topic_id),
            "rationale": str(payload.get("rationale") or "Human requested a new Topic Cluster proposal from Wiki Topic coverage."),
            "source": "wiki_topic_cluster_coverage",
            "inputs": {
                "include_wiki_topics": True,
                "include_kfc_themes": False,
                "include_kfc_concepts": False,
                "include_research_projects": False,
            },
        }
        try:
            request_obj = TopicClusterRefreshRequestStore().create(request_payload)
        except TopicClusterRefreshRequestStoreError as exc:
            raise WikiIntakeStoreError(str(exc), code=getattr(exc, "code", "validation_error"), status_code=getattr(exc, "status_code", 400)) from exc
        return {"request": request_obj, "coverage": self.get_topic_cluster_coverage(topic_id)}

    def get_topic_context_for_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        candidate_id = str(candidate_id or "").strip()
        if not candidate_id:
            return None
        latest_processed = self._latest_processed_for_candidate(candidate_id)
        if latest_processed and str(latest_processed.get("association_status") or "") == "unlinked":
            return None
        rows = self._topic_rows()
        completed = next(
            (
                row
                for row in rows
                if candidate_id in {str(row.get("candidate_id") or ""), str(row.get("source_id") or "")}
            ),
            None,
        )
        if completed and str(completed.get("association_status") or "") == "unlinked":
            return None
        topic_id = str((completed or {}).get("topic_id") or "").strip()
        if not topic_id:
            manifest = {
                str(item.get("candidate_id") or item.get("source_id") or ""): item
                for item in _read_jsonl(self.manifest_path)
            }
            record = manifest.get(candidate_id)
            guessed = record.get("guessed_topics") if record else []
            if isinstance(guessed, list) and guessed:
                first = guessed[0]
                topic_id = str(first.get("topic_id") if isinstance(first, dict) else first).strip()
        if not topic_id or not SAFE_TOPIC_ID_PATTERN.match(topic_id):
            return None
        detail = self.get_topic_articles(topic_id)
        topic = detail["topic"]
        recent = detail["articles"][:5]
        return {
            "topic_id": topic_id,
            "title": topic.get("title") or topic_id,
            "display_name": topic.get("display_name") or topic.get("title") or topic_id,
            "article_count": topic.get("article_count", 0),
            "completed_count": topic.get("completed_count", 0),
            "needs_review_count": topic.get("needs_review_count", 0),
            "cluster_ids": topic.get("cluster_ids", []),
            "cluster_links": topic.get("cluster_links", []),
            "recent_same_topic_articles": recent,
        }

    def change_candidate_primary_topic(self, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        candidate_id = str(candidate_id or "").strip()
        if not candidate_id:
            raise WikiIntakeStoreError("candidate_id is required")
        if not isinstance(payload, dict):
            raise WikiIntakeStoreError("JSON body must be an object")
        topic_id = str(payload.get("topic_id") or "").strip()
        self._validate_topic_id(topic_id)
        if not (self.wiki_hub_root / "topics" / topic_id).exists():
            raise WikiIntakeStoreError(f"topic not found: {topic_id}", code="not_found", status_code=404)
        current = self._latest_processed_for_candidate(candidate_id)
        if not current:
            raise WikiIntakeStoreError(f"processed candidate not found: {candidate_id}", code="not_found", status_code=404)
        previous_topic = str(current.get("topic_id") or "")
        row = {
            **current,
            "schema_version": "auto-processed-source.v1",
            "candidate_id": str(current.get("candidate_id") or candidate_id),
            "source_id": str(current.get("source_id") or candidate_id),
            "topic_id": topic_id,
            "association_role": "primary",
            "association_status": "active",
            "association_source": "manual_correction",
            "previous_topic_id": previous_topic,
            "correction_reason": str(payload.get("reason") or ""),
            "corrected_by": str(payload.get("operator") or "human"),
            "processed_at": now_iso(),
            "updated_at": now_iso(),
        }
        _append_jsonl(self.auto_processed_path, row)
        self._append_topic_association_event(
            {
                "event_type": "topic_primary_changed",
                "candidate_id": candidate_id,
                "from_topic_id": previous_topic,
                "to_topic_id": topic_id,
                "actor": str(payload.get("operator") or "human"),
                "reason": str(payload.get("reason") or ""),
            }
        )
        return {
            "association": row,
            "event": _read_jsonl(self.topic_association_events_path)[-1],
            "detail": self.get_candidate(candidate_id),
        }

    def unlink_candidate_primary_topic(self, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        candidate_id = str(candidate_id or "").strip()
        if not candidate_id:
            raise WikiIntakeStoreError("candidate_id is required")
        if not isinstance(payload, dict):
            raise WikiIntakeStoreError("JSON body must be an object")
        current = self._latest_processed_for_candidate(candidate_id)
        if not current:
            raise WikiIntakeStoreError(f"processed candidate not found: {candidate_id}", code="not_found", status_code=404)
        previous_topic = str(current.get("topic_id") or "")
        row = {
            **current,
            "schema_version": "auto-processed-source.v1",
            "candidate_id": str(current.get("candidate_id") or candidate_id),
            "source_id": str(current.get("source_id") or candidate_id),
            "topic_id": "",
            "association_role": "primary",
            "association_status": "unlinked",
            "association_source": "manual_correction",
            "previous_topic_id": previous_topic,
            "needs_topic_review": True,
            "correction_reason": str(payload.get("reason") or ""),
            "corrected_by": str(payload.get("operator") or "human"),
            "processed_at": now_iso(),
            "updated_at": now_iso(),
        }
        _append_jsonl(self.auto_processed_path, row)
        self._append_topic_association_event(
            {
                "event_type": "topic_primary_unlinked",
                "candidate_id": candidate_id,
                "from_topic_id": previous_topic,
                "to_topic_id": "",
                "actor": str(payload.get("operator") or "human"),
                "reason": str(payload.get("reason") or ""),
            }
        )
        return {
            "association": row,
            "event": _read_jsonl(self.topic_association_events_path)[-1],
            "detail": self.get_candidate(candidate_id),
        }

    def _latest_processed_for_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        rows = _read_jsonl(self.auto_processed_path)
        matches = [
            row for row in rows
            if candidate_id in {str(row.get("candidate_id") or ""), str(row.get("source_id") or "")}
        ]
        if not matches:
            return None
        matches.sort(key=lambda row: str(row.get("processed_at") or row.get("updated_at") or ""))
        return dict(matches[-1])

    def _append_topic_association_event(self, payload: dict[str, Any]) -> None:
        _append_jsonl(
            self.topic_association_events_path,
            {
                "schema_version": "topic-association-event.v1",
                "created_at": now_iso(),
                "side_effects": {
                    "modified_obsidian_source": False,
                    "created_kfc_project": False,
                    "called_llm": False,
                },
                **payload,
            },
        )

    def append_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if not candidate_id:
            raise WikiIntakeStoreError("candidate_id is required")
        decision = str(payload.get("decision") or payload.get("decision_status") or "").strip()
        if decision not in DECISION_STATUSES:
            raise WikiIntakeStoreError(f"invalid decision: {decision}")
        target = str(payload.get("target") or payload.get("gate1_destination") or "wiki").strip()
        if target not in DESTINATIONS:
            raise WikiIntakeStoreError(f"invalid target: {target}")
        candidates = {str(item.get("candidate_id") or item.get("source_id") or ""): item for item in _read_jsonl(self.manifest_path)}
        if candidate_id not in candidates:
            raise WikiIntakeStoreError(f"candidate not found: {candidate_id}", code="not_found", status_code=404)
        row = {
            "schema_version": "decision.v1",
            "candidate_id": candidate_id,
            "title": candidates[candidate_id].get("title", ""),
            "source_file_path": candidates[candidate_id].get("source_file_path", ""),
            "content_hash": candidates[candidate_id].get("content_hash", ""),
            "decision_status": decision,
            "gate1_destination": _legacy_destination(target),
            "target": target,
            "note": str(payload.get("note") or ""),
            "operator": str(payload.get("operator") or "human"),
            "decided_at": now_iso(),
            "tool_version": "kfc-wiki-intake-store-0.1",
            "side_effects": {
                "modified_obsidian_source": False,
                "copied_to_llm_wiki": False,
                "created_kfc_project": False,
                "called_llm": False,
            },
        }
        _append_jsonl(self.decisions_path, row)
        if decision == "accepted" and target in {"wiki", "both", "llm_wiki_only"}:
            row["enqueue"] = self.enqueue_candidate(candidate_id)
        return row

    def stats(self, *, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        records = items if items is not None else self._annotated_candidates()
        status_counts = Counter(str(item.get("status") or "pending") for item in records)
        return {
            "total": len(records),
            "pending": status_counts.get("pending", 0),
            "accepted": status_counts.get("accepted", 0),
            "deferred": status_counts.get("deferred", 0),
            "rejected": status_counts.get("rejected", 0),
            "duplicate": status_counts.get("duplicate", 0),
            "needs_human_review": status_counts.get("needs_human_review", 0),
            "completed": status_counts.get("completed", 0),
            "by_status": dict(status_counts),
        }

    def _topic_rows(self) -> list[dict[str, Any]]:
        manifest = self._manifest_by_id()
        latest = _latest_by(_read_jsonl(self.auto_processed_path), "candidate_id", "processed_at")
        if not latest:
            latest = _latest_by(_read_jsonl(self.auto_processed_path), "source_id", "processed_at")
        rows = []
        for row in latest.values():
            topic_id = str(row.get("topic_id") or "").strip()
            if not topic_id or not SAFE_TOPIC_ID_PATTERN.match(topic_id):
                continue
            candidate_id = str(row.get("candidate_id") or row.get("source_id") or "").strip()
            source_id = str(row.get("source_id") or candidate_id).strip()
            manifest_record = manifest.get(candidate_id) or manifest.get(source_id) or {}
            rows.append({**row, "_manifest": manifest_record, "candidate_id": candidate_id, "source_id": source_id})
        return rows

    def _manifest_by_id(self) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for record in _read_jsonl(self.manifest_path):
            for key in (record.get("candidate_id"), record.get("source_id")):
                text = str(key or "").strip()
                if text:
                    by_id[text] = record
        return by_id

    def _topic_profile(self, topic_id: str) -> dict[str, Any]:
        self._validate_topic_id(topic_id)
        path = self.wiki_hub_root / "topics" / topic_id / "topic_profile.json"
        if not path.exists():
            return {"topic_id": topic_id, "display_name": topic_id, "concept_seeds": [], "topic_keywords": []}
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"topic_id": topic_id, "display_name": topic_id, "concept_seeds": [], "topic_keywords": []}
        if not isinstance(profile, dict):
            return {"topic_id": topic_id, "display_name": topic_id, "concept_seeds": [], "topic_keywords": []}
        profile.setdefault("topic_id", topic_id)
        profile.setdefault("display_name", topic_id)
        profile.setdefault("concept_seeds", [])
        profile.setdefault("topic_keywords", [])
        return profile

    def _topic_article(self, row: dict[str, Any], *, include_digest: bool = False) -> dict[str, Any]:
        manifest = row.get("_manifest") if isinstance(row.get("_manifest"), dict) else {}
        digest = self._read_digest(row.get("verified_digest_json_path")) if include_digest else {}
        title = str(
            digest.get("title")
            or digest.get("source_title")
            or manifest.get("title")
            or self._title_from_article_path(row)
            or row.get("source_id")
            or row.get("candidate_id")
            or ""
        )
        concepts = _compact_list(
            list(digest.get("core_concepts") or [])
            + list(digest.get("top_concepts") or [])
            + list(digest.get("concepts") or []),
            limit=8,
        )
        source_url = str(digest.get("original_source_url") or manifest.get("source_url") or "")
        article = {
            "candidate_id": str(row.get("candidate_id") or ""),
            "intake_item_id": str(row.get("candidate_id") or row.get("source_id") or ""),
            "source_id": str(row.get("source_id") or row.get("candidate_id") or ""),
            "topic_id": str(row.get("topic_id") or ""),
            "title": title,
            "source_url": source_url,
            "source_type": str(manifest.get("source_type") or "markdown"),
            "status": "completed",
            "processed_at": str(row.get("processed_at") or ""),
            "digest_summary": str(digest.get("safe_summary") or digest.get("summary") or digest.get("safe_statement") or ""),
            "top_concepts": concepts,
            "markdown_path": str(row.get("source_md") or manifest.get("source_file_path") or ""),
            "raw_article_path": str(row.get("raw_article_path") or ""),
            "verified_digest_json_path": str(row.get("verified_digest_json_path") or ""),
            "verified_digest_md_path": str(row.get("verified_digest_md_path") or ""),
            "sources_path": str(row.get("sources_path") or ""),
            "compile_run_id": str(row.get("compile_run_id") or ""),
        }
        if digest.get("_digest_read_error"):
            article["digest_read_error"] = digest["_digest_read_error"]
        return article

    def _read_digest(self, path_value: Any) -> dict[str, Any]:
        path_text = str(path_value or "").strip()
        if not path_text:
            return {}
        path = Path(path_text).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"_digest_read_error": "missing_digest_json"}
        except (OSError, json.JSONDecodeError):
            return {"_digest_read_error": "invalid_digest_json"}
        return payload if isinstance(payload, dict) else {"_digest_read_error": "invalid_digest_json"}

    def _title_from_article_path(self, row: dict[str, Any]) -> str:
        path = Path(str(row.get("raw_article_path") or ""))
        if not path.exists():
            return ""
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:20]:
                if line.startswith("title:"):
                    return line.split(":", 1)[1].strip().strip('"')
                if line.startswith("# "):
                    return line[2:].strip()
        except OSError:
            return ""
        return ""

    def _cluster_links_for_topic(self, topic_id: str) -> list[dict[str, Any]]:
        try:
            result = TopicClusterStore().find_by_target("wiki_topic", topic_id)
        except TopicClusterStoreError:
            return []
        links = []
        for item in result.get("items", []):
            cluster = item.get("cluster") or {}
            link = item.get("link") or {}
            cluster_id = str(cluster.get("cluster_id") or link.get("cluster_id") or "")
            if cluster_id:
                links.append(
                    {
                        "cluster_id": cluster_id,
                        "title": str(cluster.get("title") or link.get("target_title") or cluster_id),
                        "link_id": str(link.get("link_id") or ""),
                        "status": str(link.get("status") or ""),
                        "role": str(link.get("role") or ""),
                        "confidence": link.get("confidence"),
                        "rationale": str(link.get("rationale") or ""),
                    }
                )
        return links

    def _cluster_coverage_overrides(self) -> dict[str, dict[str, Any]]:
        return _latest_by(_read_jsonl(self.topic_cluster_coverage_path), "topic_id", "updated_at")

    def _cluster_coverage_for_topic(self, topic: dict[str, Any]) -> dict[str, Any]:
        topic_id = str(topic.get("topic_id") or "").strip()
        links = list(topic.get("cluster_links") or self._cluster_links_for_topic(topic_id))
        accepted = [link for link in links if link.get("status") == "accepted"]
        candidate_links = [
            {
                "cluster_id": link.get("cluster_id"),
                "title": link.get("title") or link.get("cluster_id"),
                "status": link.get("status") or "candidate",
                "role": link.get("role") or "candidate",
                "confidence": link.get("confidence"),
                "reason": link.get("rationale") or "Existing unaccepted TopicClusterLink.",
                "source": "topic_cluster_link",
            }
            for link in links
            if link.get("status") in {"candidate", "needs_review"}
        ]
        generated = self._candidate_clusters_for_topic(topic, exclude_ids={str(link.get("cluster_id") or "") for link in links})
        candidates = (candidate_links + generated)[:5]
        override = self._cluster_coverage_overrides().get(topic_id)
        manual_status = str((override or {}).get("status") or "")
        if accepted:
            status = "linked"
            recommendation = "已正式关联到 Topic Cluster。"
        elif manual_status in COVERAGE_OVERRIDE_STATUSES:
            status = manual_status
            recommendation = {
                "watch": "先观察，暂不强制归集。",
                "ignored": "人工判断暂不纳入 Topic Cluster。",
                "needs_cluster": "人工标记需要进入新建或归集处理。",
            }[manual_status]
        elif candidates:
            status = "candidate"
            recommendation = "存在候选 Cluster，等待人工确认。"
        elif int(topic.get("article_count") or 0) >= 3:
            status = "needs_cluster"
            recommendation = "文章数达到归集阈值，建议人工判断是否新建或归入 Cluster。"
        else:
            status = "watch"
            recommendation = "文章数较少，先观察，避免 Cluster 泛滥。"
        return {
            "topic_id": topic_id,
            "status": status,
            "linked_clusters": accepted,
            "candidate_clusters": candidates,
            "candidate_count": len(candidates),
            "manual_override": override,
            "reason": self._coverage_reason(topic, status, candidates),
            "recommendation": recommendation,
            "allowed_actions": {
                "link_existing_cluster": True,
                "request_new_cluster": status in {"candidate", "needs_cluster", "watch"},
                "mark_watch": status not in {"linked", "watch"},
                "mark_ignored": status != "linked",
                "mark_needs_cluster": status not in {"linked", "needs_cluster"},
            },
        }

    def _coverage_reason(self, topic: dict[str, Any], status: str, candidates: list[dict[str, Any]]) -> str:
        if status == "linked":
            return "Topic has at least one accepted TopicClusterLink."
        if status == "candidate" and candidates:
            terms = ", ".join(candidates[0].get("matched_terms") or [])
            return f"Matched candidate Cluster terms: {terms}" if terms else "Found unconfirmed candidate clusters."
        if status == "needs_cluster":
            return "No accepted Cluster link; this topic is marked for explicit cluster decision."
        if status == "ignored":
            return "Human override says this topic does not need cluster coverage now."
        return "No accepted Cluster link; topic remains visible in the coverage queue."

    def _candidate_clusters_for_topic(self, topic: dict[str, Any], *, exclude_ids: set[str]) -> list[dict[str, Any]]:
        topic_terms = self._terms_for_text(
            " ".join(
                [
                    str(topic.get("topic_id") or ""),
                    str(topic.get("title") or ""),
                    " ".join(topic.get("top_concepts") or []),
                    " ".join(topic.get("topic_keywords") or []),
                    " ".join(str(article.get("title") or "") for article in topic.get("representative_articles") or []),
                ]
            )
        )
        if not topic_terms:
            return []
        try:
            clusters = TopicClusterStore().list_clusters(include_counts=False).get("items", [])
        except TopicClusterStoreError:
            return []
        candidates: list[dict[str, Any]] = []
        for cluster in clusters:
            cluster_id = str(cluster.get("cluster_id") or "")
            if not cluster_id or cluster_id in exclude_ids:
                continue
            cluster_terms = self._terms_for_text(
                " ".join([cluster_id, str(cluster.get("title") or ""), str(cluster.get("description") or "")])
            )
            matched = sorted(topic_terms & cluster_terms)
            if len(matched) < 2:
                continue
            score = min(0.95, 0.45 + len(matched) * 0.1)
            candidates.append(
                {
                    "cluster_id": cluster_id,
                    "title": cluster.get("title") or cluster_id,
                    "status": cluster.get("status") or "candidate",
                    "confidence": round(score, 2),
                    "confidence_label": "high" if score >= 0.75 else "medium",
                    "matched_terms": matched[:8],
                    "reason": f"Matched topic/cluster terms: {', '.join(matched[:6])}",
                    "source": "deterministic_metadata_match",
                    "counts": cluster.get("counts") or {},
                }
            )
        candidates.sort(key=lambda item: (-float(item.get("confidence") or 0), str(item.get("title") or "").lower()))
        return candidates[:3]

    def _terms_for_text(self, text: str) -> set[str]:
        raw_terms = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", str(text or "").lower())
        stop = {"and", "the", "for", "with", "from", "into", "topic", "cluster", "wiki", "data"}
        return {term for term in raw_terms if len(term) >= 2 and term not in stop}

    def _needs_review_count_for_topic(
        self,
        topic_id: str,
        candidates: list[dict[str, Any]],
        completed_rows: list[dict[str, Any]],
    ) -> int:
        completed_ids = {
            str(row.get("candidate_id") or row.get("source_id") or "")
            for row in completed_rows
        }
        count = 0
        for item in candidates:
            candidate_id = str(item.get("candidate_id") or item.get("source_id") or "")
            if candidate_id in completed_ids:
                continue
            guessed = item.get("guessed_topics") or []
            guessed_ids = [
                str(value.get("topic_id") if isinstance(value, dict) else value)
                for value in guessed
            ] if isinstance(guessed, list) else []
            if topic_id in guessed_ids and item.get("status") == "needs_human_review":
                count += 1
        return count

    def _validate_topic_id(self, topic_id: str) -> None:
        if not SAFE_TOPIC_ID_PATTERN.match(str(topic_id or "")):
            raise WikiIntakeStoreError("invalid topic_id")

    def list_runs(self) -> dict[str, Any]:
        run_root = self.data_root / "auto_runs"
        items = []
        if run_root.exists():
            for path in sorted(run_root.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
                if path.is_dir():
                    items.append({"run_id": path.name, "path": str(path)})
        return {"items": items, "total": len(items), "runner_enabled": True}

    def _sync_topic_cluster_link(self, runner_result: dict[str, Any]) -> dict[str, Any]:
        if runner_result.get("status") != "completed":
            return {"ok": True, "status": "skipped", "reason": "runner_not_completed"}
        apply_result = runner_result.get("apply") or (runner_result.get("result") or {}).get("apply") or {}
        processed = apply_result.get("processed") or {}
        topic_id = str(processed.get("topic_id") or "").strip()
        if not topic_id:
            return {"ok": True, "status": "skipped", "reason": "missing_topic_id"}
        coverage = self.get_topic_cluster_coverage(topic_id)
        return {
            "ok": True,
            "status": "coverage_only",
            "topic_id": topic_id,
            "coverage_status": coverage.get("status"),
            "candidate_count": coverage.get("candidate_count", 0),
            "reason": "auto_cluster_sync_disabled_human_confirmation_required",
            "side_effects": {
                "created_topic_cluster": False,
                "created_topic_cluster_link": False,
                "created_kfc_project": False,
                "called_llm": False,
            },
        }

    def _topic_title(self, topic_id: str) -> str:
        profile_path = self.wiki_hub_root / "topics" / topic_id / "topic_profile.json"
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                return str(profile.get("display_name") or profile.get("topic_id") or topic_id)
            except (OSError, json.JSONDecodeError):
                pass
        return topic_id


def _legacy_destination(target: str) -> str:
    if target == "wiki":
        return "llm_wiki_only"
    if target == "kfc":
        return "kfc_only"
    if target in {"both", "neither", "llm_wiki_only", "kfc_only"}:
        return target
    return "llm_wiki_only"


def _ensure_runner_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts" / "wiki_intake"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _safe_cluster_suffix(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-_")
    return (safe or "topic")[:100]
