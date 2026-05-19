"""TopicCluster sidecar store.

TopicCluster is a KFC-owned strategic aggregation node. This store only reads
and writes JSON sidecars and never runs model, scheduler, or research-project
workflows.
"""

from __future__ import annotations

import ast
import json
import os
import re
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


_DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")

TARGET_TYPES = {"wiki_topic", "kfc_theme", "research_project"}
CLUSTER_STATUS_VALUES = {"candidate", "active", "needs_review", "retired"}
STRATEGIC_RELEVANCE_VALUES = {"low", "medium", "high", "unknown"}
LINK_STATUS_VALUES = {"candidate", "accepted", "rejected", "needs_review"}
LINK_ROLE_VALUES = {"primary", "supporting", "candidate"}
CLUSTER_CREATE_FIELDS = {
    "cluster_id",
    "title",
    "description",
    "status",
    "strategic_relevance",
    "owner",
    "created_source",
}
CLUSTER_PATCH_FIELDS = {
    "title",
    "description",
    "status",
    "strategic_relevance",
    "owner",
}
LINK_CREATE_FIELDS = {
    "link_id",
    "target_type",
    "target_id",
    "target_title",
    "role",
    "status",
    "source",
    "confidence",
    "rationale",
    "review_decision",
}
LINK_PATCH_FIELDS = {
    "target_title",
    "role",
    "status",
    "confidence",
    "rationale",
    "review_decision",
}


