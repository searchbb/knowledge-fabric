"""
阅读骨架抽取服务

在不改变原始图谱的前提下，为阅读视图补一层文章主线摘要：
- 标题
- 核心问题
- 核心方案
- 核心架构/结构路径
- 各类分组标题
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from ..utils.llm_client import LLMClient

logger = logging.getLogger("mirofish.reading_structure")

DEFAULT_GROUP_TITLES = {
    "Layer": "架构层级",
    "Mechanism": "关键机制",
    "Decision": "关键决策",
    "Technology": "涉及技术",
    "Metric": "验证指标",
    "Evidence": "关键证据",
    "Insight": "核心洞察",
    "Example": "案例证据",
}

# Domain-aware reading-view configs (v3 methodology secondary-path fix).
# Per-domain backbone labels + group_titles. The tech variant preserves
# the original hardcoded values; methodology gets its own.

GROUP_TITLES_BY_DOMAIN: dict[str, dict[str, str]] = {
    "tech": {
        "Layer": "架构层级",
        "Mechanism": "关键机制",
        "Decision": "关键决策",
        "Technology": "涉及技术",
        "Metric": "验证指标",
        "Evidence": "关键证据",
        "Insight": "核心洞察",
        "Example": "案例证据",
    },
    "methodology": {
        "Step": "步骤流程",
        "Antipattern": "反模式",
        "Case": "案例与证据",
        "Signal": "识别信号",
    },
}

BACKBONE_LABELS_BY_DOMAIN: dict[str, list[str]] = {
    "tech": ["Topic", "Problem", "Solution", "Architecture"],
    "methodology": ["Topic", "Problem", "Principle", "Method"],
}


def _build_system_prompt(domain: str) -> str:
    if domain == "methodology":
        return """你是一个方法论文章编辑，专门把知识图谱整理成适合人类阅读的文章骨架。

你的任务不是重做实体关系抽取，而是：
1. 阅读文章内容摘要和图谱候选节点
2. 提炼出最适合阅读视图展示的主线标题
3. 用简洁中文给出核心问题、核心方法、核心原则/框架的摘要标题
4. 给阅读视图中的分组节点补充更自然的标题
5. 提取文章的原始章节结构

约束：
- 输出必须是严格 JSON
- 只能输出指定字段，不要增加额外字段
- 不要编造原文没有的事实
- 标题要像人类写的目录节点，不要像数据库实体名
- 每个 title 尽量 6-18 个中文字符
- summary 尽量 1 句话，不超过 70 个中文字符
- problem / solution / architecture 语义在方法论文中：
  - problem = 文章要回答的核心问题或研究问题
  - solution = 文章主张的核心方法 / 主要框架（Method 类节点）
  - architecture = 文章的方法论路径或论证结构（如"问题→原则→方法→案例"）
- problem / solution / architecture 下面只能保留 title 和 summary 两个字段
- group_titles 中只保留图谱中实际存在的类型对应的键（从以下选择：Step / Antipattern / Case / Signal）
- article_sections 必须从原文标题/段落结构中提取，不要自己编造章节

输出格式：
{
  "title": "整篇文章的阅读标题",
  "summary": "一句话概括文章主线",
  "problem": {"title": "核心问题标题", "summary": "一句话说明"},
  "solution": {"title": "核心方法标题", "summary": "一句话说明"},
  "architecture": {"title": "论证结构标题", "summary": "一句话说明"},
  "group_titles": {
    "Step": "步骤流程",
    "Antipattern": "反模式",
    "Case": "案例与证据",
    "Signal": "识别信号"
  },
  "article_sections": ["原文第一个章节标题", "原文第二个章节标题", "..."]
}
"""
    # default: tech — preserve original prompt verbatim
    return """你是一个技术文章编辑，专门把知识图谱整理成适合人类阅读的文章骨架。

你的任务不是重做实体关系抽取，而是：
1. 阅读文章内容摘要和图谱候选节点
2. 提炼出最适合阅读视图展示的主线标题
3. 用简洁中文给出核心问题、核心方案、核心结构路径的摘要标题
4. 给阅读视图中的分组节点补充更自然的标题
5. 提取文章的原始章节结构

