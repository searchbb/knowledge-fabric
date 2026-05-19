"""Deterministic KFC material graph sidecar store.

This store turns an already-materialized KFC Concept and its source material
slice into a lightweight graph snapshot. It deliberately does not call models,
Codex, schedulers, workers, shells, or create ProjectManager projects.
"""

from __future__ import annotations

import json
import re
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
_UPLOAD_PROJECTS_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "projects"
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")


class KfcMaterialGraphStoreError(ValueError):
    """Raised for invalid KFC material graph operations."""

    def __init__(self, message: str, *, code: str = "validation_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _trim(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").split())[:limit]


class KfcMaterialGraphStore:
    MATERIAL_GRAPH_DIR: Path = _DATA_ROOT / "kfc_material_graphs"
    GRAPHIFICATION_REQUEST_DIR: Path = _DATA_ROOT / "kfc_graphification_requests"
    MATERIAL_SLICE_DIR: Path = _DATA_ROOT / "material_slices"
    KFC_RELATION_DIR: Path = _DATA_ROOT / "kfc_asset_relations"
    CONCEPT_REGISTRY_PATH: Path = _UPLOAD_PROJECTS_ROOT / "concept_registry.json"

    def __init__(
        self,
        *,
        material_graph_dir: str | Path | None = None,
        graphification_request_dir: str | Path | None = None,
        material_slice_dir: str | Path | None = None,
        kfc_relation_dir: str | Path | None = None,
        concept_registry_path: str | Path | None = None,
    ) -> None:
        self.material_graph_dir = Path(material_graph_dir or self.MATERIAL_GRAPH_DIR).expanduser().resolve()
        self.graphification_request_dir = Path(
            graphification_request_dir or self.GRAPHIFICATION_REQUEST_DIR
        ).expanduser().resolve()
        self.material_slice_dir = Path(material_slice_dir or self.MATERIAL_SLICE_DIR).expanduser().resolve()
        self.kfc_relation_dir = Path(kfc_relation_dir or self.KFC_RELATION_DIR).expanduser().resolve()
        self.concept_registry_path = Path(concept_registry_path or self.CONCEPT_REGISTRY_PATH).expanduser().resolve()

    def ensure_snapshot_for_concept(self, concept_id: str, *, actor: str = "system", force: bool = False) -> dict[str, Any]:
        self._validate_identifier(concept_id, "concept_id")
        registry = self._load_registry()
        concept = registry.get("entries", {}).get(concept_id)
        if not concept:
            raise KfcMaterialGraphStoreError(
                f"concept not found: {concept_id}",
                code="concept_not_found",
                status_code=404,
            )

        graph_id = concept.get("material_graph_id") or self._graph_id_for_concept(concept_id)
        graph_path = self._graph_path(graph_id)
        existed = graph_path.exists()
        if existed and not force:
            graph = _read_json(graph_path)
            self._update_concept_graph_fields(registry, concept_id, graph, created=False)
            return {"graph": graph, "created": False, "reason": "already_exists"}

        material_slice = self._load_material_slice(concept)
        relations = self._relations_for_concept(concept_id, concept)
        graph = self._build_graph(graph_id, concept, material_slice, relations, actor=actor)
        self._atomic_write(graph_path, graph)
        self._update_concept_graph_fields(registry, concept_id, graph, created=not existed)
        return {"graph": graph, "created": not existed, "reason": "refreshed" if existed else "created"}

    def get_graph_for_concept(self, concept_id: str) -> dict[str, Any] | None:
        registry = self._load_registry()
        concept = registry.get("entries", {}).get(concept_id)
        if not concept:
            raise KfcMaterialGraphStoreError(
                f"concept not found: {concept_id}",
                code="concept_not_found",
                status_code=404,
            )
        graph_id = concept.get("material_graph_id") or self._graph_id_for_concept(concept_id)
        graph_path = self._graph_path(graph_id)
        if not graph_path.exists():
            return None
        return _read_json(graph_path)

    def get_graph(self, graph_id: str) -> dict[str, Any] | None:
        self._validate_identifier(graph_id, "graph_id")
        path = self._graph_path(graph_id)
        if not path.exists():
            return None
        return _read_json(path)

    def list_graphs(self, filters: dict[str, str] | None = None) -> dict[str, Any]:
        filters = filters or {}
        graphs = []
        if self.material_graph_dir.exists():
            for path in sorted(self.material_graph_dir.glob("kmg_*.json")):
                graph = _read_json(path)
                if self._matches_filters(graph, filters):
                    graphs.append(graph)
        graphs.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
        return {"items": graphs, "total": len(graphs)}

    def create_graphification_request(self, concept_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        snapshot = self.ensure_snapshot_for_concept(concept_id, actor=str(payload.get("actor") or "human"))
        graph = snapshot["graph"]
        request_id = f"kgreq_{datetime.now().strftime('%Y%m%d')}_{secrets.token_hex(4)}"
        request = {
            "request_id": request_id,
            "request_type": "kfc_material_graphification",
            "target_concept_id": concept_id,
            "target_material_graph_id": graph.get("graph_id", ""),
            "target_material_slice_id": graph.get("source_material_slice_id", ""),
            "target_article_id": graph.get("source_article_id", ""),
            "status": "requested",
            "rules": {
                "proposal_only": True,
                "do_not_auto_apply": True,
                "no_kfc_runtime_execution": True,
            },
            "expected_external_outputs": [
                "graph_pack",
                "relation_proposals",
                "evidence_links",
                "cross_article_links",
            ],
            "reason": _trim(payload.get("reason") or payload.get("note") or "Request external graphification proposal.", 500),
            "created_by": _trim(payload.get("actor") or "human", 80),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        self._atomic_write(self._request_path(request_id), request)
        self._attach_request_to_concept(concept_id, request_id)
        return request

    def graph_summary(self, graph: dict[str, Any] | None, concept_id: str = "") -> dict[str, Any]:
        if not graph:
            return {
                "concept_id": concept_id,
                "graph_status": "not_available",
                "material_graph_id": "",
                "node_count": 0,
                "edge_count": 0,
                "cross_article_link_count": 0,
            }
        return {
            "concept_id": graph.get("source_concept_id") or concept_id,
            "graph_status": graph.get("graph_state") or "snapshot_available",
            "material_graph_id": graph.get("graph_id", ""),
            "graph_depth": graph.get("graph_depth", ""),
            "node_count": len(graph.get("nodes") or []),
            "edge_count": len(graph.get("edges") or []),
            "cross_article_link_count": len(graph.get("cross_article_links") or []),
            "graphification_request_id": graph.get("graphification_request_id") or "",
        }

    def _build_graph(
        self,
        graph_id: str,
        concept: dict[str, Any],
        material_slice: dict[str, Any],
        relations: list[dict[str, Any]],
        *,
        actor: str,
    ) -> dict[str, Any]:
        concept_id = str(concept.get("entry_id") or concept.get("concept_id") or "")
        article_id = str(concept.get("source_article_id") or material_slice.get("source_article_id") or "")
        slice_id = str(concept.get("source_material_slice_id") or material_slice.get("slice_id") or "")
        cluster_ids = [item for item in concept.get("linked_topic_cluster_ids") or [] if item]
        project_ids = [item for item in concept.get("linked_research_project_ids") or [] if item]
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        cross_links: list[dict[str, Any]] = []

        def add_node(node_id: str, node_type: str, label: str, ref_id: str, **extra: Any) -> None:
            if not ref_id and node_type != "source_text":
                return
            nodes[node_id] = {
                "node_id": node_id,
                "node_type": node_type,
                "label": label or ref_id or node_type,
                "ref_id": ref_id,
                **extra,
            }

        def add_edge(source: str, target: str, edge_type: str, **extra: Any) -> None:
            if source not in nodes or target not in nodes:
                return
            edge_id = f"edge_{len(edges) + 1:03d}_{edge_type}"
            edges[edge_id] = {"edge_id": edge_id, "source": source, "target": target, "edge_type": edge_type, **extra}

        def add_relation_source_evidence(relation: dict[str, Any]) -> None:
            source_type = str(relation.get("source_type") or "")
            if source_type not in {"material_slice", "article"}:
                return
            relation_slice_id = str(relation.get("source_material_slice_id") or (
                relation.get("source_id") if source_type == "material_slice" else ""
            ) or "")
            relation_article_id = str(relation.get("source_article_id") or (
                relation.get("source_id") if source_type == "article" else ""
            ) or "")
            relation_quote = relation.get("source_quote") or relation.get("source_excerpt") or ""
            relation_context = relation.get("source_context") or relation_quote
            relation_slice_node = f"material_slice:{relation_slice_id}" if relation_slice_id else ""
            relation_article_node = f"article:{relation_article_id}" if relation_article_id else ""
            if relation_slice_node:
                add_node(
                    relation_slice_node,
                    "material_slice",
                    relation.get("source_title") or relation_slice_id,
                    relation_slice_id,
                    source_quote=relation_quote,
                    source_context=relation_context,
                )
                add_edge(relation_slice_node, concept_node, relation.get("relation_type") or "mention", relation_id=relation.get("relation_id", ""))
            if relation_article_node:
                add_node(
                    relation_article_node,
                    "source_article",
                    relation.get("source_article_title") or relation_article_id,
                    relation_article_id,
                    source_markdown_path=relation.get("source_markdown_path", ""),
                )
                if relation_slice_node:
                    add_edge(relation_article_node, relation_slice_node, "contains_slice", relation_id=relation.get("relation_id", ""))
                else:
                    add_edge(relation_article_node, concept_node, relation.get("relation_type") or "mention", relation_id=relation.get("relation_id", ""))

        concept_node = f"concept:{concept_id}"
        slice_node = f"material_slice:{slice_id}"
        article_node = f"article:{article_id}"
        add_node(concept_node, "concept_registry_entry", concept.get("canonical_name") or concept.get("label") or concept_id, concept_id)
        add_node(
            slice_node,
            "material_slice",
            material_slice.get("display_title") or material_slice.get("title") or "Source Material Slice",
            slice_id,
            source_quote=concept.get("source_quote") or material_slice.get("source_quote", ""),
            source_context=concept.get("source_context") or material_slice.get("source_context", ""),
        )
        add_node(
            article_node,
            "source_article",
            concept.get("source_article_title") or material_slice.get("source_title") or article_id,
            article_id,
            source_markdown_path=concept.get("source_markdown_path") or material_slice.get("source_markdown_path", ""),
        )
        add_edge(concept_node, slice_node, "derived_from")
        add_edge(slice_node, article_node, "sliced_from")

        for cluster_id in cluster_ids:
            node_id = f"topic_cluster:{cluster_id}"
            add_node(node_id, "topic_cluster", cluster_id, cluster_id)
            add_edge(concept_node, node_id, "belongs_to")
        for project_id in project_ids:
            node_id = f"research_project:{project_id}"
            add_node(node_id, "research_project", project_id, project_id)
            add_edge(concept_node, node_id, "supports")

        for relation in relations:
            if relation.get("target_id") == concept_id:
                add_relation_source_evidence(relation)
            if relation.get("target_type") == "concept_registry_entry" and relation.get("target_id") != concept_id:
                target_id = str(relation.get("target_id") or "")
                label = self._concept_label(target_id)
                target_node = f"concept:{target_id}"
                add_node(target_node, "concept_registry_entry", label or target_id, target_id)
                add_edge(concept_node, target_node, relation.get("relation_type") or "related_to", relation_id=relation.get("relation_id", ""))
                cross_links.append({
                    "link_type": "related_concept",
                    "target_concept_id": target_id,
                    "target_article_id": relation.get("source_article_id") or article_id,
                    "reason": "existing_kfc_asset_relation",
                    "relation_id": relation.get("relation_id", ""),
                    "label": label,
                })

        warnings = []
        if not article_id:
            warnings.append({"type": "missing_source_article_id", "message": "Concept has no source_article_id."})
        if not slice_id:
            warnings.append({"type": "missing_material_slice", "message": "Concept has no source_material_slice_id."})
        if not (concept.get("source_quote") or material_slice.get("source_quote")):
            warnings.append({"type": "missing_source_quote", "message": "Concept has no source quote."})

        now = _now_iso()
        return {
            "graph_id": graph_id,
            "asset_type": "kfc_material_graph",
            "source_concept_id": concept_id,
            "source_material_slice_id": slice_id,
            "source_lead_id": concept.get("source_lead_id", ""),
            "source_article_id": article_id,
            "source_markdown_path": concept.get("source_markdown_path") or material_slice.get("source_markdown_path", ""),
            "source_content_hash": concept.get("source_content_hash") or material_slice.get("source_content_hash", ""),
            "graph_state": "snapshot_available",
            "graph_depth": "deterministic_snapshot",
            "external_graph_pack_ids": [],
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
            "cross_article_links": cross_links,
            "provenance": {
                "source_quote": concept.get("source_quote") or material_slice.get("source_quote", ""),
                "source_context": concept.get("source_context") or material_slice.get("source_context", ""),
                "created_by": "kfc_material_graph_store",
                "creation_mode": "deterministic",
                "no_model_execution": True,
            },
            "warnings": warnings,
            "change_log": [{"event": "created", "actor": actor, "mode": "deterministic_snapshot", "timestamp": now}],
            "created_at": now,
            "updated_at": now,
        }

    def _relations_for_concept(self, concept_id: str, concept: dict[str, Any]) -> list[dict[str, Any]]:
        relations = []
        if self.kfc_relation_dir.exists():
            for path in sorted(self.kfc_relation_dir.glob("rel_*.json")):
                relation = _read_json(path)
                if relation.get("deleted"):
                    continue
                if relation.get("source_id") == concept_id or relation.get("target_id") == concept_id:
                    relations.append(relation)
        for related in concept.get("related_existing_concepts") or []:
            target_id = related.get("concept_id")
            if target_id and not any(item.get("source_id") == concept_id and item.get("target_id") == target_id for item in relations):
                relations.append({
                    "relation_id": f"inline_related_{target_id}",
                    "source_type": "concept_registry_entry",
                    "source_id": concept_id,
                    "target_type": "concept_registry_entry",
                    "target_id": target_id,
                    "relation_type": "related_to",
                    "source_article_id": concept.get("source_article_id", ""),
                })
        return relations

    def _load_material_slice(self, concept: dict[str, Any]) -> dict[str, Any]:
        slice_id = str(concept.get("source_material_slice_id") or "")
        if not slice_id:
            return {}
        path = self.material_slice_dir / f"{slice_id}.json"
        if not path.exists():
            return {}
        return _read_json(path)

    def _concept_label(self, concept_id: str) -> str:
        registry = self._load_registry()
        entry = registry.get("entries", {}).get(concept_id) or {}
        return str(entry.get("canonical_name") or entry.get("label") or concept_id)

    def _update_concept_graph_fields(self, registry: dict[str, Any], concept_id: str, graph: dict[str, Any], *, created: bool) -> None:
        entry = registry.setdefault("entries", {}).get(concept_id)
        if not entry:
            return
        entry["graph_status"] = graph.get("graph_state") or "snapshot_available"
        entry["material_graph_id"] = graph.get("graph_id", "")
        entry["graph_node_count"] = len(graph.get("nodes") or [])
        entry["graph_edge_count"] = len(graph.get("edges") or [])
        entry["cross_article_link_count"] = len(graph.get("cross_article_links") or [])
        if created:
            entry["updated_at"] = _now_iso()
        registry["entries"][concept_id] = entry
        self._save_registry(registry)

    def _attach_request_to_concept(self, concept_id: str, request_id: str) -> None:
        registry = self._load_registry()
        entry = registry.setdefault("entries", {}).get(concept_id)
        if not entry:
            return
        ids = list(entry.get("graphification_request_ids") or [])
        if request_id not in ids:
            ids.append(request_id)
        entry["graphification_request_ids"] = ids
        entry["graphification_request_id"] = request_id
        entry["updated_at"] = _now_iso()
        registry["entries"][concept_id] = entry
        self._save_registry(registry)
        graph_id = entry.get("material_graph_id")
        if graph_id:
            graph_path = self._graph_path(graph_id)
            if graph_path.exists():
                graph = _read_json(graph_path)
                graph["graphification_request_id"] = request_id
                graph["updated_at"] = _now_iso()
                self._atomic_write(graph_path, graph)

    def _load_registry(self) -> dict[str, Any]:
        path = self.concept_registry_path
        if not path.exists():
            return {"version": 1, "entries": {}}
        return _read_json(path)

    def _save_registry(self, registry: dict[str, Any]) -> None:
        self._atomic_write(self.concept_registry_path, registry)

    def _graph_id_for_concept(self, concept_id: str) -> str:
        return f"kmg_{concept_id.replace('canon_', '')}"

    def _graph_path(self, graph_id: str) -> Path:
        return self.material_graph_dir / f"{graph_id}.json"

    def _request_path(self, request_id: str) -> Path:
        return self.graphification_request_dir / f"{request_id}.json"

    def _matches_filters(self, graph: dict[str, Any], filters: dict[str, str]) -> bool:
        mapping = {
            "concept_id": graph.get("source_concept_id", ""),
            "article_id": graph.get("source_article_id", ""),
            "graph_state": graph.get("graph_state", ""),
        }
        for key in ("concept_id", "article_id", "graph_state"):
            if filters.get(key) and filters[key] != mapping.get(key):
                return False
        if filters.get("topic_cluster_id"):
            if not any(node.get("node_type") == "topic_cluster" and node.get("ref_id") == filters["topic_cluster_id"] for node in graph.get("nodes") or []):
                return False
        if filters.get("research_project_id"):
            if not any(node.get("node_type") == "research_project" and node.get("ref_id") == filters["research_project_id"] for node in graph.get("nodes") or []):
                return False
        return True

    def _validate_identifier(self, value: str, field: str) -> None:
        if not value or not _SAFE_ID_PATTERN.match(value):
            raise KfcMaterialGraphStoreError(f"invalid {field}: {value}")

    def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            tmp_name = handle.name
        Path(tmp_name).replace(path)
