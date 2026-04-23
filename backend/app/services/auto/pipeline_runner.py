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
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from .build_verifier import BuildVerificationResult, BuildVerifier
from .concept_decider import AutoConceptDecider, ConceptDecision
from .discover_job_store import DiscoverJobStore
from .discover_skip_log import DiscoverSkipLog
from .pending_store import PendingUrlStore
from .registry_linker import AutoLinkSummary, AutoRegistryLinker
from .theme_proposer import AutoThemeProposer, AutoThemeResult
from .url_fingerprint import compute_content_hash


logger = logging.getLogger(__name__)


_DEFAULT_FRONTEND_BASE_URL = "http://localhost:3000"
_VITE_PORT_RE = re.compile(r"\bport\s*:\s*(\d+)")
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


# ---------------------------------------------------------------------------
# Watchdog configuration (read from env with conservative defaults)
# ---------------------------------------------------------------------------

# Total per-URL timeout. After this many seconds of real time, the runner
# gives up on the current URL, cancels any live build tasks for it, and
# marks the URL errored. 60 minutes covers long-form research articles
# (Deloitte Insights, long WeChat essays ~40k chars) under Bailian
# cloud-provider concurrency, while still bounding a stuck URL from
# dominating an 8-hour overnight window. The stall timeout below is the
# real "stuck" detector — total timeout is only the overnight guardrail.
AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS = int(
    os.environ.get("AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS", "3600")
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

# Once the graph task itself is already completed, only a short post-build
# tail should remain (reading-view capture, note writeback). If that tail
# hangs, recover from the durable project record instead of blocking the
# whole auto pipeline indefinitely.
AUTO_PIPELINE_POST_BUILD_GRACE_SECONDS = float(
    os.environ.get("AUTO_PIPELINE_POST_BUILD_GRACE_SECONDS", "30")
)


def _is_loopback_http_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return (parsed.hostname or "").strip().lower() in _LOOPBACK_HOSTS


class AutoPipelineTimeoutError(RuntimeError):
    """Raised when the per-URL watchdog gives up on a stuck pipeline run.

    Distinct from generic RuntimeError so the runner can mark the URL as
    ``errored_timeout`` (retryable) rather than a hard ``errored`` fail.

    ``project_id`` is captured from the build task's metadata while the
    watchdog is polling, so the errored-out record still points at the
    half-built project for manual recovery.
    """

    def __init__(
        self,
        reason: str,
        *,
        phase: str,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        super().__init__(reason)
        self.phase = phase
        self.task_id = task_id
        self.project_id = project_id


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
        discover_job_store: Optional[DiscoverJobStore] = None,
        discover_skip_log: Optional[DiscoverSkipLog] = None,
        actor_id: str = "auto_pipeline",
        source: str = "auto_url_pipeline",
    ) -> None:
        self.store = store or PendingUrlStore()
        self.discover_job_store = discover_job_store or DiscoverJobStore()
        self.discover_skip_log = discover_skip_log or DiscoverSkipLog()
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

        # Post-drain: mark a pending governance request so the Theme Hub can
        # surface it as a user-actionable banner. We do NOT run merge/promote
        # inline — governance is an independent-entry operation per GPT design.
        if executed > 0:
            self._mark_theme_governance_scan_requested(reason="post_drain")

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
            new_canonical_ids = self._collect_canonical_ids(
                project_id=outcome.project_id or "",
                accepted_decisions=decisions,
            )
            theme_result = self._auto_propose_theme(
                project_id=outcome.project_id or "",
                project_name=pipeline_result.get("project_name", ""),
                article_title=pipeline_result.get("title", ""),
                new_canonical_ids=new_canonical_ids,
                run_id=run_id,
            )

            # P1 (Discover V2): discover is no longer executed inline. The
            # pipeline only schedules a background job; a worker / the
            # scripts/run_discover_jobs.py drainer picks it up afterwards.
            # This keeps the main pipeline's wall-clock bounded by fetch +
            # build + verify + concept + registry + theme, which is the
            # user-visible latency.
            self.store.heartbeat(run_id, phase="discover")
            discover_stats = self._schedule_discover_job(
                theme_id=theme_result.theme_id,
                trigger_project_id=outcome.project_id or "",
                new_entry_ids=new_canonical_ids,
                run_id=run_id,
            )

            self.store.heartbeat(run_id, phase="summarize")
            outcome.summary = self._build_summary(
                decisions=decisions,
                link_summary=link_summary,
                theme_result=theme_result,
                verification=verification,
                discover_stats=discover_stats,
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
            # ``_invoke_article_pipeline_with_watchdog`` never returned, so
            # ``outcome.project_id`` is still None here. The watchdog
            # captured it from the build task metadata — fall back to that
            # so the errored record still points at the half-built project.
            if not outcome.project_id and timeout_exc.project_id:
                outcome.project_id = timeout_exc.project_id
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
        frontend_base = self._resolve_frontend_base_url()
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

    @staticmethod
    def _resolve_frontend_base_url() -> str:
        explicit = os.environ.get("KNOWLEDGE_WORKSPACE_FRONTEND")
        if explicit:
            return explicit.rstrip("/")

        vite_config = (
            Path(__file__).resolve().parents[4] / "frontend" / "vite.config.js"
        )
        try:
            match = _VITE_PORT_RE.search(vite_config.read_text(encoding="utf-8"))
        except OSError:
            match = None
        if match:
            return f"http://localhost:{match.group(1)}"
        return _DEFAULT_FRONTEND_BASE_URL

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
        watched_project_id: Optional[str] = None
        last_phase = "build"
        post_build_started_at: Optional[float] = None

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
                active_build_task = False
                if snapshot is not None:
                    active_build_task = True
                    watched_task_id = snapshot.get("task_id") or watched_task_id
                    snapshot_project_id = (
                        (snapshot.get("metadata") or {}).get("project_id")
                    )
                    if snapshot_project_id:
                        watched_project_id = snapshot_project_id
                    last_phase = (
                        "build_verify"
                        if snapshot.get("progress", 0) >= 55
                        else "build_extract"
                    )
                    current_sig = (
                        int(snapshot.get("progress") or 0),
                        str(snapshot.get("message") or ""),
                    )
                    post_build_started_at = None
                    if current_sig != last_progress_signature:
                        last_progress_signature = current_sig
                        stall_start = time.monotonic()
                    elif stall_start is None:
                        stall_start = time.monotonic()
                elif watched_task_id:
                    watched_snapshot = self._get_task_snapshot(watched_task_id)
                    watched_status = str((watched_snapshot or {}).get("status") or "")
                    if watched_status in {"completed", "failed", "cancelled"}:
                        # Once the build task has finished, the remaining
                        # process_url() work is post-build finalization
                        # (reading-view capture, note writeback, etc.).
                        # Do not keep using the last build progress
                        # signature to trigger a false "build stall".
                        last_progress_signature = None
                        stall_start = None
                        last_phase = "post_build"
                        if post_build_started_at is None:
                            post_build_started_at = time.monotonic()
                        if (
                            watched_status == "completed"
                            and watched_project_id
                            and time.monotonic() - post_build_started_at
                            > AUTO_PIPELINE_POST_BUILD_GRACE_SECONDS
                        ):
                            recovered = self._recover_completed_project_result(
                                watched_project_id
                            )
                            if recovered is not None:
                                logger.warning(
                                    "auto pipeline run %s: recovered completed "
                                    "project %s after post_build tail exceeded %.1fs",
                                    run_id,
                                    watched_project_id,
                                    AUTO_PIPELINE_POST_BUILD_GRACE_SECONDS,
                                )
                                return recovered

                if elapsed > AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS:
                    self._request_cancel(
                        watched_task_id, reason="total timeout"
                    )
                    raise AutoPipelineTimeoutError(
                        f"total timeout after {int(elapsed)}s "
                        f"(limit {AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS}s)",
                        phase=last_phase,
                        task_id=watched_task_id,
                        project_id=watched_project_id,
                    )

                if (
                    active_build_task
                    and stall_start is not None
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
                        project_id=watched_project_id,
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

    def _get_task_snapshot(self, task_id: str) -> Optional[dict[str, Any]]:
        """Return one graph task payload, or ``None`` if unavailable."""
        try:
            body = self._http_get(f"{self.backend_base_url}/api/graph/task/{task_id}")
        except Exception:  # noqa: BLE001
            return None
        return body.get("data") or None

    def _recover_completed_project_result(
        self, project_id: Optional[str]
    ) -> Optional[dict[str, Any]]:
        """Recover the minimal pipeline result from a completed project."""
        if not project_id:
            return None
        try:
            body = self._http_get(
                f"{self.backend_base_url}/api/graph/project/{project_id}"
            )
        except Exception:  # noqa: BLE001
            return None

        project = body.get("data") or {}
        if str(project.get("status") or "") != "graph_completed":
            return None

        graph_id = str(project.get("graph_id") or "").strip()
        if not graph_id:
            return None

        content_hash = None
        md_path = ""
        for file_item in project.get("files") or []:
            candidate = str(file_item.get("source_md_path") or "").strip()
            if not candidate:
                continue
            md_path = candidate
            try:
                with open(candidate, encoding="utf-8") as handle:
                    content_hash = compute_content_hash(handle.read())
            except Exception:  # noqa: BLE001
                content_hash = None
            break

        project_name = str(project.get("name") or "").strip() or "Auto pipeline project"
        return {
            "project_id": project_id,
            "graph_id": graph_id,
            "project_name": project_name,
            "title": project_name,
            "md_path": md_path,
            "content_hash": content_hash,
        }

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
        # Resolve the project's effective domain. Priority:
        # 1. ontology_metadata.resolved_domain (what the classifier decided)
        # 2. project.domain (what the user selected)
        # 3. 'tech' fallback (legacy projects / auto-without-text)
        effective_domain = self._resolve_project_domain(project_id)
        return self.theme_proposer.process(
            project_id=project_id,
            project_name=project_name,
            article_title=article_title,
            new_canonical_ids=new_canonical_ids,
            run_id=run_id,
            project_domain=effective_domain,
        )

    def _resolve_project_domain(self, project_id: str) -> str:
        """Fetch the project and return its effective domain for theme scoping.

        Priority order:
          1. ontology_metadata.resolved_domain (set by domain classifier)
          2. project.domain (user-selected value, e.g. 'tech'/'methodology')
          3. 'tech' fallback (legacy projects, or 'auto' that was never resolved)
        """
        try:
            body = self._http_get(
                f"{self.backend_base_url}/api/graph/project/{project_id}"
            )
            project = body.get("data") or {}
            metadata = project.get("ontology_metadata") or {}
            resolved = metadata.get("resolved_domain")
            if resolved and resolved != "auto":
                return resolved
            domain = project.get("domain") or "tech"
            if domain == "auto":
                # 'auto' should have been resolved before this point; if it
                # sneaks through (e.g., classifier never ran), fall back to tech.
                return "tech"
            return domain
        except Exception:  # noqa: BLE001
            logger.warning(
                "auto pipeline: could not resolve domain for project %s, "
                "defaulting to 'tech'",
                project_id,
            )
            return "tech"

    def _schedule_discover_job(
        self,
        *,
        theme_id: Optional[str],
        trigger_project_id: str,
        new_entry_ids: list[str],
        run_id: str,
    ) -> dict[str, Any]:
        """Record a pending cross-concept discover job and return a stats dict.

        Replaces the previous inline ``_auto_discover_relations`` +
        ``_run_discover_with_timeout`` pair. The main pipeline no longer
        blocks on LLM judgment — a background worker (or the
        ``scripts/run_discover_jobs.py`` drainer in the P1 first cut) picks
        the job up later.

        Returns the stats payload that gets nested under ``summary.discover``.
        When prerequisites are missing (no theme assigned, no new canonical
        entries), no job is created and ``scheduled`` is False so the audit
        trail still explains what happened.
        """
        stats: dict[str, Any] = {
            "scheduled": False,
            "theme_id": theme_id,
            "new_entry_count": len(new_entry_ids),
        }
        if not theme_id:
            stats["skipped_reason"] = "no theme assigned (theme_proposer returned noop)"
            return stats
        if not new_entry_ids:
            stats["skipped_reason"] = "no new canonical entries this run"
            return stats

        # P4 step 11: global daily budget soft-gate. Bounds total discover
        # jobs per calendar day across all themes so a runaway-article
        # ingest can't drain LLM credit overnight. Default cap = 50/day;
        # override via DISCOVER_DAILY_JOB_BUDGET=N, or set to 0 to disable.
        try:
            _daily_budget = int(os.environ.get("DISCOVER_DAILY_JOB_BUDGET", "50"))
        except ValueError:
            _daily_budget = 50
        if _daily_budget > 0:
            try:
                today_count = self.discover_job_store.count_started_today()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "auto pipeline run %s: daily budget counter failed, allowing: %s",
                    run_id,
                    exc,
                )
                today_count = 0
            if today_count >= _daily_budget:
                stats["skipped_reason"] = (
                    f"daily budget exceeded: {today_count} discover jobs "
                    f"created today (cap={_daily_budget})"
                )
                stats["daily_count"] = today_count
                stats["daily_budget"] = _daily_budget
                # Surface this throttle event to the UI via the rolling
                # skip log. Soft-fail: log infra glitches must not turn
                # a cheap skip into a pipeline error.
                try:
                    self.discover_skip_log.append(
                        reason=stats["skipped_reason"],
                        kind="daily_budget",
                        theme_id=theme_id,
                        trigger_project_id=trigger_project_id,
                        origin_run_id=run_id,
                    )
                except Exception as log_exc:  # noqa: BLE001
                    logger.warning(
                        "auto pipeline run %s: skip_log append failed "
                        "(non-fatal): %s",
                        run_id,
                        log_exc,
                    )
                return stats

        # P4 step 10: per-theme per-hour cooldown. Bounds pathological
        # cases where a single theme spawns discover jobs faster than
        # the worker can drain them (e.g. a script re-ingesting the
        # same article on a loop). Default cap = 10/hour; override via
        # DISCOVER_THEME_HOURLY_CAP=N.
        try:
            _theme_cap = int(os.environ.get("DISCOVER_THEME_HOURLY_CAP", "10"))
        except ValueError:
            _theme_cap = 10
        if _theme_cap > 0:
            try:
                recent = self.discover_job_store.count_recent_for_theme(
                    theme_id, window_seconds=3600
                )
            except Exception as exc:  # noqa: BLE001
                # Don't let a counter glitch block scheduling — soft-fail
                # the rate check rather than the whole schedule.
                logger.warning(
                    "auto pipeline run %s: theme cooldown counter failed, allowing: %s",
                    run_id,
                    exc,
                )
                recent = 0
            if recent >= _theme_cap:
                stats["skipped_reason"] = (
                    f"theme cooldown: {recent} discover jobs created for this theme "
                    f"in the last hour (cap={_theme_cap})"
                )
                stats["theme_hourly_count"] = recent
                stats["theme_hourly_cap"] = _theme_cap
                try:
                    self.discover_skip_log.append(
                        reason=stats["skipped_reason"],
                        kind="theme_cooldown",
                        theme_id=theme_id,
                        trigger_project_id=trigger_project_id,
                        origin_run_id=run_id,
                    )
                except Exception as log_exc:  # noqa: BLE001
                    logger.warning(
                        "auto pipeline run %s: skip_log append failed "
                        "(non-fatal): %s",
                        run_id,
                        log_exc,
                    )
                return stats

        try:
            job = self.discover_job_store.create_job(
                theme_id=theme_id,
                trigger_project_id=trigger_project_id,
                new_entry_ids=list(new_entry_ids),
                origin_run_id=run_id,
            )
        except Exception as exc:  # noqa: BLE001
            # Discover scheduling is a soft-fail enrich: if the job store
            # itself is broken, we surface the error in the summary but the
            # article still marks processed. Matches the previous inline
            # policy (discover is enrich, not gate).
            logger.warning(
                "auto pipeline run %s: failed to schedule discover job: %s",
                run_id,
                exc,
            )
            stats["error"] = str(exc)
            return stats

        stats.update(
            {
                "scheduled": True,
                "job_id": job["job_id"],
                "status": job["status"],
            }
        )
        return stats

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
        with AutoPipelineRunner._open_url(req, timeout=30) as resp:
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
        with AutoPipelineRunner._open_url(req, timeout=60) as resp:
            data = resp.read()
        return _json.loads(data.decode("utf-8"))

    @staticmethod
    def _open_url(
        req: urllib.request.Request, *, timeout: int | float
    ):
        if _is_loopback_http_url(req.full_url):
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            return opener.open(req, timeout=timeout)
        return urllib.request.urlopen(req, timeout=timeout)

    @staticmethod
    def _mark_theme_governance_scan_requested(*, reason: str = "post_drain") -> None:
        """Write a pending governance request flag. Soft-fail — never break drain."""
        try:
            from .governance_request_store import mark_pending

            mark_pending(reason=reason)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "failed to mark governance scan requested: %s (non-fatal)", exc
            )

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
        discover_stats: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
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
        # discover is the soft-failing enrich phase. Always emit the block (even
        # when not attempted) so callers/audit don't have to special-case its
        # absence — explicit "attempted=False, skipped_reason=..." is clearer
        # than missing data.
        if discover_stats is not None:
            summary["discover"] = discover_stats
        return summary

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
