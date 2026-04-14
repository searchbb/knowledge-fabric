"""
图谱质量检查与定向补抽服务

在 Graphiti 一阶段抽取后：
1. assess(): 检查核心类型覆盖率 + 文本信号对齐
2. supplement(): 对缺失类型做定向 LLM 补抽，写入 Neo4j
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.llm_client import LLMClient

logger = logging.getLogger("mirofish.quality_gate")


def _name_similarity(a: str, b: str) -> float:
    """计算两个实体名的相似度（基于字符重叠）。"""
    if not a or not b:
        return 0.0
    # Containment check: if one is substring of the other
    if a in b or b in a:
        return max(len(a), len(b)) / (max(len(a), len(b)) + 2)
    # Character-level Jaccard
    set_a = set(a)
    set_b = set(b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


# 文本信号检测正则
_EVIDENCE_SIGNALS = re.compile(
    r"\d+[\.\d]*\s*[%％]|"        # 百分比
    r"\d{2,}[,，]\d{3}|"          # 大数字 (e.g. 3,161,237)
    r"\d+\.\d+\s*(倍|x|X)|"      # 倍数
    r"提升.*?\d|改进.*?\d|"       # 提升/改进+数字
    r"实验结果|实验表明|测试结果", # 实验相关
    re.UNICODE,
)

_PROBLEM_SIGNALS = re.compile(
    r"问题|挑战|困境|局限|瓶颈|缺陷|不足|"
    r"痛点|难题|障碍|冗余|缺失|失败|缺乏|"
    r"however|but|challenge|limitation|gap|issue",
    re.IGNORECASE | re.UNICODE,
)

_INSIGHT_SIGNALS = re.compile(
    r"结论|贡献|启示|展望|洞察|发现|总结|"
    r"我们发现|核心发现|关键发现|最终|"
    r"insight|conclusion|contribution|finding|takeaway",
    re.IGNORECASE | re.UNICODE,
)

# 补抽 prompt 模板
_SUPPLEMENT_SYSTEM_PROMPT = """你是一个知识图谱实体抽取专家。当前图谱缺少以下类型的实体，请从文本中补充抽取。

**重要：输出严格 JSON，不要输出任何其他内容。**

输出格式：
{
  "nodes": [
    {
      "name": "实体名称（具体、有意义，不要泛化）",
      "type": "实体类型（必须是指定的缺失类型之一）",
      "summary": "一句话描述（不超过80字）"
    }
  ],
  "edges": [
    {
      "source": "源实体名称",
      "target": "目标实体名称",
      "relation": "关系类型",
      "fact": "关系描述"
    }
  ]
}

