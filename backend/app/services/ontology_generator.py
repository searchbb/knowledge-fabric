"""
本体生成服务
分析技术文章内容，生成适合认知图谱建模的实体和关系类型定义
"""

import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient

logger = logging.getLogger('mirofish.ontology')

FIXED_ENTITY_TYPE_ORDER = [
    "Topic",
    "Problem",
    "Solution",
    "Architecture",
    "Layer",
    "Mechanism",
    "Decision",
    "Technology",
    "Metric",
    "Evidence",
    "Insight",
    "Example",
]

# 核心类型：每篇文章必须输出
CORE_ENTITY_TYPES = {"Topic", "Problem", "Solution", "Technology", "Example"}

# 条件类型：仅当文章内容明确涉及时才启用
CONDITIONAL_ENTITY_TYPES = {"Architecture", "Layer", "Decision", "Mechanism", "Metric", "Evidence", "Insight"}

FIXED_EDGE_TYPE_ORDER = [
    "HAS_TOPIC",
    "HAS_PROBLEM",
    "SOLVES",
    "IMPLEMENTED_BY",
    "HAS_LAYER",
    "USES_MECHANISM",
    "USES_TECHNOLOGY",
    "JUSTIFIED_BY",
    "OUTPERFORMS",
    "HAS_EXAMPLE",
    "EVIDENCED_BY",
    "PRODUCES",
]

ENTITY_NAME_ALIASES = {
    "topic": "Topic",
    "主题": "Topic",
    "problem": "Problem",
    "问题": "Problem",
    "solution": "Solution",
    "方案": "Solution",
    "architecture": "Architecture",
    "架构": "Architecture",
    "layer": "Layer",
    "层级": "Layer",
    "层": "Layer",
    "mechanism": "Mechanism",
    "机制": "Mechanism",
    "decision": "Decision",
    "决策": "Decision",
    "technology": "Technology",
    "技术": "Technology",
    "tool": "Technology",
    "metric": "Metric",
    "指标": "Metric",
    "evaluation": "Metric",
    "evidence": "Evidence",
    "证据": "Evidence",
    "数据": "Evidence",
    "事实": "Evidence",
    "observation": "Evidence",
    "finding": "Evidence",
    "发现": "Evidence",
    "insight": "Insight",
    "洞察": "Insight",
    "结论": "Insight",
    "conclusion": "Insight",
    "principle": "Insight",
    "原则": "Insight",
    "example": "Example",
    "案例": "Example",
    "场景": "Example",
}

EDGE_NAME_ALIASES = {
    "hastopic": "HAS_TOPIC",
    "涉及主题": "HAS_TOPIC",
    "hasproblem": "HAS_PROBLEM",
    "存在问题": "HAS_PROBLEM",
    "solves": "SOLVES",
    "解决方案": "SOLVES",
    "implementedby": "IMPLEMENTED_BY",
    "实现架构": "IMPLEMENTED_BY",
    "haslayer": "HAS_LAYER",
    "包含层级": "HAS_LAYER",
    "usesmechanism": "USES_MECHANISM",
    "使用机制": "USES_MECHANISM",
    "usestechnology": "USES_TECHNOLOGY",
    "使用技术": "USES_TECHNOLOGY",
    "justifiedby": "JUSTIFIED_BY",
    "基于依据": "JUSTIFIED_BY",
    "outperforms": "OUTPERFORMS",
    "优于对比": "OUTPERFORMS",
    "hasexample": "HAS_EXAMPLE",
    "验证案例": "HAS_EXAMPLE",
    "evidencedby": "EVIDENCED_BY",
    "有证据": "EVIDENCED_BY",
    "支撑": "EVIDENCED_BY",
    "produces": "PRODUCES",
    "产出": "PRODUCES",
    "产生结果": "PRODUCES",
}


def _normalize_identifier_key(name: str) -> str:
    """将标识名归一为便于匹配的 key。"""
    return re.sub(r"[\W_]+", "", str(name), flags=re.UNICODE).lower()


def _to_pascal_case(name: str) -> str:
    """将任意格式的名称转换为 PascalCase。"""
    parts = re.split(r"[^a-zA-Z0-9]+", str(name))
    words = []
    for part in parts:
        words.extend(re.sub(r"([a-z])([A-Z])", r"\1_\2", part).split("_"))
    result = "".join(word.capitalize() for word in words if word)
    return result if result else "Unknown"


