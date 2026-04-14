"""End-to-end runner that orchestrates one URL through the auto pipeline.

The runner is the only piece in the ``auto`` package that knows about the
full sequence: claim → fetch+build → verify → concept-decide → suggest →
register/link → propose theme → audit summary → mark processed.

It catches per-phase exceptions and routes them to ``mark_errored`` with
the phase tag so the user can see exactly where each failure occurred.

The runner does NOT depend on Flask app context. It can be invoked from a
CLI script, a REST endpoint, or a future scheduler.
"""

from __future__ import annotations

import concurrent.futures
import json as _json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from .build_verifier import BuildVerificationResult, BuildVerifier
from .concept_decider import AutoConceptDecider, ConceptDecision
from .pending_store import PendingUrlStore
from .registry_linker import AutoLinkSummary, AutoRegistryLinker
from .theme_proposer import AutoThemeProposer, AutoThemeResult
from .url_fingerprint import compute_content_hash


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Watchdog configuration (read from env with conservative defaults)
# ---------------------------------------------------------------------------

# Total per-URL timeout. After this many seconds of real time, the runner
# gives up on the current URL, cancels any live build tasks for it, and
# marks the URL errored. 20 minutes is long enough for a normal WeChat
# article with 15 chunks on local qwen3-30b and short enough that a stuck
# URL won't dominate an 8-hour overnight window.
AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS = int(
    os.environ.get("AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS", "1200")
)

# No-progress window. If the latest build task's progress + message stay
# identical for this many seconds, we consider it stuck and cancel.
AUTO_PIPELINE_STALL_TIMEOUT_SECONDS = int(
    os.environ.get("AUTO_PIPELINE_STALL_TIMEOUT_SECONDS", "240")
)

# Poll interval for the watchdog loop.
AUTO_PIPELINE_WATCHDOG_INTERVAL_SECONDS = int(
    os.environ.get("AUTO_PIPELINE_WATCHDOG_INTERVAL_SECONDS", "15")
)


class AutoPipelineTimeoutError(RuntimeError):
    """Raised when the per-URL watchdog gives up on a stuck pipeline run.

    Distinct from generic RuntimeError so the runner can mark the URL as
    ``errored_timeout`` (retryable) rather than a hard ``errored`` fail.
    """

    def __init__(self, reason: str, *, phase: str, task_id: Optional[str] = None):
        super().__init__(reason)
        self.phase = phase
        self.task_id = task_id


@dataclass
class RunOutcome:
    run_id: str
    url: str
    status: str  # "processed" | "errored" | "skipped_duplicate"
    project_id: Optional[str] = None
    graph_id: Optional[str] = None
    duration_ms: int = 0
    summary: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    phase: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "url": self.url,
            "status": self.status,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "duration_ms": self.duration_ms,
            "summary": dict(self.summary),
            "error": self.error,
            "phase": self.phase,
        }


@dataclass
class DrainResult:
    runs: list[RunOutcome] = field(default_factory=list)
    recovered: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovered": dict(self.recovered),
            "runs": [r.to_dict() for r in self.runs],
            "total_runs": len(self.runs),
        }