约束：
- 只抽取指定的缺失类型，不要抽取已有类型的实体
- 实体名称必须具体（如"三元组级别语义冗余问题"而非"问题"）
- Evidence 必须带具体数值（如"20.47%-73.71%改进幅度"）
- Insight 必须是作者的结论性判断（如"Token异常是最好的异常检测器"）
- 边的 source/target 可以引用已有节点的名称
- 不要编造原文没有的内容
"""


@dataclass
class AssessmentResult:
    """质量评估结果"""
    missing_types: List[str] = field(default_factory=list)
    low_node_count: bool = False
    text_signals: Dict[str, int] = field(default_factory=dict)
    should_supplement: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class SupplementResult:
    """补抽结果"""
    new_nodes: List[Dict[str, Any]] = field(default_factory=list)
    new_edges: List[Dict[str, Any]] = field(default_factory=list)
    supplemented_types: List[str] = field(default_factory=list)


class GraphQualityGate:
    """图谱质量检查与定向补抽"""

    # 检查的核心类型
    CORE_CHECK_TYPES = {"Problem", "Evidence", "Insight"}

    # 节点数下限
    MIN_NODE_COUNT = 12
    SUMMARY_BATCH_SIZE = 4
    SUMMARY_CONTEXT_CHARS = 6000
    SUMMARY_SNIPPET_WINDOW = 320

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.last_summary_backfill_meta = {
            "requested": 0,
            "completed": 0,
            "missing": [],
        }

    def assess(
        self,
        graph_data: Dict[str, Any],
        ontology: Dict[str, Any],
        document_text: str,
    ) -> AssessmentResult:
        """评估图谱质量，检查核心类型覆盖和文本信号对齐。"""
        result = AssessmentResult()

        # 1. 统计已有类型
        nodes = graph_data.get("nodes", [])
        existing_types = set()
        for node in nodes:
            labels = [l for l in (node.get("labels") or []) if l != "Entity"]
            if labels:
                existing_types.add(labels[0])

        # 2. 检查核心类型覆盖
        ontology_types = {et["name"] for et in ontology.get("entity_types", [])}
        check_types = self.CORE_CHECK_TYPES & ontology_types  # 只检查 ontology 中有的
        missing = check_types - existing_types
        if missing:
            result.missing_types = sorted(missing)
            result.reasons.append(f"核心类型缺失: {', '.join(result.missing_types)}")

        # 3. 节点数检查
        node_count = len(nodes)
        if node_count < self.MIN_NODE_COUNT:
            result.low_node_count = True
            result.reasons.append(f"节点数偏低: {node_count} < {self.MIN_NODE_COUNT}")

        # 4. 文本信号扫描
        text_sample = document_text[:8000] if document_text else ""

        evidence_matches = len(_EVIDENCE_SIGNALS.findall(text_sample))
        problem_matches = len(_PROBLEM_SIGNALS.findall(text_sample))
        insight_matches = len(_INSIGHT_SIGNALS.findall(text_sample))

        result.text_signals = {
            "evidence": evidence_matches,
            "problem": problem_matches,
            "insight": insight_matches,
        }

        # 5. 信号-覆盖对齐检查
        if "Evidence" not in existing_types and evidence_matches >= 3:
            if "Evidence" not in result.missing_types:
                result.missing_types.append("Evidence")
            result.reasons.append(f"文本有 {evidence_matches} 个数据信号但无 Evidence 节点")

        if "Problem" not in existing_types and problem_matches >= 2:
            if "Problem" not in result.missing_types:
                result.missing_types.append("Problem")
            result.reasons.append(f"文本有 {problem_matches} 个问题信号但无 Problem 节点")

        if "Insight" not in existing_types and insight_matches >= 2:
            if "Insight" not in result.missing_types:
                result.missing_types.append("Insight")
            result.reasons.append(f"文本有 {insight_matches} 个结论信号但无 Insight 节点")

        # 6. 判断是否需要补抽
        result.should_supplement = bool(result.missing_types) or result.low_node_count

        if result.should_supplement:
            logger.info(
                "质量检查触发补抽: %s",
                "; ".join(result.reasons),
            )
        else:
            logger.info("质量检查通过: %d 节点, 类型 %s", node_count, sorted(existing_types))

        return result

    def supplement(
        self,
        *,
        missing_types: List[str],
        document_text: str,
        ontology: Dict[str, Any],
        existing_nodes: List[Dict[str, Any]],
    ) -> SupplementResult:
        """对缺失类型做定向 LLM 补抽。"""
        result = SupplementResult()

        if not missing_types:
            return result

        # 构建已有节点列表
        existing_names = []
        for node in existing_nodes:
            labels = [l for l in (node.get("labels") or []) if l != "Entity"]
            t = labels[0] if labels else "Unknown"
            existing_names.append(f"[{t}] {node.get('name', '')}")

        # 构建类型描述
        type_descriptions = {}
        for et in ontology.get("entity_types", []):
            if et["name"] in missing_types:
                type_descriptions[et["name"]] = et.get("description", "")

        # 文本截断（保留更多内容给补抽）
        text_for_extraction = document_text[:6000] if document_text else ""

        user_prompt = f"""## 缺失的实体类型

{chr(10).join(f'- **{t}**: {type_descriptions.get(t, "")}' for t in missing_types)}

## 已有节点（不要重复抽取）

{chr(10).join(existing_names[:30])}

## 文章正文

{text_for_extraction}