def _to_upper_snake_case(name: str) -> str:
    """将任意格式的名称转换为 UPPER_SNAKE_CASE。"""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.upper() if text else "UNKNOWN"


def _canonicalize_name(name: str, aliases: Dict[str, str], fallback_converter) -> str:
    """优先按固定 schema 做别名映射，否则回退到格式规范化。"""
    normalized_key = _normalize_identifier_key(name)
    if normalized_key in aliases:
        return aliases[normalized_key]
    return fallback_converter(name)


def _order_by_name(items: List[Dict[str, Any]], ordered_names: List[str]) -> List[Dict[str, Any]]:
    """按固定名称顺序排序，未命中的项保留在末尾。"""
    order_index = {name: index for index, name in enumerate(ordered_names)}
    return sorted(items, key=lambda item: (order_index.get(item.get("name"), len(order_index)), item.get("name", "")))


def _normalize_entity_type_name(name: str) -> str:
    """将实体类型名收敛到固定 schema。"""
    normalized = _canonicalize_name(name, ENTITY_NAME_ALIASES, _to_pascal_case)
    _all_known = set(FIXED_ENTITY_TYPE_ORDER)
    if normalized in _all_known:
        return normalized
    key = _normalize_identifier_key(name)
    if key in {"example", "case", "usecase", "scenario", "案例", "场景"}:
        fallback = "Example"
    elif key in {"evidence", "observation", "finding", "数据", "证据", "事实", "发现"}:
        fallback = "Evidence"
    elif key in {"insight", "conclusion", "principle", "洞察", "结论", "原则"}:
        fallback = "Insight"
    else:
        fallback = "Technology"
    logger.warning(f"Unknown entity type '{name}' remapped to fallback '{fallback}'")
    return fallback


def _normalize_edge_type_name(name: str) -> str:
    """将关系类型名收敛到固定 schema。"""
    normalized = _canonicalize_name(name, EDGE_NAME_ALIASES, _to_upper_snake_case)
    if normalized in FIXED_EDGE_TYPE_ORDER:
        return normalized
    logger.warning(f"Unknown edge type '{name}' discarded during validation")
    return ""


