#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "wiki_intake"))

from generate_decision_digest import generate_decision_digest  # noqa: E402


class DecisionDigestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="decision-digest-test-"))
        self.clippings = self.tmp / "clippings"
        self.intake = self.tmp / "intake"
        self.clippings.mkdir(parents=True)
        self.intake.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def write_candidate(self, source_id: str, topic_id: str, markdown: str) -> Path:
        source_path = self.clippings / f"{source_id}.md"
        source_path.write_text(markdown, encoding="utf-8")
        record = {
            "source_id": source_id,
            "title": source_id,
            "source_url": f"https://example.com/{source_id}",
            "source_file_path": str(source_path),
            "content_hash": f"sha256:{hashlib.sha256(markdown.encode('utf-8')).hexdigest()}",
            "guessed_topics": [{"topic_id": topic_id, "score": 3}],
        }
        with (self.intake / "manifest.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return source_path

    def test_decision_digest_recommends_reasoning_topic_without_wiki_mutation(self) -> None:
        self.write_candidate(
            "agent-cot",
            "agent-harness",
            """---
title: "Agent：思维链你在教我做事啊？"
source_url: "https://example.com/agent-cot"
---

# Agent：思维链你在教我做事啊？

这篇文章讨论 Agent 在推理式思考、思维链表达、行为边界和用户控制感上的变化。
作者认为这不是单纯的 harness 或工具编排问题，而是智能体式思考如何暴露给用户的问题。

本地路径 /Users/mac/not/article.md 不能被当成文章事实。
""",
        )
        result = generate_decision_digest(self.intake, "agent-cot", mode="deterministic")
        digest = result["digest"]

        self.assertEqual(digest["digest_version"], "decision_digest_v1")
        self.assertTrue(digest["source_only"])
        self.assertFalse(digest["web_research_used"])
        self.assertFalse(digest["wiki_mutation"])
        self.assertEqual(digest["scanner_signal"]["primary_topic"], "agent-harness")
        topic = digest["topic_recommendation"]
        self.assertEqual(topic["recommended_topic_id"], "agent-reasoning-behavior")
        self.assertTrue(topic["scanner_differs"])
        self.assertTrue(Path(result["json_path"]).exists())
        self.assertTrue(Path(result["md_path"]).exists())
        self.assertIn("pre_digest", result["json_path"])
        self.assertFalse((self.tmp / "wiki" / "topics" / "agent-reasoning-behavior" / "raw" / "articles").exists())

        semantic_text = "\n".join(
            [
                digest["article_understanding"]["summary"],
                digest["article_understanding"]["main_claim"],
                topic["rationale"],
            ]
        )
        self.assertNotIn("/Users/", semantic_text)

    def test_decision_digest_separates_devtools_economics_from_tokenization(self) -> None:
        self.write_candidate(
            "copilot-price",
            "ai-tokenization",
            """---
title: "Copilot 和 Claude Code 一起涨价"
source_url: "https://example.com/copilot-price"
---

# Copilot 和 Claude Code 一起涨价

文章讨论 AI coding、Copilot、Claude Code、AI credits 和 usage-based billing。
它关心的是 agentic coding 的成本模型，而不是 tokenizer 机制。
""",
        )
        result = generate_decision_digest(self.intake, "copilot-price", mode="deterministic")
        topic = result["digest"]["topic_recommendation"]

        self.assertEqual(result["digest"]["scanner_signal"]["primary_topic"], "ai-tokenization")
        self.assertEqual(topic["recommended_topic_id"], "ai-devtools-economics")
        self.assertTrue(topic["scanner_differs"])
        self.assertIn("AI 编程工具", topic["recommended_topic_label"])


if __name__ == "__main__":
    unittest.main()