请从文章中补充抽取上述缺失类型的实体。每种缺失类型至少抽取 1-3 个实体。
边的 source/target 可以引用已有节点。
"""

        try:
            raw = self.llm_client.chat_json(
                [
                    {"role": "system", "content": _SUPPLEMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=3000,
            )
        except Exception as exc:
            logger.warning("补抽 LLM 调用失败: %s", exc)
            return result

        # 解析结果
        for node_data in raw.get("nodes", []):
            name = str(node_data.get("name", "")).strip()
            node_type = str(node_data.get("type", "")).strip()
            summary = str(node_data.get("summary", "")).strip()
            if not name or not node_type:
                continue
            if node_type not in missing_types:
                continue
            result.new_nodes.append({
                "name": name,
                "type": node_type,
                "summary": summary,
            })

        for edge_data in raw.get("edges", []):
            source = str(edge_data.get("source", "")).strip()
            target = str(edge_data.get("target", "")).strip()
            relation = str(edge_data.get("relation", "")).strip()
            fact = str(edge_data.get("fact", "")).strip()
            if not source or not target or not relation:
                continue
            result.new_edges.append({
                "source": source,
                "target": target,
                "relation": relation,
                "fact": fact,
            })

        result.supplemented_types = sorted(set(
            n["type"] for n in result.new_nodes
        ))

        logger.info(
            "补抽完成: %d 新节点 (%s), %d 新边",
            len(result.new_nodes),
            ", ".join(result.supplemented_types),
            len(result.new_edges),
        )
        return result

    # ------------------------------------------------------------------
    # 节点去重：合并名称高度相似的节点
    # ------------------------------------------------------------------

    @staticmethod
    def find_near_duplicates(
        graph_data: Dict[str, Any],
        threshold: float = 0.75,
    ) -> List[tuple]:
        """找出名称高度相似的节点对，返回 [(keep_uuid, merge_uuid, similarity), ...]"""
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        # 计算每个节点的度
        degree = {}
        for e in edges:
            su = e.get("source_node_uuid", "")
            tu = e.get("target_node_uuid", "")
            degree[su] = degree.get(su, 0) + 1
            degree[tu] = degree.get(tu, 0) + 1

        # 按类型分组
        by_type: Dict[str, List[Dict]] = {}
        for n in nodes:
            labels = [l for l in (n.get("labels") or []) if l != "Entity"]
            t = labels[0] if labels else "Unknown"
            by_type.setdefault(t, []).append(n)

        duplicates = []
        for t, group in by_type.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    n1, n2 = group[i], group[j]
                    name1 = (n1.get("name") or "").strip()
                    name2 = (n2.get("name") or "").strip()
                    if not name1 or not name2:
                        continue
                    sim = _name_similarity(name1, name2)
                    if sim >= threshold:
                        # Keep the one with more edges
                        d1 = degree.get(n1.get("uuid"), 0)
                        d2 = degree.get(n2.get("uuid"), 0)
                        if d1 >= d2:
                            duplicates.append((n1["uuid"], n2["uuid"], name1, name2, sim))
                        else:
                            duplicates.append((n2["uuid"], n1["uuid"], name2, name1, sim))
        return duplicates

    # ------------------------------------------------------------------
    # Summary 回填：为空 summary 的节点批量生成描述
    # ------------------------------------------------------------------

    _SUMMARY_SYSTEM_PROMPT = """你是一个知识图谱编辑，负责为实体节点补充简洁的一句话描述。

**输出严格 JSON，不要输出任何其他内容。**

输出格式：
{
  "summaries": [
    {"name": "实体名称", "summary": "一句话描述（不超过80字，围绕该实体本身，不要引入其他实体的信息）"}
  ]
}

