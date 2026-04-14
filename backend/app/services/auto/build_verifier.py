"""Verify that an article project is healthy enough for auto decisions.

After ``ArticleWorkspacePipeline.process_url()`` returns we cannot blindly
trust that the project is ready. The runner could have failed mid-build,
returned a project with zero nodes, or left the concept view unable to load.
This module is the gate between "build complete" and "auto-decide on the
results".

The verifier is intentionally tolerant of ``completed_with_warnings`` —
that's the normal outcome when summary backfill misses a node. It is NOT
tolerant of ``failed`` or empty graphs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


_OK_BUILD_STATUSES = {"completed", "completed_with_warnings"}


@dataclass
class BuildVerificationResult:
    ok: bool
    reason: str
    node_count: int = 0
    edge_count: int = 0
    candidate_count: int = 0
    build_status: str = ""


class BuildVerifier:
    """Re-checks the project state after process_url returns.

    The verifier holds no state of its own; it just calls into the existing
    project / concept services and turns their answers into a structured
    pass/fail with a human-readable reason.
    """

    def verify(self, project_id: str) -> BuildVerificationResult:
        if not project_id:
            return BuildVerificationResult(ok=False, reason="empty project_id")

        # Imports are deferred so the auto package does not pull half the
        # backend at module load time. This matters for unit tests that
        # mock individual services.
        from ...models.project import ProjectManager
        from ..workspace.concept_view_service import (
            ConceptViewNotFoundError,
            ConceptViewService,
        )
        from ..graph_access_service import load_graph_data_by_backend

        project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
        if not project:
            return BuildVerificationResult(ok=False, reason="project not found")

        # 1. Check the persisted phase-1 result
        result_payload: dict = {}
        snapshot = getattr(project, "phase1_task_result", None)
        if isinstance(snapshot, dict):
            result_payload = snapshot.get("result") or {}

        artifacts = result_payload.get("artifacts") or {}
        graph_artifact = artifacts.get("graph") or {}
        build_status = graph_artifact.get("build_status") or ""

        if build_status and build_status not in _OK_BUILD_STATUSES:
            return BuildVerificationResult(
                ok=False,
                reason=f"build_status={build_status}",
                build_status=build_status,
            )

        # 2. Check the live graph data has nodes
        graph_id = getattr(project, "graph_id", None) or graph_artifact.get("graph_id")
        node_count = 0
        edge_count = 0
        if graph_id:
            try:
                graph = load_graph_data_by_backend(graph_id) or {}
                node_count = len(graph.get("nodes") or [])
                edge_count = len(graph.get("edges") or [])
            except Exception as error:  # noqa: BLE001 - we want the reason
                return BuildVerificationResult(
                    ok=False,
                    reason=f"graph_data unreadable: {error}",
                    build_status=build_status,
                )
        if node_count == 0:
            return BuildVerificationResult(
                ok=False,
                reason="graph has zero nodes",
                node_count=0,
                edge_count=edge_count,
                build_status=build_status,
            )

        # 3. Check the concept view returns at least 1 candidate
        try:
            view = ConceptViewService().build_project_view(project_id)
        except ConceptViewNotFoundError as error:
            return BuildVerificationResult(
                ok=False,
                reason=f"concept view not available: {error}",
                node_count=node_count,
                edge_count=edge_count,
                build_status=build_status,
            )
        candidates = view.get("candidateConcepts") or []
        if not candidates:
            return BuildVerificationResult(
                ok=False,
                reason="concept view has zero candidates",
                node_count=node_count,
                edge_count=edge_count,
                candidate_count=0,
                build_status=build_status,
            )

        return BuildVerificationResult(
            ok=True,
            reason="ok",
            node_count=node_count,
            edge_count=edge_count,
            candidate_count=len(candidates),
            build_status=build_status or "completed",
        )