class TopicClusterStoreError(ValueError):
    """Raised for invalid read-only lookup parameters."""

    def __init__(self, message: str, *, code: str = "validation_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _is_safe_identifier(value: str) -> bool:
    return bool(_SAFE_ID_PATTERN.match(value or ""))


def _blank_counts() -> dict[str, int]:
    return {
        "wiki_topics": 0,
        "kfc_themes": 0,
        "research_projects": 0,
        "candidate_links": 0,
        "needs_review_links": 0,
    }


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _concept_detail(value: Any) -> dict[str, str] | None:
    raw = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith("{") and "concept" in text:
            try:
                raw = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                raw = value
        else:
            return {"title": text, "summary": ""}
    if isinstance(raw, dict):
        title = str(raw.get("concept") or raw.get("name") or raw.get("title") or "").strip()
        summary = str(raw.get("summary") or raw.get("description") or raw.get("body") or "").strip()
        if title:
            return {"title": title, "summary": summary}
    text = str(value or "").strip()
    return {"title": text, "summary": ""} if text else None


def _compact_concept_details(values: Any, *, limit: int = 8) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    details: list[dict[str, str]] = []
    for value in values:
        detail = _concept_detail(value)
        if not detail or detail["title"] in seen:
            continue
        seen.add(detail["title"])
        details.append(detail)
        if len(details) >= limit:
            break
    return details


def _new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d')}_{secrets.token_hex(4)}"


class TopicClusterStore:
    """Filesystem reader for TopicCluster and TopicClusterLink JSON files."""

    CLUSTER_DIR: Path = _DEFAULT_DATA_ROOT / "topic_clusters"
    LINK_DIR: Path = _DEFAULT_DATA_ROOT / "topic_cluster_links"

    def __init__(
        self,
        cluster_dir: str | Path | None = None,
        link_dir: str | Path | None = None,
    ) -> None:
        self.cluster_dir = Path(cluster_dir or self.CLUSTER_DIR).expanduser().resolve()
        self.link_dir = Path(link_dir or self.LINK_DIR).expanduser().resolve()

    def create_cluster(self, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self._validate_cluster_payload(payload, creating=True)
        cluster_id = clean.get("cluster_id") or _new_id("tc")
        self._validate_identifier(cluster_id, "cluster_id")
        path = self._cluster_path(cluster_id)
        if path.exists():
            raise TopicClusterStoreError(
                f"topic cluster already exists: {cluster_id}",
                code="duplicate_cluster",
                status_code=409,
            )

        now = _now_iso()
        cluster = {
            "cluster_id": cluster_id,
            "title": clean["title"],
            "description": clean.get("description", ""),
            "status": clean.get("status", "candidate"),
            "strategic_relevance": clean.get("strategic_relevance", "unknown"),
            "owner": clean.get("owner"),
            "created_source": clean.get("created_source", "human"),
            "created_at": now,
            "updated_at": now,
        }
        self._atomic_write(path, cluster)
        return {"cluster": {**cluster, "counts": _blank_counts()}, "warnings": []}

    def update_cluster(self, cluster_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        self._validate_identifier(cluster_id, "cluster_id")
        clean = self._validate_cluster_payload(payload, creating=False)
        path = self._cluster_path(cluster_id)
        if not path.exists():
            return None
        cluster = self._read_object_file(path, "cluster")
        if cluster.get("cluster_id") != cluster_id:
            raise TopicClusterStoreError("cluster_id mismatch in sidecar", code="invalid_cluster")
        cluster.update(clean)
        cluster["updated_at"] = _now_iso()
        self._atomic_write(path, cluster)
        links, link_warnings = self._load_links()
        return {
            "cluster": {**cluster, "counts": self._counts_for_links([link for link in links if link.get("cluster_id") == cluster_id])},
            "warnings": link_warnings,
        }

    def create_cluster_link(self, cluster_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        self._validate_identifier(cluster_id, "cluster_id")
        if self.get_cluster(cluster_id) is None:
            return None
        clean = self._validate_link_payload(payload, creating=True)
        link_id = clean.get("link_id") or _new_id("tcl")
        self._validate_identifier(link_id, "link_id")
        path = self._link_path(link_id)
        if path.exists():
            raise TopicClusterStoreError(
                f"topic cluster link already exists: {link_id}",
                code="duplicate_link",
                status_code=409,
            )
        links, _ = self._load_links(include_deleted=True)
        duplicate = next(
            (
                link
                for link in links
                if not link.get("deleted")
                and link.get("cluster_id") == cluster_id
                and link.get("target_type") == clean["target_type"]
                and link.get("target_id") == clean["target_id"]
            ),
            None,
        )
        if duplicate:
            raise TopicClusterStoreError(
                "A link for this cluster and target already exists.",
                code="duplicate_link",
                status_code=409,
            )

        now = _now_iso()
        link = {
            "link_id": link_id,
            "cluster_id": cluster_id,
            "target_type": clean["target_type"],
            "target_id": clean["target_id"],
            "target_title": clean.get("target_title") or clean["target_id"],
            "role": clean.get("role", "candidate"),
            "status": clean.get("status", "candidate"),
            "source": clean.get("source", "human"),
            "confidence": clean.get("confidence"),
            "rationale": clean.get("rationale", ""),
            "review_decision": clean.get("review_decision"),
            "created_at": now,
            "updated_at": now,
        }
        self._atomic_write(path, link)
        return {"link": link, "warnings": self._target_warnings(link)}

    def update_cluster_link(self, link_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        self._validate_identifier(link_id, "link_id")
        clean = self._validate_link_payload(payload, creating=False)
        path = self._link_path(link_id)
        if not path.exists():
            return None
        link = self._read_object_file(path, "link")
        if link.get("link_id") != link_id:
            raise TopicClusterStoreError("link_id mismatch in sidecar", code="invalid_link")
        link.update(clean)
        link["updated_at"] = _now_iso()
        self._atomic_write(path, link)
        return {"link": link, "warnings": self._target_warnings(link)}

    def delete_cluster_link(self, link_id: str) -> dict[str, Any] | None:
        self._validate_identifier(link_id, "link_id")
        path = self._link_path(link_id)
        if not path.exists():
            return None
        link = self._read_object_file(path, "link")
        if link.get("link_id") != link_id:
            raise TopicClusterStoreError("link_id mismatch in sidecar", code="invalid_link")
        now = _now_iso()
        link["deleted"] = True
        link["deleted_at"] = now
        link["updated_at"] = now
        self._atomic_write(path, link)
        return {"link_id": link_id, "deleted": True}

    def list_clusters(self, *, include_counts: bool = False, include_articles: bool = False) -> dict[str, Any]:
        clusters, cluster_warnings = self._load_clusters()
        links, link_warnings = self._load_links()
        by_cluster = self._links_by_cluster(links)
        items = [
            self._cluster_with_counts(
                cluster,
                by_cluster.get(cluster["cluster_id"], []),
                include_counts=include_counts,
                include_articles=include_articles,
            )
            for cluster in clusters
        ]
        items.sort(key=lambda item: (item.get("status") != "active", item.get("title", "").lower()))
        return {"items": items, "total": len(items), "warnings": cluster_warnings + link_warnings}

    def get_cluster(self, cluster_id: str, *, include_counts: bool = False, include_articles: bool = False) -> dict[str, Any] | None:
        self._validate_identifier(cluster_id, "cluster_id")
        clusters, cluster_warnings = self._load_clusters()
        cluster = next((item for item in clusters if item.get("cluster_id") == cluster_id), None)
        if cluster is None:
            return None

        links, link_warnings = self._load_links()
        selected_links = [link for link in links if link.get("cluster_id") == cluster_id]
        links_by_type = self._group_links_by_type(selected_links)
        return {
            "cluster": self._cluster_with_counts(
                cluster,
                selected_links,
                include_counts=include_counts,
                include_articles=include_articles,
            ),
            "links_by_type": links_by_type,
            "warnings": cluster_warnings + link_warnings,
        }

    def get_cluster_links(self, cluster_id: str) -> dict[str, Any] | None:
        detail = self.get_cluster(cluster_id)
        if detail is None:
            return None
        links = []
        for group in detail["links_by_type"].values():
            links.extend(group)
        links.sort(key=self._link_sort_key)
        return {"items": links, "total": len(links), "warnings": detail.get("warnings", [])}

    def find_by_target(self, target_type: str, target_id: str) -> dict[str, Any]:
        if target_type not in TARGET_TYPES:
            raise TopicClusterStoreError(f"target_type must be one of {sorted(TARGET_TYPES)}")
        self._validate_identifier(target_id, "target_id")

        clusters, cluster_warnings = self._load_clusters()
        cluster_by_id = {cluster["cluster_id"]: cluster for cluster in clusters}
        links, link_warnings = self._load_links()
        matching_links = [
            link
            for link in links
            if link.get("target_type") == target_type and link.get("target_id") == target_id
        ]
        by_cluster = self._links_by_cluster(links)
        items = []
        for link in matching_links:
            cluster = cluster_by_id.get(link.get("cluster_id"))
            if not cluster:
                continue
            items.append(
                {
                    "cluster": {
                        **cluster,
                        "counts": self._counts_for_links(by_cluster.get(cluster["cluster_id"], [])),
                    },
                    "link": link,
                }
            )
        items.sort(key=lambda item: item["cluster"].get("title", "").lower())
        return {"items": items, "total": len(items), "warnings": cluster_warnings + link_warnings}

    def _validate_identifier(self, value: str, field_name: str) -> None:
        if not _is_safe_identifier(value):
            raise TopicClusterStoreError(f"invalid {field_name}")

    def _cluster_path(self, cluster_id: str) -> Path:
        self._validate_identifier(cluster_id, "cluster_id")
        return self.cluster_dir / f"{cluster_id}.json"

    def _link_path(self, link_id: str) -> Path:
        self._validate_identifier(link_id, "link_id")
        return self.link_dir / f"{link_id}.json"

    def _read_object_file(self, path: Path, kind: str) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            raise TopicClusterStoreError(
                f"malformed {kind} json: {path.name}",
                code=f"malformed_{kind}_json",
                status_code=500,
            ) from exc
        if not isinstance(payload, dict):
            raise TopicClusterStoreError(
                f"invalid {kind} json: payload must be an object",
                code=f"invalid_{kind}_json",
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

    def _validate_cluster_payload(self, payload: dict[str, Any], *, creating: bool) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TopicClusterStoreError("JSON body must be an object")
        allowed = CLUSTER_CREATE_FIELDS if creating else CLUSTER_PATCH_FIELDS
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise TopicClusterStoreError(f"unsupported fields: {', '.join(unknown)}")
        if creating and not str(payload.get("title") or "").strip():
            raise TopicClusterStoreError("title is required")
        clean: dict[str, Any] = {}
        if "cluster_id" in payload:
            cluster_id = str(payload.get("cluster_id") or "").strip()
            self._validate_identifier(cluster_id, "cluster_id")
            clean["cluster_id"] = cluster_id
        for field in ("title", "description", "owner", "created_source"):
            if field not in payload:
                continue
            value = payload.get(field)
            if value is not None and not isinstance(value, str):
                raise TopicClusterStoreError(f"{field} must be a string")
            value = value.strip() if field == "title" and value is not None else value
            if field == "title" and not value:
                raise TopicClusterStoreError("title is required")
            clean[field] = value
        if "status" in payload:
            status = payload["status"]
            if status not in CLUSTER_STATUS_VALUES:
                raise TopicClusterStoreError(f"status must be one of {sorted(CLUSTER_STATUS_VALUES)}")
            clean["status"] = status
        if "strategic_relevance" in payload:
            relevance = payload["strategic_relevance"]
            if relevance not in STRATEGIC_RELEVANCE_VALUES:
                raise TopicClusterStoreError(
                    f"strategic_relevance must be one of {sorted(STRATEGIC_RELEVANCE_VALUES)}"
                )
            clean["strategic_relevance"] = relevance
        return clean

    def _validate_link_payload(self, payload: dict[str, Any], *, creating: bool) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TopicClusterStoreError("JSON body must be an object")
        allowed = LINK_CREATE_FIELDS if creating else LINK_PATCH_FIELDS
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise TopicClusterStoreError(f"unsupported fields: {', '.join(unknown)}")
        if creating:
            for field in ("target_type", "target_id"):
                if not str(payload.get(field) or "").strip():
                    raise TopicClusterStoreError(f"{field} is required")
        clean: dict[str, Any] = {}
        if "link_id" in payload:
            link_id = str(payload.get("link_id") or "").strip()
            self._validate_identifier(link_id, "link_id")
            clean["link_id"] = link_id
        if "target_type" in payload:
            target_type = payload["target_type"]
            if target_type not in TARGET_TYPES:
                raise TopicClusterStoreError(f"target_type must be one of {sorted(TARGET_TYPES)}")
            clean["target_type"] = target_type
        if "target_id" in payload:
            target_id = str(payload.get("target_id") or "").strip()
            self._validate_identifier(target_id, "target_id")
            clean["target_id"] = target_id
        for field in ("target_title", "source", "rationale"):
            if field not in payload:
                continue
            value = payload.get(field)
            if value is not None and not isinstance(value, str):
                raise TopicClusterStoreError(f"{field} must be a string")
            clean[field] = value or ""
        if "role" in payload:
            role = payload["role"]
            if role not in LINK_ROLE_VALUES:
                raise TopicClusterStoreError(f"role must be one of {sorted(LINK_ROLE_VALUES)}")
            clean["role"] = role
        if "status" in payload:
            status = payload["status"]
            if status not in LINK_STATUS_VALUES:
                raise TopicClusterStoreError(f"status must be one of {sorted(LINK_STATUS_VALUES)}")
            clean["status"] = status
        if "confidence" in payload:
            confidence = payload["confidence"]
            if confidence is not None and not isinstance(confidence, (int, float)):
                raise TopicClusterStoreError("confidence must be a number")
            if isinstance(confidence, (int, float)) and not 0 <= confidence <= 1:
                raise TopicClusterStoreError("confidence must be between 0 and 1")
            clean["confidence"] = confidence
        if "review_decision" in payload:
            decision = payload["review_decision"]
            if decision is not None and not isinstance(decision, dict):
                raise TopicClusterStoreError("review_decision must be an object")
            clean["review_decision"] = decision
        return clean

    def _load_clusters(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        raw, warnings = self._load_json_dir(self.cluster_dir, "cluster")
        clusters = []
        for item in raw:
            cluster = dict(item)
            cluster_id = str(cluster.get("cluster_id") or "").strip()
            if not _is_safe_identifier(cluster_id):
                warnings.append({"type": "invalid_cluster", "file": cluster.get("_source_file", ""), "error": "invalid cluster_id"})
                continue
            cluster.setdefault("title", cluster_id)
            cluster.setdefault("description", "")
            cluster.setdefault("status", "candidate")
            cluster.setdefault("strategic_relevance", "unknown")
            cluster.setdefault("owner", None)
            cluster.setdefault("created_source", "unknown")
            cluster.setdefault("created_at", "")
            cluster.setdefault("updated_at", "")
            cluster.pop("_source_file", None)
            clusters.append(cluster)
        return clusters, warnings

    def _load_links(self, *, include_deleted: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        raw, warnings = self._load_json_dir(self.link_dir, "link")
        links = []
        for item in raw:
            link = dict(item)
            if not _is_safe_identifier(str(link.get("cluster_id") or "")):
                warnings.append({"type": "invalid_link", "file": link.get("_source_file", ""), "error": "invalid cluster_id"})
                continue
            if link.get("target_type") not in TARGET_TYPES:
                warnings.append({"type": "invalid_link", "file": link.get("_source_file", ""), "error": "invalid target_type"})
                continue
            if not _is_safe_identifier(str(link.get("target_id") or "")):
                warnings.append({"type": "invalid_link", "file": link.get("_source_file", ""), "error": "invalid target_id"})
                continue
            if link.get("status") not in LINK_STATUS_VALUES:
                link["status"] = "candidate"
            link.setdefault("link_id", "")
            link.setdefault("target_title", link["target_id"])
            link.setdefault("role", "candidate")
            link.setdefault("source", "imported")
            link.setdefault("confidence", None)
            link.setdefault("rationale", "")
            link.setdefault("review_decision", None)
            link.setdefault("created_at", "")
            link.setdefault("updated_at", "")
            link.pop("_source_file", None)
            if link.get("deleted") and not include_deleted:
                continue
            links.append(link)
        links.sort(key=self._link_sort_key)
        return links, warnings

    def _load_json_dir(self, directory: Path, kind: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        if not directory.exists():
            return [], []
        items: list[dict[str, Any]] = []
        warnings: list[dict[str, str]] = []
        for path in sorted(directory.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as fh:
                    payload = json.load(fh)
            except json.JSONDecodeError as exc:
                warnings.append({"type": f"malformed_{kind}_json", "file": path.name, "error": str(exc)})
                continue
            except OSError as exc:
                warnings.append({"type": f"unreadable_{kind}_json", "file": path.name, "error": str(exc)})
                continue
            if not isinstance(payload, dict):
                warnings.append({"type": f"invalid_{kind}_json", "file": path.name, "error": "payload must be an object"})
                continue
            payload["_source_file"] = path.name
            items.append(payload)
        return items, warnings

    def _links_by_cluster(self, links: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for link in links:
            grouped.setdefault(link["cluster_id"], []).append(link)
        return grouped

    def _group_links_by_type(self, links: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped = {target_type: [] for target_type in sorted(TARGET_TYPES)}
        for link in sorted(links, key=self._link_sort_key):
            grouped.setdefault(link["target_type"], []).append(link)
        return grouped

    def _counts_for_links(self, links: list[dict[str, Any]]) -> dict[str, int]:
        counts = _blank_counts()
        for link in links:
            if link.get("deleted") or link.get("status") == "rejected":
                continue
            target_type = link.get("target_type")
            if target_type == "wiki_topic":
                counts["wiki_topics"] += 1
            elif target_type == "kfc_theme":
                counts["kfc_themes"] += 1
            elif target_type == "research_project":
                counts["research_projects"] += 1

            if link.get("status") == "candidate":
                counts["candidate_links"] += 1
            elif link.get("status") == "needs_review":
                counts["needs_review_links"] += 1
        return counts

    def _cluster_with_counts(
        self,
        cluster: dict[str, Any],
        links: list[dict[str, Any]],
        *,
        include_counts: bool,
        include_articles: bool,
    ) -> dict[str, Any]:
        counts = self._counts_for_links(links)
        result = {**cluster, "counts": counts}
        if include_counts or include_articles:
            result.update(self._wiki_article_aggregation(links, include_articles=include_articles))
        return result

    def _wiki_article_aggregation(self, links: list[dict[str, Any]], *, include_articles: bool) -> dict[str, Any]:
        active_links = [
            link
            for link in links
            if not link.get("deleted") and link.get("status") != "rejected"
        ]
        wiki_links = [link for link in active_links if link.get("target_type") == "wiki_topic"]
        aggregation: dict[str, Any] = {
            "wiki_topic_count": len(wiki_links),
            "kfc_theme_count": len([link for link in active_links if link.get("target_type") == "kfc_theme"]),
            "research_project_count": len([link for link in active_links if link.get("target_type") == "research_project"]),
            "article_count": 0,
            "representative_articles": [],
        }
        if not wiki_links:
            if include_articles:
                aggregation["linked_topic_articles"] = []
            return aggregation

        try:
            from ..wiki_intake.store import WikiIntakeStore

            topic_store = WikiIntakeStore()
            topics = {topic["topic_id"]: topic for topic in topic_store.list_topics()}
            representative: list[dict[str, Any]] = []
            linked_topic_articles: list[dict[str, Any]] = []
            seen_articles: set[str] = set()
            for link in wiki_links:
                topic_id = str(link.get("target_id") or "")
                topic = topics.get(topic_id, {"topic_id": topic_id, "title": link.get("target_title") or topic_id, "article_count": 0})
                article_count = int(topic.get("article_count") or 0)
                aggregation["article_count"] += article_count
                for article in topic.get("representative_articles") or []:
                    key = str(article.get("candidate_id") or article.get("source_id") or article.get("title") or "")
                    if not key or key in seen_articles:
                        continue
                    seen_articles.add(key)
                    representative.append({**article, "topic_id": topic_id, "topic_title": topic.get("title") or topic_id})
                    if len(representative) >= 5:
                        break
                if include_articles:
                    detail = topic_store.get_topic_articles(topic_id)
                    articles = [
                        self._article_with_cluster_context(article, link, topic_id, topic.get("title") or topic_id)
                        for article in detail.get("articles") or []
                    ]
                    linked_topic_articles.append(
                        {
                            "topic_id": topic_id,
                            "title": (detail.get("topic") or {}).get("title") or topic.get("title") or topic_id,
                            "article_count": len(articles),
                            "articles": articles,
                        }
                    )
            aggregation["representative_articles"] = representative[:5]
            if include_articles:
                aggregation["linked_topic_articles"] = linked_topic_articles
        except Exception as exc:  # noqa: BLE001
            aggregation["enrichment_error"] = str(exc)
            if include_articles:
                aggregation["linked_topic_articles"] = []
        return aggregation

    def _article_with_cluster_context(
        self,
        article: dict[str, Any],
        link: dict[str, Any],
        topic_id: str,
        topic_title: str,
    ) -> dict[str, Any]:
        top_concept_details = _compact_concept_details(article.get("top_concepts") or [])
        top_concepts = [item["title"] for item in top_concept_details]
        reasons = [
            f"formal wiki_topic link: {topic_id}",
            "article topic_id matched linked wiki topic",
        ]
        if top_concepts:
            reasons.append(f"top concepts overlap: {', '.join(top_concepts[:5])}")
        candidate_id = str(article.get("candidate_id") or article.get("source_id") or "")
        routes = {
            "wiki_topic": f"/workspace/wiki-topics/{topic_id}",
            "wiki_intake": f"/workspace/wiki-intake?candidate={candidate_id}" if candidate_id else "/workspace/wiki-intake",
        }
        if article.get("source_url"):
            routes["source_url"] = str(article.get("source_url"))
        if article.get("verified_digest_md_path"):
            routes["verified_digest"] = f"file://{article.get('verified_digest_md_path')}"
        if article.get("markdown_path"):
            routes["source_file"] = f"file://{article.get('markdown_path')}"
        return {
            **article,
            "top_concepts": top_concepts,
            "top_concept_details": top_concept_details,
            "topic_title": topic_title,
            "belongs_to_cluster_reason": reasons,
            "cluster_link": {
                "link_id": link.get("link_id", ""),
                "target_type": "wiki_topic",
                "target_id": topic_id,
                "target_title": link.get("target_title") or topic_title,
                "status": link.get("status", ""),
                "role": link.get("role", ""),
            },
            "routes": routes,
        }

    def _link_sort_key(self, link: dict[str, Any]) -> tuple[int, str, str]:
        role_order = {"primary": 0, "supporting": 1, "candidate": 2}
        return (
            role_order.get(str(link.get("role") or ""), 9),
            str(link.get("target_type") or ""),
            str(link.get("target_title") or "").lower(),
        )

    def _target_warnings(self, link: dict[str, Any]) -> list[dict[str, str]]:
        # Phase 1 permits manual references to targets that may not exist yet.
        # The warning is intentionally non-blocking and has no side effects.
        return [
            {
                "code": "target_unresolved",
                "target_type": str(link.get("target_type") or ""),
                "target_id": str(link.get("target_id") or ""),
                "message": "Target existence is not required in Phase 1; link was saved as a manual reference.",
            }
        ]
