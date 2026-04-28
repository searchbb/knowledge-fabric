"""Article domain classifier (v3 Stage 4).

Routes articles between tech and methodology ontologies when the user
hasn't manually chosen (project.domain='auto'). Reads title + first 2000
chars to keep token cost low.

Output schema: {primary, confidence, secondary, secondary_confidence, reason}
where primary ∈ {'tech', 'methodology'}. Callers (ontology_dispatcher) apply
the 0.65 fallback threshold on `confidence`.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from ..utils.llm_client import LLMClient

logger = logging.getLogger("mirofish.domain_classifier")


VALID_DOMAINS = {"tech", "methodology"}

CLASSIFIER_SYSTEM_PROMPT = """你是文章领域路由分类器。请判断下面文章更适合进入哪一种知识图谱本体：

- tech：技术实现、系统架构、工程方案、性能优化、产品技术设计、论文技术方法
- methodology：方法论、认知框架、自助成长、管理经验、做事原则、流程套路

判定标准：

1. 看文章主体在回答"系统/技术是如何设计和实现的"，还是"人应该如何思考与行动"。
2. 若文章有技术名词，但主体是在讲通用方法、认知框架、决策原则，判 methodology。
3. 若文章有步骤，但主体是在讲技术系统、模块、机制、实现细节，判 tech。
4. 新闻评论、时评、观点综述、泛资讯，若不能稳定归入 methodology，则偏向 tech 作为安全默认（fallback）。

输出严格 JSON，不要输出 markdown，格式：

{
  "primary": "tech" | "methodology",
  "confidence": 0.0-1.0,
  "secondary": "tech" | "methodology" | null,
  "secondary_confidence": 0.0-1.0,
  "reason": "一句话说明"
}"""


class DomainClassifier:
    """Classify an article into tech vs methodology for ontology routing."""

    MAX_BODY_CHARS = 2000

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client

    def classify(self, *, title: str, text: str) -> Dict[str, Any]:
        """Classify the article. Returns the 5-field result dict.

        Failure modes are SAFE by design:
        - LLM raises / malformed output → return tech with confidence=0.0
          (dispatcher will fall back to tech).
        - Unknown primary value → coerce to tech with confidence=0.0.
        """
        try:
            llm = self.llm_client or LLMClient()
            body = (text or "")[: self.MAX_BODY_CHARS]
            user_msg = (
                f"文章标题：{title or '(无)'}\n\n"
                f"文章正文（前 {self.MAX_BODY_CHARS} 字）：\n{body}\n\n"
                "请判断领域并返回 JSON。"
            )
            messages = [
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ]
            result = llm.chat_json(messages=messages, temperature=0.0, max_tokens=512)
        except Exception as e:
            logger.warning("DomainClassifier LLM call failed: %s", e)
            return self._safe_default(reason=f"llm_error: {e!s}"[:200])

        primary = str(result.get("primary", "")).strip().lower()
        if primary not in VALID_DOMAINS:
            logger.warning(
                "DomainClassifier got unknown primary %r — coercing to tech", primary
            )
            return self._safe_default(reason=f"unknown primary {primary!r}")

        return {
            "primary": primary,
            "confidence": float(result.get("confidence", 0) or 0),
            "secondary": result.get("secondary") if result.get("secondary") in VALID_DOMAINS else None,
            "secondary_confidence": float(result.get("secondary_confidence", 0) or 0),
            "reason": str(result.get("reason", ""))[:300],
        }

    @staticmethod
    def _safe_default(*, reason: str) -> Dict[str, Any]:
        return {
            "primary": "tech",
            "confidence": 0.0,
            "secondary": None,
            "secondary_confidence": 0.0,
            "reason": reason,
        }