class AutoPipelineRunner:
    """Drive a single URL through the auto pipeline end-to-end."""

    def __init__(
        self,
        *,
        store: Optional[PendingUrlStore] = None,
        backend_base_url: Optional[str] = None,
        verifier: Optional[BuildVerifier] = None,
        decider: Optional[AutoConceptDecider] = None,
        linker: Optional[AutoRegistryLinker] = None,
        theme_proposer: Optional[AutoThemeProposer] = None,
        actor_id: str = "auto_pipeline",
        source: str = "auto_url_pipeline",
    ) -> None:
        self.store = store or PendingUrlStore()
        self.backend_base_url = (
            backend_base_url
            or os.environ.get("MIROFISH_BACKEND_BASE_URL")
            or "http://127.0.0.1:5001"
        )
        self.verifier = verifier or BuildVerifier()
        self.decider = decider or AutoConceptDecider()
        self.linker = linker or AutoRegistryLinker(
            actor_id=actor_id, source=source
        )
        self.theme_proposer = theme_proposer or AutoThemeProposer(
            actor_id=actor_id, source=source
        )
        self.actor_id = actor_id
        self.source = source

    # ------------------------------------------------------------------
    # Drain loop
    # ------------------------------------------------------------------

    def run_until_drained(
        self, *, max_runs: Optional[int] = None
    ) -> DrainResult:
        """Process pending URLs until the queue is empty.

        Args:
            max_runs: optional safety cap so a single CLI invocation cannot
                eat the entire queue (defaults to no cap).
        """
        recovered = self.store.recover_stale_inflight()
        result = DrainResult(recovered=recovered)

        executed = 0
        while True:
            if max_runs is not None and executed >= max_runs:
                break
            claimed = self.store.claim_next()
            if claimed is None:
                break
            outcome = self._run_claimed(claimed)
            result.runs.append(outcome)
            executed += 1
        return result

    # ------------------------------------------------------------------
    # Single URL processing
    # ------------------------------------------------------------------

    def _run_claimed(self, claimed: dict[str, Any]) -> RunOutcome:
        run_id: str = claimed["run_id"]
        # An entry is either a URL or a local markdown file; the OutcomeUrl
        # field displays whichever was used so the CLI output stays readable.
        md_path: str = claimed.get("md_path") or ""
        url: str = claimed.get("url") or (f"file://{md_path}" if md_path else "")
        started = time.monotonic()

        outcome = RunOutcome(run_id=run_id, url=url, status="errored")
        try:
            self.store.heartbeat(run_id, phase="fetch")
            if md_path:
                pipeline_result = self._invoke_article_pipeline_with_watchdog(
                    run_id=run_id,
                    invoke=lambda: self._invoke_article_pipeline_from_file(
                        md_path=md_path,
                        source_url=claimed.get("source_url") or None,
                    ),
                )
            else:
                pipeline_result = self._invoke_article_pipeline_with_watchdog(
                    run_id=run_id,
                    invoke=lambda: self._invoke_article_pipeline(url),
                )
            outcome.project_id = pipeline_result.get("project_id")
            outcome.graph_id = pipeline_result.get("graph_id")

            self.store.heartbeat(run_id, phase="verify")
            verification = self.verifier.verify(outcome.project_id or "")
            if not verification.ok:
                raise RuntimeError(f"build verification failed: {verification.reason}")

            self.store.heartbeat(run_id, phase="concept")
            decisions, candidate_signal = self._auto_accept_concepts(
                outcome.project_id or "", run_id=run_id
            )

            self.store.heartbeat(run_id, phase="registry")
            link_summary = self._auto_register_and_link(
                project_id=outcome.project_id or "",
                project_name=pipeline_result.get("project_name", ""),
                run_id=run_id,
                candidate_signal=candidate_signal,
            )

            self.store.heartbeat(run_id, phase="theme")
            theme_result = self._auto_propose_theme(
                project_id=outcome.project_id or "",
                project_name=pipeline_result.get("project_name", ""),
                article_title=pipeline_result.get("title", ""),
                new_canonical_ids=self._collect_canonical_ids(
                    project_id=outcome.project_id or "",
                    accepted_decisions=decisions,
                ),
                run_id=run_id,
            )

            self.store.heartbeat(run_id, phase="summarize")
            outcome.summary = self._build_summary(
                decisions=decisions,
                link_summary=link_summary,
                theme_result=theme_result,
                verification=verification,
            )
            outcome.duration_ms = int((time.monotonic() - started) * 1000)
            outcome.phase = "done"
            outcome.status = "processed"

            self._emit_run_summary(
                run_id=run_id,
                url=url,
                outcome=outcome,
            )
            self.store.mark_processed(
                run_id,
                project_id=outcome.project_id or "",
                graph_id=outcome.graph_id or "",
                content_hash=pipeline_result.get("content_hash"),
                summary=outcome.summary,
                duration_ms=outcome.duration_ms,
            )
        except AutoPipelineTimeoutError as timeout_exc:
            logger.warning(
                "auto pipeline run %s timed out in phase=%s: %s",
                run_id,
                timeout_exc.phase,
                timeout_exc,
            )
            outcome.duration_ms = int((time.monotonic() - started) * 1000)
            outcome.error = str(timeout_exc)
            outcome.phase = timeout_exc.phase or "timeout"
            outcome.status = "errored"
            try:
                self.store.mark_errored(
                    run_id,
                    error=f"timeout: {timeout_exc}",
                    phase=f"errored_timeout:{outcome.phase}",
                    project_id=outcome.project_id,
                    graph_id=outcome.graph_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception("failed to mark errored_timeout for run %s", run_id)
            self._emit_timeout_audit(
                run_id=run_id,
                url=url,
                outcome=outcome,
                timeout_exc=timeout_exc,
            )
        except Exception as error:  # noqa: BLE001
            logger.exception("auto pipeline run %s failed", run_id)
            outcome.duration_ms = int((time.monotonic() - started) * 1000)
            outcome.error = str(error)
            outcome.phase = self._infer_phase(error)
            try:
                self.store.mark_errored(
                    run_id,
                    error=str(error),
                    phase=outcome.phase,
                    project_id=outcome.project_id,
                    graph_id=outcome.graph_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception("failed to mark errored for run %s", run_id)
        return outcome

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _build_article_pipeline(self):
        """Construct an ``ArticleWorkspacePipeline`` using environment defaults.

        Deferred import + construction means the runner can be unit-tested
        with a fake article pipeline injected via subclass, and unused
        config (e.g. the fetch script) does not break local-file-only runs.
        """
        from ..article_workspace_pipeline import (
            ArticleWorkspacePipeline,
            DEFAULT_NOTE_SUBDIR,
        )

        vault_root = (
            os.environ.get("KNOWLEDGE_WORKSPACE_VAULT_ROOT")
            or os.path.expanduser("~/Downloads/OB笔记")
        )
        frontend_base = (
            os.environ.get("KNOWLEDGE_WORKSPACE_FRONTEND")
            or "http://127.0.0.1:3001"
        )
        backend_base = (
            os.environ.get("KNOWLEDGE_WORKSPACE_BACKEND")
            or self.backend_base_url
        )
        fetch_script = (
            os.environ.get("AUTO_PIPELINE_FETCH_SCRIPT")
            or "/Users/mac/.openclaw/workspace/skills/web-content-fetcher/fetch.sh"
        )
        return ArticleWorkspacePipeline(
            vault_root=vault_root,
            frontend_base_url=frontend_base,
            backend_base_url=backend_base,
            fetch_script_path=fetch_script,
            note_subdir=DEFAULT_NOTE_SUBDIR,
        )

    def _normalize_pipeline_result(self, result) -> dict[str, Any]:
        result_dict = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        md_path = result_dict.get("md_path") or ""
        content_hash = None
        if md_path and os.path.exists(md_path):
            try:
                content_hash = compute_content_hash(open(md_path, encoding="utf-8").read())
            except Exception:  # noqa: BLE001
                content_hash = None
        result_dict["content_hash"] = content_hash
        result_dict.setdefault(
            "project_name", result_dict.get("title") or "Auto pipeline project"
        )
        return result_dict

    def _invoke_article_pipeline(self, url: str) -> dict[str, Any]:
        """Call ``ArticleWorkspacePipeline.process_url`` and normalize result."""
        pipeline = self._build_article_pipeline()
        result = pipeline.process_url(url=url)
        return self._normalize_pipeline_result(result)

    def _invoke_article_pipeline_with_watchdog(
        self,
        *,
        run_id: str,
        invoke,
    ) -> dict[str, Any]:
        """Run the article pipeline in a worker thread under watchdog supervision.

        GPT-consulted design: the runner cannot kill the Graphiti daemon
        thread, and ``ArticleWorkspacePipeline.process_url`` internally
        polls the graph build task without any external abort hook. The
        watchdog compromise is:

        1. Start ``invoke()`` in a ``ThreadPoolExecutor`` (daemon thread)
        2. Poll every ``AUTO_PIPELINE_WATCHDOG_INTERVAL_SECONDS`` seconds:
           - If worker finished, collect the result.
           - Heartbeat the pending-urls.json entry.
           - Look up the most recent build task whose graph_id matches
             one of our active projects. Record its progress + message.
           - If total elapsed exceeds ``AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS``,
             cancel the build task (cooperative) and raise TimeoutError.
           - If progress + message haven't changed for
             ``AUTO_PIPELINE_STALL_TIMEOUT_SECONDS``, cancel and raise.

        The worker thread continues running in the background after a
        timeout (daemon, backend-process-lifetime bounded). It will
        eventually hit the chunk-boundary cancel check and exit cleanly.
        """
        started = time.monotonic()
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"auto_pipeline_{run_id}",
        )
        future = executor.submit(invoke)

        last_progress_signature: Optional[tuple[int, str]] = None
        stall_start: Optional[float] = None
        watched_task_id: Optional[str] = None
        last_phase = "build"

        try:
            while True:
                try:
                    result = future.result(
                        timeout=AUTO_PIPELINE_WATCHDOG_INTERVAL_SECONDS
                    )
                    return result
                except concurrent.futures.TimeoutError:
                    pass

                self.store.heartbeat(run_id, phase=last_phase)

                elapsed = time.monotonic() - started
                # Look up the latest build task so we can observe its
                # progress/message drift. We accept missing task info
                # silently — it just means the watchdog waits on the
                # total timeout instead of the stall timeout.
                snapshot = self._latest_build_task_snapshot()
                if snapshot is not None:
                    watched_task_id = snapshot.get("task_id") or watched_task_id
                    last_phase = (
                        "build_verify"
                        if snapshot.get("progress", 0) >= 55
                        else "build_extract"
                    )
                    current_sig = (
                        int(snapshot.get("progress") or 0),
                        str(snapshot.get("message") or ""),
                    )
                    if current_sig != last_progress_signature:
                        last_progress_signature = current_sig
                        stall_start = time.monotonic()
                    elif stall_start is None:
                        stall_start = time.monotonic()

                if elapsed > AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS:
                    self._request_cancel(
                        watched_task_id, reason="total timeout"
                    )
                    raise AutoPipelineTimeoutError(
                        f"total timeout after {int(elapsed)}s "
                        f"(limit {AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS}s)",
                        phase=last_phase,
                        task_id=watched_task_id,
                    )

                if (
                    stall_start is not None
                    and time.monotonic() - stall_start
                    > AUTO_PIPELINE_STALL_TIMEOUT_SECONDS
                ):
                    self._request_cancel(
                        watched_task_id, reason="no progress stall"
                    )
                    raise AutoPipelineTimeoutError(
                        f"no progress for "
                        f"{int(time.monotonic() - stall_start)}s "
                        f"(limit {AUTO_PIPELINE_STALL_TIMEOUT_SECONDS}s)",
                        phase=last_phase,
                        task_id=watched_task_id,
                    )
        finally:
            # Do NOT wait on the future — if we raised, the worker is
            # still running. Daemon ensures cleanup at process exit.
            executor.shutdown(wait=False, cancel_futures=False)

    def _latest_build_task_snapshot(self) -> Optional[dict[str, Any]]:
        """Return the newest graph build task record from the backend.

        The backend creates build tasks with a Chinese dynamic task_type
        like ``"构建图谱: {graph_name}"`` (see
        ``graph.py::build_graph``). We can't match on a fixed type string,
        so we look for the newest task that is ``processing`` AND whose
        task_type starts with ``"构建图谱"`` (defensive fallback: also
        match an English ``graph_build`` prefix in case the label gets
        standardized later).

        Returns ``None`` if the backend is unreachable or no processing
        build task exists.
        """
        try:
            body = self._http_get(f"{self.backend_base_url}/api/graph/tasks")
        except Exception:  # noqa: BLE001
            return None
        tasks = body.get("data") or []
        for task in tasks:
            if task.get("status") != "processing":
                continue
            task_type = str(task.get("task_type") or "")
            if task_type.startswith("构建图谱") or task_type.startswith("graph_build"):
                return task
        return None

    def _request_cancel(
        self, task_id: Optional[str], *, reason: str
    ) -> None:
        """Best-effort POST to the backend cancel endpoint."""
        if not task_id:
            return
        try:
            self._http_send(
                f"{self.backend_base_url}/api/graph/task/{task_id}/cancel",
                payload={"reason": reason},
                method="POST",
            )
            logger.info(
                "auto pipeline: requested cancel on task %s: %s",
                task_id,
                reason,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "auto pipeline: failed to request cancel on task %s", task_id
            )

    def _emit_timeout_audit(
        self,
        *,
        run_id: str,
        url: str,
        outcome: RunOutcome,
        timeout_exc: AutoPipelineTimeoutError,
    ) -> None:
        from ..registry.evolution_log import emit_event

        emit_event(
            event_type="auto_run_summary",
            entity_type="auto_run",
            entity_id=run_id,
            entity_name=url,
            project_id=outcome.project_id or "",
            details={
                "url": url,
                "outcome": "errored_timeout",
                "phase": timeout_exc.phase,
                "task_id": timeout_exc.task_id,
                "error": str(timeout_exc),
                "duration_ms": outcome.duration_ms,
            },
            actor_type="auto",
            actor_id=self.actor_id,
            run_id=run_id,
            source=self.source,
        )

    def _invoke_article_pipeline_from_file(
        self,
        *,
        md_path: str,
        source_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Feed a local markdown file through the article pipeline.

        This path is used for testing and for any future ingestion source
        that writes a raw markdown file without a live URL (e.g. a
        journaling export). It reuses the same downstream build path as
        the URL flow, so concept view + suggest behaviour is identical.
        """
        pipeline = self._build_article_pipeline()
        result = pipeline.process_markdown_file(
            markdown_file=md_path,
            source_url=source_url,
        )
        return self._normalize_pipeline_result(result)

    def _auto_accept_concepts(
        self, project_id: str, *, run_id: str
    ) -> tuple[list[ConceptDecision], dict[str, dict]]:
        """Run the concept decider and persist accepted decisions."""
        view = self._get_concept_view(project_id)
        candidates = view.get("candidateConcepts") or []
        candidate_signal = {c.get("key", ""): c for c in candidates}
        all_decisions = self.decider.decide_all(candidates)
        accepted = [d for d in all_decisions if d.decision == "accepted"]

        from ..registry.evolution_log import emit_event

        for decision in accepted:
            self._put_concept_decision(
                project_id=project_id,
                concept_key=decision.concept_key,
                canonical_name=decision.display_name,
                note=f"auto pipeline run {run_id}: {decision.reason}",
            )
            emit_event(
                event_type="concept_auto_accepted",
                entity_type="project_concept",
                entity_id=decision.concept_key,
                entity_name=decision.display_name,
                project_id=project_id,
                details={
                    "concept_type": decision.concept_type,
                    "connected_count": decision.connected_count,
                    "mention_count": decision.mention_count,
                    "reason": decision.reason,
                },
                actor_type="auto",
                actor_id=self.actor_id,
                run_id=run_id,
                source=self.source,
            )
        return accepted, candidate_signal

    def _auto_register_and_link(
        self,
        *,
        project_id: str,
        project_name: str,
        run_id: str,
        candidate_signal: dict[str, dict],
    ) -> AutoLinkSummary:
        suggest_payload = self._post_suggest_from_project(project_id)
        return self.linker.process(
            project_id=project_id,
            project_name=project_name,
            suggest_payload=suggest_payload,
            candidate_signal=candidate_signal,
            run_id=run_id,
        )

    def _auto_propose_theme(
        self,
        *,
        project_id: str,
        project_name: str,
        article_title: str,
        new_canonical_ids: list[str],
        run_id: str,
    ) -> AutoThemeResult:
        return self.theme_proposer.process(
            project_id=project_id,
            project_name=project_name,
            article_title=article_title,
            new_canonical_ids=new_canonical_ids,
            run_id=run_id,
        )

    # ------------------------------------------------------------------
    # Backend HTTP helpers (no Flask context required)
    # ------------------------------------------------------------------

    def _get_concept_view(self, project_id: str) -> dict[str, Any]:
        url = f"{self.backend_base_url}/api/concept/projects/{project_id}/view"
        body = self._http_get(url)
        return body.get("data") or {}

    def _put_concept_decision(
        self,
        *,
        project_id: str,
        concept_key: str,
        canonical_name: str,
        note: str,
    ) -> dict[str, Any]:
        encoded = urllib.parse.quote(concept_key, safe="")
        url = (
            f"{self.backend_base_url}/api/concept/projects/{project_id}/decisions/{encoded}"
        )
        payload = {
            "status": "accepted",
            "canonical_name": canonical_name,
            "note": note,
        }
        return self._http_send(url, payload, method="PUT")

    def _post_suggest_from_project(self, project_id: str) -> dict[str, Any]:
        url = f"{self.backend_base_url}/api/registry/suggest-from-project/{project_id}"
        body = self._http_send(url, payload={}, method="POST")
        return body.get("data") or {}

    @staticmethod
    def _http_get(url: str) -> dict[str, Any]:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        import json as _json
        return _json.loads(data.decode("utf-8"))

    @staticmethod
    def _http_send(url: str, payload: dict[str, Any], *, method: str) -> dict[str, Any]:
        import json as _json
        body = _json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        return _json.loads(data.decode("utf-8"))

    # ------------------------------------------------------------------
    # Result helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_canonical_ids(
        project_id: str, *, accepted_decisions: list[ConceptDecision]
    ) -> list[str]:
        """Return the canonical entry ids the linker just created or linked.

        We re-fetch the project's source links from the registry rather than
        try to track them in memory — this means even idempotent re-runs see
        the right list.
        """
        from ..registry import global_concept_registry as registry

        accepted_keys = {d.concept_key for d in accepted_decisions}
        canonical_ids: list[str] = []
        for entry in registry.list_entries():
            for link in entry.get("source_links") or []:
                if (
                    link.get("project_id") == project_id
                    and link.get("concept_key") in accepted_keys
                ):
                    if entry.get("entry_id") and entry["entry_id"] not in canonical_ids:
                        canonical_ids.append(entry["entry_id"])
                    break
        return canonical_ids

    @staticmethod
    def _build_summary(
        *,
        decisions: list[ConceptDecision],
        link_summary: AutoLinkSummary,
        theme_result: AutoThemeResult,
        verification: BuildVerificationResult,
    ) -> dict[str, Any]:
        return {
            "node_count": verification.node_count,
            "edge_count": verification.edge_count,
            "candidate_count": verification.candidate_count,
            "build_status": verification.build_status,
            "concept_decisions": {
                "accepted": len(decisions),
            },
            "registry": link_summary.to_dict(),
            "theme": theme_result.to_dict(),
        }

    def _emit_run_summary(
        self, *, run_id: str, url: str, outcome: RunOutcome
    ) -> None:
        from ..registry.evolution_log import emit_event

        emit_event(
            event_type="auto_run_summary",
            entity_type="auto_run",
            entity_id=run_id,
            entity_name=url,
            project_id=outcome.project_id or "",
            details={
                "url": url,
                "duration_ms": outcome.duration_ms,
                "summary": outcome.summary,
            },
            actor_type="auto",
            actor_id=self.actor_id,
            run_id=run_id,
            source=self.source,
        )

    @staticmethod
    def _infer_phase(error: Exception) -> str:
        """Map an exception message to a coarse phase label for the audit log."""
        msg = str(error).lower()
        if "build verification failed" in msg:
            return "verify"
        if "fetch" in msg and "fail" in msg:
            return "fetch"
        if "ontology" in msg:
            return "ontology"
        if "graph" in msg and "build" in msg:
            return "build"
        if "concept" in msg and "view" in msg:
            return "concept"
        if "suggest" in msg:
            return "registry"
        if "theme" in msg:
            return "theme"
        return "unknown"
