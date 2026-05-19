#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "wiki_intake"))

from apply_intake_decision import ProcessorContext, apply_decision  # noqa: E402
from generate_source_digest import generate_source_digest  # noqa: E402


class SourceDigestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="source-digest-test-"))
        self.clippings = self.tmp / "clippings"
        self.intake = self.tmp / "intake"
        self.wiki = self.tmp / "wiki"
        self.topic = self.wiki / "topics" / "ai-tokenization"
        (self.topic / "raw" / "articles").mkdir(parents=True)
        self.clippings.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def write_source(self, name: str = "article.md") -> Path:
        source = self.clippings / name
        source.write_text(
            """---
title: "为什么 token 成本会改变 AI 编程工具"
source_url: "https://example.com/token"
---

# 为什么 token 成本会改变 AI 编程工具

作者认为，AI 编程工具从订阅制走向 usage-based billing，是因为长上下文和 agentic coding 会显著增加推理成本。

文中举例说，某些用户在 Claude Code 和 GitHub Copilot 上的高频调用会消耗大量 AI Credits。

这个判断仍需要官方价格页、厂商公告和反方案例来验证。

本地路径 /Users/mac/not/article.md 不应该进入 digest。
""",
            encoding="utf-8",
        )
        return source

    def test_digest_schema_filters_paths_and_noisy_concepts(self) -> None:
        raw = self.topic / "raw" / "articles" / "2026-05-08-token.md"
        raw.write_text(self.write_source().read_text(encoding="utf-8"), encoding="utf-8")
        result = generate_source_digest(
            topic_root=self.topic,
            raw_article_path=raw,
            candidate_id="cand_digest",
            source_fingerprint="fp123",
            selected_topic="ai-tokenization",
            recommended_topic="ai-tokenization",
            mode="deterministic",
        )
        digest = result["digest"]
        self.assertEqual(digest["digest_version"], "source_digest_v1")
        self.assertEqual(digest["candidate_id"], "cand_digest")
        self.assertTrue(Path(result["json_path"]).exists())
        self.assertTrue(Path(result["md_path"]).exists())
        joined = "\n".join([digest["main_claim"], *digest["key_points"], *digest["mechanism"]])
        self.assertNotIn("/Users/", joined)
        self.assertNotIn("路径", digest["candidate_concepts"])
        self.assertNotIn("作者", digest["candidate_concepts"])
        self.assertNotIn("为什么", digest["candidate_concepts"])

    def test_source_digest_can_derive_from_accepted_decision_digest(self) -> None:
        raw = self.topic / "raw" / "articles" / "2026-05-08-token.md"
        raw.write_text(self.write_source().read_text(encoding="utf-8"), encoding="utf-8")
        decision_digest = {
            "digest_version": "decision_digest_v1",
            "candidate_id": "cand_digest",
            "source_fingerprint": "sha256:decision",
            "source_title": "为什么 token 成本会改变 AI 编程工具",
            "source_language": "zh",
            "source_only": True,
            "web_research_used": False,
            "wiki_mutation": False,
            "scanner_signal": {"primary_topic": "ai-tokenization", "guessed_topics": []},
            "article_understanding": {
                "article_type": "technical_analysis",
                "summary": "已采纳摘要会进入 source digest。",
                "main_claim": "已采纳主张会进入 source digest。",
                "key_points": ["已采纳关键点一", "已采纳关键点二"],
                "important_entities": ["Claude Code", "GitHub Copilot"],
                "mechanisms": ["已采纳机制解释"],
                "evidence_in_source": ["已采纳原文证据"],
                "uncertainties": ["已采纳待验证问题"],
            },
            "topic_recommendation": {
                "scanner_topic_id": "ai-tokenization",
                "recommended_topic_id": "ai-devtools-economics",
                "recommended_topic_label": "AI 编程工具经济学",
                "confidence": "high",
                "fit_status": "strong_fit",
                "rationale": "已采纳推荐理由。",
                "alternative_topics": [],
                "scanner_differs": True,
                "new_topic_proposal": None,
            },
            "apply_recommendation": {"recommended_research_depth": "basic"},
        }
        result = generate_source_digest(
            topic_root=self.topic,
            raw_article_path=raw,
            candidate_id="cand_digest",
            source_fingerprint="fp123",
            selected_topic="ai-tokenization",
            recommended_topic="ai-devtools-economics",
            accepted_decision_digest={
                "accepted_at": "2026-05-09T10:00:00+08:00",
                "digest_path": "/tmp/pre_digest/cand.decision_digest.json",
                "decision_digest": decision_digest,
            },
            mode="deterministic",
        )
        digest = result["digest"]
        self.assertEqual(digest["generator"], "decision_digest_v1_derived_source_digest")
        self.assertIn("derived_from_decision_digest_v1", digest["quality_flags"])
        self.assertEqual(digest["main_claim"], "已采纳主张会进入 source digest。")
        self.assertIn("已采纳机制解释", digest["mechanism"])
        self.assertEqual(digest["derived_from_decision_digest"]["digest_path"], "/tmp/pre_digest/cand.decision_digest.json")
        self.assertEqual(digest["derived_from_decision_digest"]["rationale"], "已采纳推荐理由。")

    def test_apply_digest_failure_keeps_compile_fallback(self) -> None:
        source = self.write_source("fallback.md")
        markdown = source.read_text(encoding="utf-8")
        decision = {
            "candidate_id": "cand_fallback",
            "decision_id": "dec_fallback",
            "title": "为什么 token 成本会改变 AI 编程工具",
            "source_file_path": str(source),
            "source_url": "https://example.com/token",
            "content_hash": f"sha256:{hashlib.sha256(markdown.encode('utf-8')).hexdigest()}",
            "decision_status": "accepted",
            "gate1_destination": "llm_wiki_only",
            "topic_id": "ai-tokenization",
            "topic_name": "ai-tokenization",
            "decided_by": "test",
        }
        ctx = ProcessorContext(intake_dir=self.intake, wiki_hub=self.wiki, clippings_root=self.clippings, execute=True)
        os.environ["SOURCE_DIGEST_FORCE_FAIL"] = "1"
        try:
            result = apply_decision(decision, ctx)
        finally:
            os.environ.pop("SOURCE_DIGEST_FORCE_FAIL", None)
        self.assertEqual(result["wiki"]["digest"]["status"], "digest_failed")
        self.assertEqual(result["wiki"]["ingest"]["compile_status"], "compiled")
        raw_path = Path(result["wiki"]["ingest"]["path"])
        raw_text = raw_path.read_text(encoding="utf-8")
        self.assertIn("digest_status: digest_failed", raw_text)
        compiled_page = Path(result["wiki"]["ingest"]["compiled_page_path"]).read_text(encoding="utf-8")
        self.assertIn("deterministic_fallback", compiled_page)

    def test_apply_uses_accepted_decision_digest_only_when_payload_contains_it(self) -> None:
        source = self.write_source("accepted.md")
        markdown = source.read_text(encoding="utf-8")
        decision_digest = {
            "digest_version": "decision_digest_v1",
            "candidate_id": "cand_accepted",
            "source_fingerprint": "sha256:decision",
            "source_title": "为什么 token 成本会改变 AI 编程工具",
            "source_language": "zh",
            "source_only": True,
            "web_research_used": False,
            "wiki_mutation": False,
            "scanner_signal": {"primary_topic": "ai-tokenization", "guessed_topics": []},
            "article_understanding": {
                "article_type": "technical_analysis",
                "summary": "Apply 采纳摘要。",
                "main_claim": "Apply 采纳主张。",
                "key_points": ["Apply 采纳关键点"],
                "important_entities": ["Claude Code"],
                "mechanisms": ["Apply 采纳机制"],
                "evidence_in_source": ["Apply 采纳证据"],
                "uncertainties": ["Apply 采纳待验证项"],
            },
            "topic_recommendation": {
                "scanner_topic_id": "ai-tokenization",
                "recommended_topic_id": "ai-tokenization",
                "recommended_topic_label": "AI 分词与计费成本",
                "confidence": "high",
                "fit_status": "strong_fit",
                "rationale": "Apply 采纳理由。",
                "alternative_topics": [],
                "scanner_differs": False,
                "new_topic_proposal": None,
            },
            "apply_recommendation": {"recommended_research_depth": "basic"},
        }
        decision = {
            "candidate_id": "cand_accepted",
            "decision_id": "dec_accepted",
            "title": "为什么 token 成本会改变 AI 编程工具",
            "source_file_path": str(source),
            "source_url": "https://example.com/token",
            "content_hash": f"sha256:{hashlib.sha256(markdown.encode('utf-8')).hexdigest()}",
            "decision_status": "accepted",
            "gate1_destination": "llm_wiki_only",
            "topic_id": "ai-tokenization",
            "topic_name": "ai-tokenization",
            "decided_by": "test",
            "accepted_decision_digest": {
                "accepted_at": "2026-05-09T10:00:00+08:00",
                "digest_path": "/tmp/pre_digest/cand_accepted.decision_digest.json",
                "decision_digest": decision_digest,
            },
        }
        ctx = ProcessorContext(intake_dir=self.intake, wiki_hub=self.wiki, clippings_root=self.clippings, execute=True)
        result = apply_decision(decision, ctx)
        digest_path = Path(result["wiki"]["digest"]["json_path"])
        digest = json.loads(digest_path.read_text(encoding="utf-8"))
        self.assertEqual(digest["generator"], "decision_digest_v1_derived_source_digest")
        self.assertEqual(digest["main_claim"], "Apply 采纳主张。")
        self.assertEqual(result["wiki"]["digest"]["derived_from_decision_digest"]["digest_path"], "/tmp/pre_digest/cand_accepted.decision_digest.json")
        raw_text = Path(result["wiki"]["ingest"]["path"]).read_text(encoding="utf-8")
        self.assertIn("derived_from_decision_digest_v1:", raw_text)


if __name__ == "__main__":
    unittest.main()