# 本体生成的系统提示词
ONTOLOGY_SYSTEM_PROMPT = """你是一个专业的知识图谱本体设计专家。你的任务是分析给定的技术文章内容，设计适合**技术文章认知图谱**的实体类型和关系类型。

**重要：你必须输出有效的JSON格式数据，不要输出任何其他内容。**

## 核心任务背景

我们正在构建一个**技术文章认知图谱系统**。在这个系统中：
- 每个实体都是技术文章中的一个认知要素（主题、问题、方案、证据、洞察等）
- 实体之间的关系反映技术文章的**论证逻辑**和知识结构
- 目标不仅是"文章讲了什么"，更是"作者怎么论证的"——问题→方法→证据→结论

因此，**实体必须是技术文章中可识别的认知要素**：

**可以是**：
- 文章讨论的核心主题（如"可观测性"、"微服务架构"）
- 文章提出或分析的技术问题（如"Agent执行过程不可见"、"日志碎片化"）
- 文章给出的解决方案（如"构建可观测插件"、"统一日志平台"）
- 系统架构或架构模式（如"四层架构"、"采集-建模-存储-展示"）——仅当文章**明确提出**架构设计时
- 架构中的层级或组件（如"数据采集层"、"存储层"）——仅当文章**明确描述**分层结构时
- 使用的机制或设计模式（如"Hook拦截"、"异步写入"、"Trace链路"）
- 做出的技术决策或选型依据（如"选择DuckDB而非SQLite"）——仅当文章**明确对比**并做出选择时
- 具体的技术、工具、框架（如"DuckDB"、"OpenTelemetry"）
- 性能指标或度量维度（如"失败率"、"延迟"、"Token消耗"）——抽象的衡量维度
- 具体的数据事实或实验发现（如"15%任务链失败"、"消耗是成功任务的3.27倍"）——带数值的观测事实
- 作者的核心洞察或结论（如"Token异常是最好的异常检测器"、"AI可观测性终局是闭环"）
- 验证方案的案例或场景（如"排障案例"、"电商秒杀场景"）

**不可以是**：
- 纯粹的代码片段（应提炼为技术概念）
- 与文章主题无关的泛化概念
- 文章没有明确表述、靠推断编造的内容

## 输出格式

请输出JSON格式，包含以下结构：

```json
{
    "entity_types": [
        {
            "name": "实体类型名称（英文，固定使用 PascalCase）",
            "description": "简短描述（中文，不超过100字符）",
            "attributes": [
                {
                    "name": "属性名（英文，snake_case）",
                    "type": "text",
                    "description": "属性描述"
                }
            ],
            "examples": ["从文章中提取的具体实例1", "具体实例2"]
        }
    ],
    "edge_types": [
        {
            "name": "关系类型名称（英文，固定使用 UPPER_SNAKE_CASE）",
            "description": "简短描述（中文，不超过100字符）",
            "source_targets": [
                {"source": "源实体类型（英文固定标识）", "target": "目标实体类型（英文固定标识）"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "对文本内容的简要分析说明（中文）"
}
```

## 设计指南（极其重要！）

### 1. 实体类型设计

**数量要求：输出 8-12 个实体类型**

实体类型分为**核心类型**（必须包含）和**条件类型**（按文章内容决定是否启用）。

**核心类型（必须包含，共5个）**：

1. `Topic`（主题）: 文章讨论的核心主题或技术领域。每篇文章通常有1-2个核心主题。
2. `Problem`（问题）: 文章提出或分析的技术问题、痛点、挑战。这是文章论证的起点。
3. `Solution`（方案）: 文章给出的解决方案、策略、方法。直接回应问题。
4. `Technology`（技术）: 具体的技术、工具、框架、协议。
5. `Example`（案例）: 实际案例、应用场景、验证结果。

**条件类型（按文章内容选择，选3-7个）**：

6. `Architecture`（架构）: 系统架构、架构模式、整体设计。**仅当文章明确提出了系统架构设计时才使用**，不要把一般性的方法论或困境分析误归为架构。
7. `Layer`（层级）: 架构中的层次、模块、组件。**仅当文章明确描述了分层结构时才使用**，不要为了填充类型而强行切分层级。
8. `Mechanism`（机制）: 使用的机制、设计模式、算法、核心技术手段。
9. `Decision`（决策）: 技术选型、权衡决策及其依据。**仅当文章明确对比了多个选项并给出选择理由时才使用**，不要推断文章没有表述的决策。
10. `Metric`（指标）: 抽象的性能指标、度量维度、评估维度。如"失败率"、"延迟"、"Token消耗"——不带具体数值。
11. `Evidence`（证据）: 具体的数据事实、实验结果、定量发现。如"15%任务链失败"、"消耗310万Token"——带具体数值或观测结果。这是支撑论点的事实单元。
12. `Insight`（洞察）: 作者的核心洞察、结论性判断、原则总结。如"Token异常是最好的异常检测器"、"失败是概率性的"。通常出现在文章结语或总结中。

**重要约束**：
- 如果文章没有明确的分层架构设计，**不要输出 Architecture 和 Layer**
- 如果文章没有明确的技术选型对比，**不要输出 Decision**
- 如果文章有大量数据论证，**必须输出 Evidence**
- 如果文章有明确的结论性洞察，**必须输出 Insight**

**兜底类型说明**：
- `Technology`: 当某个概念不属于其他更具体类型时，如果它是一个具体的技术/工具/框架，归入此类
- `Example`: 当某个内容不属于其他更具体类型时，如果它是一个具体的场景/案例/实例，归入此类

**主链结构（文章论证的核心骨架，极其重要）**：

一篇技术文章的论证结构通常是：
  Topic → Problem → Solution（→ Architecture，如果有的话）

即：文章围绕某个**主题(Topic)**展开，分析了该主题下的**问题(Problem)**，提出了**方案(Solution)**来解决问题。

更完整的论证链可以是：
  Problem → Solution → Evidence → Insight
  即：方案通过证据验证，最终得出洞察性结论。

你必须确保 examples 字段中包含从文章中提取的具体实例，让后续的图谱构建能形成论证链。

### 2. 关系类型设计 - 固定12个

**固定的12个关系类型（name 字段必须用英文 UPPER_SNAKE_CASE）**：

1. `HAS_TOPIC`（涉及主题）: 连接任意实体到它所属的主题。
   source_targets: [{"source": "Problem", "target": "Topic"}, {"source": "Solution", "target": "Topic"}, {"source": "Technology", "target": "Topic"}]

2. `HAS_PROBLEM`（存在问题）: 主题或系统中存在的问题。
   source_targets: [{"source": "Topic", "target": "Problem"}, {"source": "Architecture", "target": "Problem"}]

3. `SOLVES`（解决方案）: 方案解决了某个问题。
   source_targets: [{"source": "Solution", "target": "Problem"}]

4. `IMPLEMENTED_BY`（实现架构）: 方案通过某个架构来实现。
   source_targets: [{"source": "Solution", "target": "Architecture"}]

5. `HAS_LAYER`（包含层级）: 架构包含的层级/组件。
   source_targets: [{"source": "Architecture", "target": "Layer"}]

6. `USES_MECHANISM`（使用机制）: 方案或层级使用了某种机制。
   source_targets: [{"source": "Solution", "target": "Mechanism"}, {"source": "Layer", "target": "Mechanism"}, {"source": "Architecture", "target": "Mechanism"}]

7. `USES_TECHNOLOGY`（使用技术）: 任意实体使用了某项具体技术。
   source_targets: [{"source": "Solution", "target": "Technology"}, {"source": "Architecture", "target": "Technology"}, {"source": "Layer", "target": "Technology"}, {"source": "Mechanism", "target": "Technology"}]

8. `JUSTIFIED_BY`（基于依据）: 决策基于某个指标或依据。
   source_targets: [{"source": "Decision", "target": "Metric"}, {"source": "Decision", "target": "Technology"}]

9. `OUTPERFORMS`（优于对比）: 技术优于另一个技术，或方案优于另一个方案。
   source_targets: [{"source": "Technology", "target": "Technology"}, {"source": "Solution", "target": "Solution"}]

10. `HAS_EXAMPLE`（验证案例）: 方案或架构通过案例验证。
    source_targets: [{"source": "Solution", "target": "Example"}, {"source": "Architecture", "target": "Example"}, {"source": "Mechanism", "target": "Example"}]

11. `EVIDENCED_BY`（有证据支撑）: 方案、洞察或结论由具体数据事实支撑。
    source_targets: [{"source": "Solution", "target": "Evidence"}, {"source": "Insight", "target": "Evidence"}, {"source": "Problem", "target": "Evidence"}]

12. `PRODUCES`（产出结果）: 方法或机制产出了某个结果、发现或产物。
    source_targets: [{"source": "Solution", "target": "Evidence"}, {"source": "Mechanism", "target": "Evidence"}, {"source": "Solution", "target": "Insight"}]

### 3. 属性设计

- 每个实体类型1-3个关键属性
- **注意**：属性名不能使用 `name`、`uuid`、`group_id`、`created_at`、`summary`、`name_embedding`（这些是系统保留字）
- 属性名必须使用英文 snake_case
- 推荐属性：
  - Topic: `domain`(所属领域), `scope`(范围)
  - Problem: `severity`(严重程度), `context`(发生场景)
  - Solution: `approach`(方法类型), `trade_off`(权衡点)
  - Architecture: `pattern`(架构模式), `scale`(规模)
  - Layer: `responsibility`(职责), `position`(位置)
  - Mechanism: `principle`(原理), `trigger_condition`(触发条件)
  - Decision: `reasoning`(理由), `alternatives`(备选项)
  - Technology: `category`(类别), `version_info`(版本)
  - Metric: `unit`(单位), `benchmark`(基准值)
  - Evidence: `data_value`(具体数值), `source_context`(来源上下文)
  - Insight: `confidence`(确信度), `scope`(适用范围)
  - Example: `scenario`(场景), `outcome`(结果)

## 重要提醒

1. 实体类型的 name 字段必须使用固定的英文 PascalCase 名称，从以下12个中选择8-12个：Topic/Problem/Solution/Architecture/Layer/Mechanism/Decision/Technology/Metric/Evidence/Insight/Example
2. 关系类型的 name 字段必须使用固定的英文 UPPER_SNAKE_CASE 名称（12个全部输出）
3. description 字段用中文，根据文章内容具体化，但不超过100字符
4. examples 字段必须从文章中提取具体的实例，不要编造
5. source_targets 必须覆盖上述指定的实体类型对
6. 属性名必须用英文 snake_case，不能用中文，不能用保留字
7. 即使 description 和 analysis_summary 使用中文，name/source/target 这些技术标识也绝对不要翻译成中文
8. **条件类型使用判断**：仔细阅读文章，只在文章有明确对应内容时才启用条件类型，不要为了凑数而强行使用
"""