约束：
- 输出必须是严格 JSON
- 只能输出指定字段，不要增加额外字段
- 不要编造原文没有的事实
- 标题要像人类写的目录节点，不要像数据库实体名
- 每个 title 尽量 6-18 个中文字符
- summary 尽量 1 句话，不超过 70 个中文字符
- problem / solution 的标题和摘要必须忠实反映原文表述，不要过度抽象或广告化
- architecture：如果文章没有明确提出系统架构设计，允许描述文章的方法论路径或展开逻辑，但必须在 summary 中说明这不是作者原文的架构
- problem / solution / architecture 下面只能保留 title 和 summary 两个字段
- group_titles 中只保留图谱中实际存在的类型对应的键（从以下选择：Layer / Mechanism / Decision / Technology / Metric / Evidence / Insight / Example）
- article_sections 必须从原文标题/段落结构中提取，不要自己编造章节

输出格式：
{
  "title": "整篇文章的阅读标题",
  "summary": "一句话概括文章主线",
  "problem": {"title": "核心问题标题", "summary": "一句话说明"},
  "solution": {"title": "核心方案标题", "summary": "一句话说明"},
  "architecture": {"title": "核心结构标题", "summary": "一句话说明"},
  "group_titles": {
    "Mechanism": "关键机制",
    "Technology": "涉及技术",
    "Evidence": "关键证据",
    "Insight": "核心洞察",
    "Example": "案例证据"
  },
  "article_sections": ["原文第一个章节标题", "原文第二个章节标题", "..."]
}
"""


class ReadingStructureExtractor:
    """为阅读视图抽取稳定的文章骨架。"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.last_result_meta: Dict[str, Any] = {
            "status": "idle",
            "reason": "",
        }

    def extract(
        self,
        *,
        project_name: str,
        document_text: str,
        analysis_summary: str,
        ontology: Optional[Dict[str, Any]],
        graph_data: Optional[Dict[str, Any]],
        simulation_requirement: str = "",
        domain: str = "tech",
    ) -> Dict[str, Any]:
        """抽取阅读骨架。LLM 失败时直接抛出异常。"""
        prompt = self._build_user_prompt(
            project_name=project_name,
            document_text=document_text,
            analysis_summary=analysis_summary,
            ontology=ontology or {},
            graph_data=graph_data or {},
            simulation_requirement=simulation_requirement,
            domain=domain,
        )

        raw = self.llm_client.chat_json(
            [
                {"role": "system", "content": _build_system_prompt(domain)},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2600,
        )
        result = self._normalize_result(
            raw,
            fallback_title=project_name,
            document_text=document_text,
            graph_data=graph_data or {},
            domain=domain,
        )
        self.last_result_meta = {
            "status": "generated",
            "reason": "",
        }
        return result

    def _build_user_prompt(
        self,
        *,
        project_name: str,
        document_text: str,
        analysis_summary: str,
        ontology: Dict[str, Any],
        graph_data: Dict[str, Any],
        simulation_requirement: str,
        domain: str = "tech",
    ) -> str:
        graph_digest = self._build_graph_digest(graph_data, domain=domain)
        entity_types = [item.get("name") for item in ontology.get("entity_types", []) if item.get("name")]
        edge_types = [item.get("name") for item in ontology.get("edge_types", []) if item.get("name")]
        truncated_text = (document_text or "").strip()
        if len(truncated_text) > 5000:
            truncated_text = f"{truncated_text[:5000]}\n\n[内容已截断]"

        return f"""请基于下面信息，为阅读视图整理文章骨架。

项目名：
{project_name}

抽取目标：
{simulation_requirement or "技术文章知识抽取与阅读主线整理"}

分析摘要：
{analysis_summary or "暂无"}

固定实体类型：
{", ".join(entity_types) or "暂无"}

固定关系类型：
{", ".join(edge_types) or "暂无"}

图谱摘要：
{graph_digest}

文章正文（可能截断）：
{truncated_text}
"""

    def _build_graph_digest(self, graph_data: Dict[str, Any], domain: str = "tech") -> str:
        nodes = graph_data.get("nodes", []) or []
        edges = graph_data.get("edges", []) or []
        degree_map = Counter()
        for edge in edges:
            source_uuid = edge.get("source_node_uuid")
            target_uuid = edge.get("target_node_uuid")
            if source_uuid:
                degree_map[source_uuid] += 1
            if target_uuid:
                degree_map[target_uuid] += 1

        grouped_nodes: Dict[str, List[tuple[int, str]]] = {}
        for node in nodes:
            labels = [label for label in (node.get("labels") or []) if label != "Entity"]
            label = labels[0] if labels else "Unclassified"
            if label == "Unclassified":
                continue
            if edges and degree_map.get(node.get("uuid"), 0) == 0:
                continue
            grouped_nodes.setdefault(label, [])
            name = (node.get("name") or "").strip()
            if not name:
                continue
            if name in {existing_name for _, existing_name in grouped_nodes[label]}:
                continue
            grouped_nodes[label].append((degree_map.get(node.get("uuid"), 0), name))

        if not grouped_nodes:
            for node in nodes:
                labels = [label for label in (node.get("labels") or []) if label != "Entity"]
                label = labels[0] if labels else "Unclassified"
                if label == "Unclassified":
                    continue
                grouped_nodes.setdefault(label, [])
                name = (node.get("name") or "").strip()
                if name and name not in {existing_name for _, existing_name in grouped_nodes[label]}:
                    grouped_nodes[label].append((degree_map.get(node.get("uuid"), 0), name))

        relation_counts: Dict[str, int] = {}
        for edge in edges:
            relation = edge.get("fact_type") or edge.get("name") or "RELATED"
            relation_counts[relation] = relation_counts.get(relation, 0) + 1

        lines = [
            f"node_count={graph_data.get('node_count', len(nodes))}",
            f"edge_count={graph_data.get('edge_count', len(edges))}",
        ]

        backbone_labels = BACKBONE_LABELS_BY_DOMAIN.get(domain, BACKBONE_LABELS_BY_DOMAIN["tech"])
        backbone_count = 0
        for label in backbone_labels:
            items = grouped_nodes.get(label) or []
            if not items:
                continue
            backbone_count += 1
            ordered_names = [name for _, name in sorted(items, key=lambda item: (-item[0], item[1]))]
            lines.append(f"backbone_{label}: {'、'.join(ordered_names[:4])}")

        if backbone_count < 2:
            fallback_candidates: List[tuple[int, str, str]] = []
            for label, items in grouped_nodes.items():
                if label in backbone_labels:
                    continue
                for degree, name in items:
                    fallback_candidates.append((degree, label, name))

            if fallback_candidates:
                ordered_candidates = sorted(
                    fallback_candidates,
                    key=lambda item: (-item[0], item[1], item[2]),
                )
                preview = "、".join(name for _, _, name in ordered_candidates[:4])
                lines.append(f"backbone_fallback: {preview}")

        for label, items in sorted(grouped_nodes.items()):
            ordered_names = [name for _, name in sorted(items, key=lambda item: (-item[0], item[1]))]
            preview = "、".join(ordered_names[:6]) if ordered_names else "无"
            lines.append(f"{label}: {len(ordered_names)} 个，示例：{preview}")

        if relation_counts:
            ordered_relations = sorted(relation_counts.items(), key=lambda item: (-item[1], item[0]))
            relation_preview = "；".join(f"{name}:{count}" for name, count in ordered_relations[:12])
            lines.append(f"relations: {relation_preview}")

        return "\n".join(lines)

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        fallback_title: str,
        document_text: str,
        graph_data: Dict[str, Any],
        domain: str = "tech",
    ) -> Dict[str, Any]:
        title = self._clean_text(raw.get("title")) or fallback_title
        summary = self._clean_text(raw.get("summary"))

        # Extract article_sections (original article structure from the text)
        raw_sections = raw.get("article_sections", [])
        article_sections = []
        if isinstance(raw_sections, list):
            for section in raw_sections:
                cleaned = self._clean_text(section)
                if cleaned:
                    article_sections.append(cleaned)

        # Methodology domain uses different fallback labels for the second
        # and third backbone stages (solution=核心方法, architecture=论证路径).
        if domain == "methodology":
            solution_fallback = "核心方法"
            architecture_fallback = "论证路径"
        else:
            solution_fallback = "核心方案"
            architecture_fallback = "结构路径"

        result = {
            "title": title,
            "summary": summary,
            "problem": self._normalize_stage(raw.get("problem"), "核心问题"),
            "solution": self._normalize_stage(raw.get("solution"), solution_fallback),
            "architecture": self._normalize_stage(raw.get("architecture"), architecture_fallback),
            "group_titles": self._normalize_group_titles(raw.get("group_titles"), domain=domain),
            "article_sections": article_sections,
            "node_order_hints": self._build_node_order_hints(document_text, graph_data),
        }
        return result

    def _normalize_stage(self, value: Any, fallback_title: str) -> Dict[str, str]:
        if not isinstance(value, dict):
            return {"title": fallback_title, "summary": ""}
        return {
            "title": self._clean_text(value.get("title")) or fallback_title,
            "summary": self._clean_text(value.get("summary")),
        }

    def _normalize_group_titles(self, value: Any, *, domain: str = "tech") -> Dict[str, str]:
        """Domain-scoped group_titles: base set is domain-specific, no
        cross-domain leakage. Tech ontology never exports Step/Antipattern;
        methodology never exports Layer/Technology/Mechanism."""
        base = dict(GROUP_TITLES_BY_DOMAIN.get(domain, DEFAULT_GROUP_TITLES))
        titles = dict(base)
        if isinstance(value, dict):
            # Accept LLM's override for the known keys
            for key, default in base.items():
                cleaned = self._clean_text(value.get(key))
                if cleaned:
                    titles[key] = cleaned
                else:
                    titles[key] = default
            # Tolerate LLM adding keys that belong to the current domain only
            for key, val in value.items():
                if key in titles:
                    continue
                # Only accept extra keys that exist in the domain's allowed set
                if key in base:
                    cleaned = self._clean_text(val)
                    if cleaned:
                        titles[key] = cleaned
                # Keys from other domains (e.g., Layer/Technology for methodology)
                # are silently dropped.
        return titles

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        text = " ".join(text.split())
        return text[:120]

    def _build_node_order_hints(self, document_text: str, graph_data: Dict[str, Any]) -> Dict[str, int]:
        normalized_text = self._normalize_for_lookup(document_text)
        if not normalized_text:
            return {}

        matches = []
        for node in graph_data.get("nodes", []) or []:
            node_id = node.get("uuid")
            node_name = (node.get("name") or "").strip()
            if not node_id or len(node_name) < 2:
                continue

            position = self._find_text_position(node_name, normalized_text)
            if position is None:
                continue

            matches.append((node_id, position))

        matches.sort(key=lambda item: item[1])
        return {node_id: index for index, (node_id, _) in enumerate(matches)}

    def _find_text_position(self, node_name: str, normalized_text: str) -> Optional[int]:
        normalized_name = self._normalize_for_lookup(node_name)
        if len(normalized_name) < 2:
            return None

        exact_position = normalized_text.find(normalized_name)
        if exact_position >= 0:
            return exact_position

        compact_name = normalized_name.replace(" ", "")
        compact_text = normalized_text.replace(" ", "")
        if len(compact_name) >= 2:
            compact_position = compact_text.find(compact_name)
            if compact_position >= 0:
                return compact_position

        relaxed_name = compact_name.replace("-", "").replace("_", "").replace("/", "")
        relaxed_text = compact_text.replace("-", "").replace("_", "").replace("/", "")
        if len(relaxed_name) >= 2:
            relaxed_position = relaxed_text.find(relaxed_name)
            if relaxed_position >= 0:
                return relaxed_position

        return None

    def _normalize_for_lookup(self, value: str) -> str:
        text = (value or "").lower().strip()
        if not text:
            return ""
        return " ".join(text.split())
