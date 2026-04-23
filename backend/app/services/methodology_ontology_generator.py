"""方法论本体生成器 (v3 Stage 2).

针对方法论/认知提升/自助成长/管理经验总结类文章，提取"问题—原则—方法—步骤—
反模式—案例—信号"这类可迁移认知单元。与 tech ontology_generator 并列。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mirofish.methodology_ontology")


METHODOLOGY_ENTITY_TYPES = {
    "Topic", "Problem", "Principle", "Method",
    "Step", "Antipattern", "Case", "Signal",
}

METHODOLOGY_EDGE_TYPES = {
    "ADDRESSES", "GUIDED_BY", "COMPOSED_OF", "PRECEDES",
    "AVOIDS", "ILLUSTRATED_BY", "INDICATED_BY", "CONTRASTS_WITH",
}

# Unknown-type fallback (entity): key is lowercased alias, value is canonical
# from METHODOLOGY_ENTITY_TYPES. Unknowns not in this map are DROPPED.
# (Tech generator falls back unknowns to "Technology" — that defeats the
# purpose here, where the whole point is to avoid force-fitting.)
_ENTITY_FALLBACK = {
    "concept": "Principle",
    "观念": "Principle",
    "framework": "Method",
    "action": "Step",
    "动作": "Step",
    "stage": "Step",
    "阶段": "Step",
    "pitfall": "Antipattern",
    "误区": "Antipattern",
    "example": "Case",
    "indicator": "Signal",
    "指标": "Signal",
    "symptom": "Signal",
    "征兆": "Signal",
}


METHODOLOGY_SYSTEM_PROMPT = """你是知识图谱本体设计专家。请为"方法论 / 认知提升 / 自助成长 / 管理经验总结类文章"设计稳定、克制、可复用的认知图谱本体。

目标不是覆盖所有细节，而是提炼文章中最有长期价值的结构化知识。优先抽取"问题—原则—方法—步骤—反模式—案例—信号"这类可迁移认知单元，避免把普通事实名词泛化成实体。

实体类型只允许从以下集合中选择：

- Topic：文章主题、核心议题
- Problem：文章试图解释或解决的问题
- Principle：作者强调的原则、判断标准、底层规律
- Method：成体系的方法、框架、套路、做法
- Step：方法中的步骤、动作、阶段
- Antipattern：作者明确反对的错误做法、误区、陷阱
- Case：用于说明原则/方法/反模式的案例、故事、实例
- Signal：识别问题或判断是否适用某方法的征兆、信号、指标

关系类型只允许从以下集合中选择：

- ADDRESSES：Method/Principle 指向 Problem（解决什么问题）
- GUIDED_BY：Method/Step 指向 Principle（遵循什么原则）
- COMPOSED_OF：Method 指向 Step（由哪些步骤组成）
- PRECEDES：Step 指向 Step（先后顺序）
- AVOIDS：Method/Principle 指向 Antipattern（避免什么错误）
- ILLUSTRATED_BY：Principle/Method/Antipattern 指向 Case（由什么例子说明）
- INDICATED_BY：Problem/Principle 指向 Signal（由什么信号表明）
- CONTRASTS_WITH：两两对比

要求：

1. 类型数量要少而稳，优先高复用类型，不要临时发明新类型。
2. 只有当一个概念在文中具有明确认知作用时才建实体。
3. 普通修饰语、空泛抽象词、一次性例子不要强行建实体。
4. Step 只在文章明确给出流程、顺序、阶段时使用。
5. Principle 与 Method 要区分：Principle 是"为什么/判断依据"，Method 是"怎么做"。
6. Antipattern 只用于作者明确否定或批评的做法。
7. Signal 只用于"什么迹象说明你处于某问题/应采用某方法"的表述。
8. 输出需稳定，尽量让相似文章复用同一批类型与关系类型。

严格返回 JSON，不要输出 markdown。"""


class MethodologyOntologyGenerator:
    """Parallel to OntologyGenerator but for methodology/self-help articles.

    Interface matches OntologyGenerator.generate(...) so ontology_dispatcher
    can pick between them transparently.
    """

    def generate(
        self,
        *,
        document_texts: List[str],
        simulation_requirement: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from ..utils.llm_client import LLMClient
        llm = LLMClient()

        joined_text = "\n\n---\n\n".join(document_texts[:3])[:12000]
        user_prompt = (
            "请分析以下文章内容，为它设计方法论领域的认知图谱本体：\n\n"
            f"{joined_text}\n\n"
            "输出 JSON，结构：\n"
            '{"entity_types": [{"name": "...", "description": "...", '
            '"attributes": [{"name": "...", "type": "text", "description": "..."}], '
            '"examples": ["..."]}], '
            '"edge_types": [{"name": "...", "description": "...", '
            '"source_targets": [{"source": "...", "target": "..."}], "attributes": []}], '
            '"analysis_summary": "..."}'
        )

        messages = [
            {"role": "system", "content": METHODOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        result = llm.chat_json(messages=messages, temperature=0.2, max_tokens=4096)

        # Normalize entity types: fallback alias or drop.
        normalized_entities = []
        for e in result.get("entity_types", []):
            name = e.get("name", "")
            canonical = self._normalize_entity_type(name)
            if canonical is None:
                logger.warning("Dropping unknown methodology entity type: %s", name)
                continue
            e["name"] = canonical
            normalized_entities.append(e)

        # Normalize edge types: strict — drop unknowns.
        normalized_edges = []
        for edge in result.get("edge_types", []):
            name = edge.get("name", "")
            if name in METHODOLOGY_EDGE_TYPES:
                normalized_edges.append(edge)
            else:
                logger.warning("Dropping unknown methodology edge type: %s", name)

        return {
            "entity_types": normalized_entities,
            "edge_types": normalized_edges,
            "analysis_summary": result.get("analysis_summary", ""),
        }

    @staticmethod
    def _normalize_entity_type(name: str) -> Optional[str]:
        if name in METHODOLOGY_ENTITY_TYPES:
            return name
        key = name.strip().lower()
        return _ENTITY_FALLBACK.get(key)