class OntologyGenerator:
    """
    本体生成器
    分析技术文章内容，生成认知图谱的实体和关系类型定义
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成本体定义

        Args:
            document_texts: 文档文本列表
            simulation_requirement: 分析需求描述
            additional_context: 额外上下文

        Returns:
            本体定义（entity_types, edge_types等）
        """
        # 构建用户消息
        user_message = self._build_user_message(
            document_texts,
            simulation_requirement,
            additional_context
        )

        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        # 调用LLM（失败时直接向上抛出异常，不做 fallback）
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        result["metadata"] = {
            "generation_mode": "llm",
        }

        # 验证和后处理
        result = self._validate_and_process(result)

        return result

    # ontology 只需要文章高层结构，不需要把整篇长文都送给模型。
    MAX_TEXT_LENGTH_FOR_LLM = 8000

    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """构建用户消息"""

        # 合并文本
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        # 如果文本超过5万字，截断
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(原文共{original_length}字，已截取前{self.MAX_TEXT_LENGTH_FOR_LLM}字用于本体分析)..."

        message = f"""## 分析需求

{simulation_requirement}

## 文档内容

{combined_text}
"""

        if additional_context:
            message += f"""
## 额外说明

{additional_context}
"""

        message += """
请根据以上技术文章内容，设计技术文章认知图谱的实体和关系定义。

**必须遵守的规则**：
1. 输出 8-12 个实体类型。核心类型（Topic, Problem, Solution, Technology, Example）必须包含，条件类型按文章内容选择
2. 输出全部 12 个关系类型：HAS_TOPIC, HAS_PROBLEM, SOLVES, IMPLEMENTED_BY, HAS_LAYER, USES_MECHANISM, USES_TECHNOLOGY, JUSTIFIED_BY, OUTPERFORMS, HAS_EXAMPLE, EVIDENCED_BY, PRODUCES
3. 兜底类型是 Technology 和 Example
4. 必须确保主链结构：Topic → Problem → Solution
5. 属性名必须用英文 snake_case，不能使用 name、uuid、group_id 等保留字
6. examples 字段必须从文章中提取具体实例，不要编造
7. description 字段根据文章内容具体化描述
8. 条件类型判断：Architecture/Layer 仅在文章有明确架构设计时使用；Decision 仅在文章有明确选型对比时使用；Evidence 在文章有数据论证时必须使用；Insight 在文章有结论性判断时必须使用
"""

        return message

    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证和后处理结果"""

        # 确保必要字段存在
        if "entity_types" not in result or not isinstance(result["entity_types"], list):
            result["entity_types"] = []
        if "edge_types" not in result or not isinstance(result["edge_types"], list):
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""

        # 验证实体类型
        entity_name_map: Dict[str, str] = {}
        deduped_entities: List[Dict[str, Any]] = []
        seen_entity_names = set()
        for entity in result["entity_types"]:
            if not isinstance(entity, dict):
                continue
            original_name = str(entity.get("name", "")).strip()
            if original_name:
                normalized_name = _normalize_entity_type_name(original_name)
                entity["name"] = normalized_name
                entity_name_map[original_name] = normalized_name
                entity_name_map[_normalize_identifier_key(original_name)] = normalized_name
                if normalized_name != original_name:
                    logger.warning(f"Entity type name '{original_name}' normalized to '{normalized_name}'")
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
            entity_name = entity.get("name", "")
            if entity_name and entity_name not in seen_entity_names:
                seen_entity_names.add(entity_name)
                deduped_entities.append(entity)
            elif entity_name:
                logger.warning(f"Duplicate entity type '{entity_name}' removed during validation")
        result["entity_types"] = _order_by_name(deduped_entities, FIXED_ENTITY_TYPE_ORDER)

        # 验证关系类型
        deduped_edges: List[Dict[str, Any]] = []
        seen_edge_names = set()
        for edge in result["edge_types"]:
            if not isinstance(edge, dict):
                continue
            original_name = str(edge.get("name", "")).strip()
            if original_name:
                normalized_name = _normalize_edge_type_name(original_name)
                edge["name"] = normalized_name
                if normalized_name != original_name:
                    logger.warning(f"Edge type name '{original_name}' normalized to '{normalized_name}'")
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
            normalized_pairs = []
            seen_pairs = set()
            for source_target in edge.get("source_targets", []):
                if not isinstance(source_target, dict):
                    continue
                source_name = str(source_target.get("source", "")).strip()
                target_name = str(source_target.get("target", "")).strip()
                source = entity_name_map.get(
                    source_name,
                    entity_name_map.get(
                        _normalize_identifier_key(source_name),
                        _normalize_entity_type_name(source_name),
                    ),
                )
                target = entity_name_map.get(
                    target_name,
                    entity_name_map.get(
                        _normalize_identifier_key(target_name),
                        _normalize_entity_type_name(target_name),
                    ),
                )
                if not source or not target:
                    continue
                pair = (source, target)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                normalized_pairs.append({"source": source, "target": target})
            edge["source_targets"] = normalized_pairs
            edge_name = edge.get("name", "")
            if edge_name and edge_name not in seen_edge_names:
                seen_edge_names.add(edge_name)
                deduped_edges.append(edge)
            elif edge_name:
                logger.warning(f"Duplicate edge type '{edge_name}' removed during validation")
        result["edge_types"] = _order_by_name(deduped_edges, FIXED_EDGE_TYPE_ORDER)

        MAX_ENTITY_TYPES = 12
        MAX_EDGE_TYPES = 12

        # 兜底类型定义（技术文章认知建模场景）
        tech_fallback = {
            "name": "Technology",
            "description": "具体的技术、工具、框架、协议，不属于其他类型时归入此类",
            "attributes": [
                {"name": "category", "type": "text", "description": "技术类别"},
                {"name": "version_info", "type": "text", "description": "版本信息"}
            ],
            "examples": ["通用技术"]
        }

        case_fallback = {
            "name": "Example",
            "description": "实际应用案例、验证场景、实践结果，不属于其他类型时归入此类",
            "attributes": [
                {"name": "scenario", "type": "text", "description": "应用场景"},
                {"name": "outcome", "type": "text", "description": "实施结果"}
            ],
            "examples": ["通用案例"]
        }

        # 检查是否已有兜底类型
        entity_names = {e["name"] for e in result["entity_types"]}
        has_tech = "Technology" in entity_names
        has_case = "Example" in entity_names

        # 需要添加的兜底类型
        fallbacks_to_add = []
        if not has_tech:
            fallbacks_to_add.append(tech_fallback)
        if not has_case:
            fallbacks_to_add.append(case_fallback)

        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)

            if current_count + needed_slots > MAX_ENTITY_TYPES:
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                result["entity_types"] = result["entity_types"][:-to_remove]

            result["entity_types"].extend(fallbacks_to_add)
            result["entity_types"] = _order_by_name(result["entity_types"], FIXED_ENTITY_TYPE_ORDER)

        # 最终确保不超过限制
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]

        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]

        # 主链完整性校验（核心类型必须存在）
        existing_names = {e["name"] for e in result["entity_types"]}
        missing_core = CORE_ENTITY_TYPES - existing_names
        if missing_core:
            logger.warning(f"核心类型缺失: {missing_core}，可能影响图谱质量")

        missing_edges = set(FIXED_EDGE_TYPE_ORDER) - {e.get("name") for e in result["edge_types"]}
        if missing_edges:
            logger.warning(f"固定关系类型缺失: {missing_edges}，可能影响图谱可解释性")

        return result

    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        将本体定义转换为Python代码（保留兼容性）
        """
        code_lines = [
            '"""',
            '自定义实体类型定义',
            '由Knowledge Fabric自动生成，用于技术文章认知建模',
            '"""',
            '',
            'from pydantic import Field',
            '',
            '',
            '# ============== 实体类型定义 ==============',
            '',
        ]

        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"{name} 实体类型")

            code_lines.append(f'class {name}:')
            code_lines.append(f'    """{desc}"""')

            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: str = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')

            code_lines.append('')
            code_lines.append('')

        code_lines.append('# ============== 关系类型定义 ==============')
        code_lines.append('')

        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            desc = edge.get("description", f"{name} 关系类型")

            code_lines.append(f'class {name}:')
            code_lines.append(f'    """{desc}"""')

            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: str = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')

            code_lines.append('')
            code_lines.append('')

        return '\n'.join(code_lines)
