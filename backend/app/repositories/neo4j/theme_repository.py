"""
Neo4j mirror for the hub-and-spoke theme system.

JSON 是 source of truth (global_themes.json + concept_registry.json)。
这个 repository 只负责把 JSON 状态**镜像**到 Neo4j，供查询和可视化使用。
所有写操作都是 fire-and-forget: 调用方不应因为 Neo4j 同步失败而阻塞业务逻辑。

节点:
    (:Theme {theme_id, name, slug, description, status, source, created_at, updated_at})
    (:CanonicalConcept {entry_id, canonical_name, concept_type, created_at})

边:
    (c:CanonicalConcept)-[:IN_THEME {score, role, source, assigned_by, assigned_at}]->(t:Theme)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...config import Config

logger = logging.getLogger("mirofish.theme_repository")


def _get_driver():
    """延迟导入 + 构造 Neo4j driver (和 graph_builder 用同一个 pattern)。"""
    from graphiti_core.driver.neo4j_driver import Neo4jDriver

    return Neo4jDriver(
        uri=Config.NEO4J_URI,
        user=Config.NEO4J_USER,
        password=Config.NEO4J_PASSWORD,
    )


def _run_async(coro):
    """在同步上下文中跑 async coroutine。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class ThemeNeo4jRepository:
    """Neo4j 镜像层，所有方法都是同步的 (内部用 _run_async 桥接)。"""

    def __init__(self):
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            self._driver = _get_driver()
        return self._driver

    async def _exec(self, query: str, params: Optional[Dict] = None):
        driver = self._get_driver()
        # Graphiti's Neo4jDriver.execute_query signature varies by version.
        # Some versions accept (query, parameters=dict), some only (query).
        # Inline the parameters into the query as a workaround.
        if params:
            # Use neo4j's parameter syntax: $key is already in the query,
            # so pass via the database_ kwarg pattern or inline.
            # Try keyword first, fall back to inline.
            try:
                return await driver.execute_query(query, parameters=params)
            except TypeError:
                # Inline params into the query string for simple cases
                for key, val in params.items():
                    placeholder = f"${key}"
                    if isinstance(val, str):
                        query = query.replace(placeholder, f"'{val}'")
                    elif isinstance(val, (int, float)):
                        query = query.replace(placeholder, str(val))
                    elif val is None:
                        query = query.replace(placeholder, "null")
                return await driver.execute_query(query)
        return await driver.execute_query(query)

    def exec_sync(self, query: str, params: Optional[Dict] = None):
        return _run_async(self._exec(query, params))

    # ── Schema ──────────────────────────────────────────────────

    def ensure_constraints(self) -> None:
        """Create uniqueness constraints if they don't exist."""
        for q in [
            "CREATE CONSTRAINT theme_id_unique IF NOT EXISTS FOR (t:Theme) REQUIRE t.theme_id IS UNIQUE",
            "CREATE CONSTRAINT concept_entry_id_unique IF NOT EXISTS FOR (c:CanonicalConcept) REQUIRE c.entry_id IS UNIQUE",
            "CREATE INDEX theme_status_idx IF NOT EXISTS FOR (t:Theme) ON (t.status)",
        ]:
            try:
                self.exec_sync(q)
            except Exception as e:
                logger.debug("constraint/index create skipped: %s", e)

    # ── Theme CRUD ──────────────────────────────────────────────

    def sync_theme(self, theme: Dict[str, Any]) -> None:
        """Upsert a Theme node from JSON state."""
        self.exec_sync(
            """
            MERGE (t:Theme {theme_id: $theme_id})
            SET t.name        = $name,
                t.slug        = $slug,
                t.description = $description,
                t.status      = $status,
                t.source      = $source,
                t.updated_at  = $updated_at
            ON CREATE SET
                t.created_at  = $created_at
            """,
            {
                "theme_id": theme["theme_id"],
                "name": theme.get("name", ""),
                "slug": theme.get("slug", ""),
                "description": theme.get("description", ""),
                "status": theme.get("status", "active"),
                "source": theme.get("source", "user"),
                "created_at": theme.get("created_at", datetime.now().isoformat()),
                "updated_at": theme.get("updated_at", datetime.now().isoformat()),
            },
        )

    def delete_theme(self, theme_id: str) -> None:
        self.exec_sync(
            "MATCH (t:Theme {theme_id: $theme_id}) DETACH DELETE t",
            {"theme_id": theme_id},
        )

    # ── Concept CRUD ────────────────────────────────────────────

    def sync_concept(self, entry: Dict[str, Any]) -> None:
        """Upsert a CanonicalConcept node from JSON registry entry."""
        self.exec_sync(
            """
            MERGE (c:CanonicalConcept {entry_id: $entry_id})
            SET c.canonical_name = $canonical_name,
                c.concept_type   = $concept_type,
                c.updated_at     = $updated_at
            ON CREATE SET
                c.created_at     = $created_at
            """,
            {
                "entry_id": entry["entry_id"],
                "canonical_name": entry.get("canonical_name", ""),
                "concept_type": entry.get("concept_type", "Concept"),
                "created_at": entry.get("created_at", datetime.now().isoformat()),
                "updated_at": entry.get("updated_at", datetime.now().isoformat()),
            },
        )

    # ── Membership (IN_THEME edge) ──────────────────────────────

    def sync_membership(
        self,
        entry_id: str,
        theme_id: str,
        *,
        score: float = 1.0,
        role: str = "member",
        source: str = "manual",
        assigned_by: str = "system",
    ) -> None:
        self.exec_sync(
            """
            MATCH (c:CanonicalConcept {entry_id: $entry_id})
            MATCH (t:Theme {theme_id: $theme_id})
            MERGE (c)-[r:IN_THEME]->(t)
            SET r.score       = $score,
                r.role        = $role,
                r.source      = $source,
                r.assigned_by = $assigned_by,
                r.assigned_at = datetime()
            """,
            {
                "entry_id": entry_id,
                "theme_id": theme_id,
                "score": score,
                "role": role,
                "source": source,
                "assigned_by": assigned_by,
            },
        )

    def remove_membership(self, entry_id: str, theme_id: str) -> None:
        self.exec_sync(
            """
            MATCH (c:CanonicalConcept {entry_id: $entry_id})
                  -[r:IN_THEME]->
                  (t:Theme {theme_id: $theme_id})
            DELETE r
            """,
            {"entry_id": entry_id, "theme_id": theme_id},
        )

    # ── Query ───────────────────────────────────────────────────

    def get_theme_hub_data(self, theme_id: str) -> Dict[str, Any]:
        """Return theme + member concepts for hub view."""
        result = self.exec_sync(
            """
            MATCH (t:Theme {theme_id: $theme_id})
            OPTIONAL MATCH (c:CanonicalConcept)-[r:IN_THEME]->(t)
            RETURN t.theme_id AS theme_id, t.name AS theme_name,
                   t.description AS description, t.status AS status,
                   collect({
                       entry_id: c.entry_id,
                       canonical_name: c.canonical_name,
                       concept_type: c.concept_type,
                       score: r.score,
                       role: r.role,
                       source: r.source
                   }) AS concepts
            """,
            {"theme_id": theme_id},
        )
        records = result.records if hasattr(result, "records") else (result[0] if isinstance(result, tuple) else result)
        if not records:
            return {}
        rec = records[0]
        return {
            "theme_id": rec["theme_id"],
            "theme_name": rec["theme_name"],
            "description": rec["description"],
            "status": rec["status"],
            "concepts": [c for c in rec["concepts"] if c.get("entry_id")],
        }

    def get_orphans(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return canonical concepts not assigned to any theme."""
        result = self.exec_sync(
            """
            MATCH (c:CanonicalConcept)
            WHERE NOT (c)-[:IN_THEME]->(:Theme)
            RETURN c.entry_id AS entry_id,
                   c.canonical_name AS canonical_name,
                   c.concept_type AS concept_type
            ORDER BY c.canonical_name
            LIMIT $limit
            """,
            {"limit": limit},
        )
        records = result.records if hasattr(result, "records") else (result[0] if isinstance(result, tuple) else result)
        return [dict(r) for r in records] if records else []

    # ── Bulk operations ─────────────────────────────────────────

    def delete_all(self) -> int:
        """Delete all Theme and CanonicalConcept nodes + edges."""
        result = self.exec_sync(
            "MATCH (n) WHERE n:Theme OR n:CanonicalConcept DETACH DELETE n RETURN count(n) AS cnt"
        )
        records = result.records if hasattr(result, "records") else (result[0] if isinstance(result, tuple) else result)
        return records[0]["cnt"] if records else 0

    def full_sync_from_json(
        self,
        themes: Dict[str, Dict],
        concepts: Dict[str, Dict],
    ) -> Dict[str, int]:
        """Full mirror sync: push all JSON state to Neo4j."""
        self.ensure_constraints()

        synced_themes = 0
        for t in themes.values():
            try:
                self.sync_theme(t)
                synced_themes += 1
            except Exception as e:
                logger.warning("sync_theme %s failed: %s", t.get("theme_id"), e)

        synced_concepts = 0
        for c in concepts.values():
            try:
                self.sync_concept(c)
                synced_concepts += 1
            except Exception as e:
                logger.warning("sync_concept %s failed: %s", c.get("entry_id"), e)

        synced_edges = 0
        for t in themes.values():
            for m in t.get("concept_memberships", []):
                try:
                    self.sync_membership(
                        entry_id=m["entry_id"],
                        theme_id=t["theme_id"],
                        score=m.get("score", 1.0),
                        role=m.get("role", "member"),
                        source=m.get("source", "sync"),
                    )
                    synced_edges += 1
                except Exception as e:
                    logger.warning("sync_membership %s→%s failed: %s", m.get("entry_id"), t.get("theme_id"), e)

        return {"themes": synced_themes, "concepts": synced_concepts, "edges": synced_edges}