约束：
- summary 必须围绕节点名称本身，简洁说明它是什么、做了什么、有什么特点
- 不要编造原文没有的内容
- 不要把多个实体的信息混入一个 summary
- Evidence 类型的 summary 应包含具体数值
- 如果无法从上下文推断，写"（待补充）"
"""

    def backfill_summaries(
        self,
        *,
        graph_data: Dict[str, Any],
        document_text: str,
    ) -> Dict[str, str]:
        """为空 summary 的节点批量生成描述。返回 {node_name: summary}。"""
        nodes = graph_data.get("nodes", [])
        empty_nodes = []
        for node in nodes:
            summary = (node.get("summary") or "").strip()
            if not summary:
                labels = [l for l in (node.get("labels") or []) if l != "Entity"]
                t = labels[0] if labels else "Unknown"
                empty_nodes.append({"name": node.get("name", ""), "type": t})

        if not empty_nodes:
            logger.info("所有节点都有 summary，无需回填")
            self.last_summary_backfill_meta = {
                "requested": 0,
                "completed": 0,
                "missing": [],
            }
            return {}

        logger.info("发现 %d 个空 summary 节点，开始回填", len(empty_nodes))
        result: Dict[str, str] = {}
        for batch in self._iter_summary_batches(empty_nodes):
            batch_result = self._request_summary_batch(
                nodes=batch,
                document_text=document_text,
            )
            result.update(batch_result)

        remaining_nodes = [node for node in empty_nodes if node["name"] not in result]
        if remaining_nodes:
            logger.warning("summary 首轮回填后仍缺失 %d 个节点，开始逐个补充", len(remaining_nodes))
            for node in remaining_nodes:
                node_result = self._request_summary_batch(
                    nodes=[node],
                    document_text=document_text,
                )
                result.update(node_result)

        missing_names = [node["name"] for node in empty_nodes if node["name"] not in result]
        self.last_summary_backfill_meta = {
            "requested": len(empty_nodes),
            "completed": len(result),
            "missing": missing_names,
        }

        if missing_names:
            logger.warning(
                "summary 回填未覆盖 %d/%d 个节点: %s",
                len(missing_names),
                len(empty_nodes),
                ", ".join(missing_names[:8]),
            )
        else:
            logger.info("summary 回填完成: %d/%d 个节点", len(result), len(empty_nodes))
        return result

    def _iter_summary_batches(self, nodes: List[Dict[str, str]]):
        batch_size = max(int(self.SUMMARY_BATCH_SIZE or 1), 1)
        for index in range(0, len(nodes), batch_size):
            yield nodes[index:index + batch_size]

    def _request_summary_batch(
        self,
        *,
        nodes: List[Dict[str, str]],
        document_text: str,
    ) -> Dict[str, str]:
        if not nodes:
            return {}

        node_list = "\n".join(f"- [{node['type']}] {node['name']}" for node in nodes)
        text_sample = self._build_summary_context(document_text, nodes)

        user_prompt = f"""## 需要补充 summary 的节点

{node_list}

## 文章正文（用于推断 summary）

{text_sample}

请为以上每个节点生成一句话 summary。
"""
        try:
            raw = self.llm_client.chat_json(
                [
                    {"role": "system", "content": self._SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
        except Exception as exc:
            logger.warning("summary 回填 LLM 调用失败: %s", exc)
            return {}

        result: Dict[str, str] = {}
        for item in raw.get("summaries", []):
            name = str(item.get("name", "")).strip()
            summary = str(item.get("summary", "")).strip()
            if name and summary and summary != "（待补充）":
                result[name] = summary

        logger.info("summary 回填批次完成: %d/%d 个节点", len(result), len(nodes))
        return result

    def _build_summary_context(
        self,
        document_text: str,
        nodes: List[Dict[str, str]],
    ) -> str:
        if not document_text:
            return ""

        snippets: List[str] = []
        seen_snippets = set()
        for node in nodes:
            snippet = self._extract_summary_snippet(document_text, node.get("name", ""))
            if snippet and snippet not in seen_snippets:
                snippets.append(snippet)
                seen_snippets.add(snippet)

        context = "\n\n".join(snippets).strip()
        if len(context) >= min(1200, self.SUMMARY_CONTEXT_CHARS):
            return context[: self.SUMMARY_CONTEXT_CHARS]

        fallback = document_text[: self.SUMMARY_CONTEXT_CHARS].strip()
        if context and fallback:
            return f"{context}\n\n---\n\n{fallback}"[: self.SUMMARY_CONTEXT_CHARS]
        return context or fallback

    def _extract_summary_snippet(self, document_text: str, node_name: str) -> str:
        if not document_text or not node_name:
            return ""

        candidates = [node_name]
        for token in re.split(r"[：:→\-（）()、，,·/\\\s]+", node_name):
            token = token.strip()
            if len(token) >= 2 and token not in candidates:
                candidates.append(token)

        for candidate in candidates:
            start_index = document_text.find(candidate)
            if start_index < 0:
                continue
            end_index = start_index + len(candidate)
            start = max(0, start_index - self.SUMMARY_SNIPPET_WINDOW)
            end = min(len(document_text), end_index + self.SUMMARY_SNIPPET_WINDOW)
            return document_text[start:end].strip()

        return ""
