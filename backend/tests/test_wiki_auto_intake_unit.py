#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "wiki_intake"))

import auto_intake_job_store as store  # noqa: E402
from auto_intake_enqueue import enqueue_from_manifest  # noqa: E402
from auto_intake_fresh_runner import process_one  # noqa: E402
from topic_candidate_selector import write_topic_candidate_context  # noqa: E402
from validate_auto_intake_output import validate_paths  # noqa: E402


class Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class AutoIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="auto-intake-test-"))
        self.clippings = self.tmp / "clippings"
        self.intake = self.tmp / "intake"
        self.wiki = self.tmp / "wiki"
        self.clippings.mkdir(parents=True)
        self.intake.mkdir(parents=True)
        self.wiki.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def write_md(self, name: str, title: str, body: str, source_url: str = "https://example.com/article") -> Path:
        path = self.clippings / name
        path.write_text(
            f"""---
title: "{title}"
source_url: "{source_url}"
workflow: clippings_archive
---

# {title}

{body}
""",
            encoding="utf-8",
        )
        return path

    def manifest_record(self, path: Path, source_id: str, topic: str = "agent-harness", duplicate_status: str = "none") -> dict:
        text = path.read_text(encoding="utf-8")
        return {
            "schema_version": "manifest.v1",
            "source_id": source_id,
            "title": path.stem,
            "source_file_path": str(path),
            "source_relative_path": path.name,
            "source_url": "https://example.com/article",
            "content_hash": f"sha256:{sha256_text(text)}",
            "image_ref_count": 0,
            "existing_image_ref_count": 0,
            "guessed_topics": [{"topic_id": topic, "score": 3}] if topic else [],
            "duplicate_status": duplicate_status,
            "duplicate_candidate_ids": [],
        }

    def write_manifest(self, records: list[dict]) -> None:
        with (self.intake / "manifest.jsonl").open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def runner_args(self) -> Args:
        return Args(
            intake_dir=self.intake,
            wiki_hub=self.wiki,
            clippings_root=self.clippings,
            adapter="deterministic",
            timeout_seconds=60,
            codex_bin="/opt/homebrew/bin/codex",
            model="",
        )

    def test_enqueue_is_idempotent_and_queues_duplicate_risk(self) -> None:
        article = self.write_md("agent.md", "Hermes Agent Skills", "Hermes 使用 skill_manage 和 skill_view 管理技能。")
        duplicate = self.write_md("dup.md", "Duplicate", "重复内容")
        self.write_manifest([
            self.manifest_record(article, "src_agent"),
            self.manifest_record(duplicate, "src_dup", duplicate_status="same_url_duplicate"),
        ])
        first = enqueue_from_manifest(self.intake)
        second = enqueue_from_manifest(self.intake)
        self.assertEqual(first["created_count"], 2)
        self.assertEqual(first["skipped_count"], 0)
        self.assertEqual(second["created_count"], 0)
        jobs = store.load_jobs(self.intake)
        self.assertEqual(len([job for job in jobs if job["status"] == "queued"]), 2)
        self.assertEqual(len([job for job in jobs if job["status"] == "skipped_duplicate"]), 0)
        duplicate_jobs = [job for job in jobs if job["source_id"] == "src_dup"]
        self.assertEqual(duplicate_jobs[0]["reason"], "duplicate_risk:same_url_duplicate")

    def test_enqueue_and_claim_skip_already_auto_processed_sources(self) -> None:
        article = self.write_md("agent.md", "Hermes Agent Skills", "Hermes 使用 skill_manage 和 skill_view 管理技能。")
        record = self.manifest_record(article, "src_agent")
        self.write_manifest([record])
        (self.intake / "auto_processed_manifest.jsonl").write_text(
            json.dumps(
                {
                    "schema_version": "auto-processed-source.v1",
                    "source_key": store.source_key(record),
                    "source_id": "src_agent",
                    "topic_id": "agent-harness",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        first = enqueue_from_manifest(self.intake)

        self.assertEqual(first["created_count"], 0)
        self.assertEqual(first["skipped"][0]["reason"], "already_active_or_processed")
        queued = store.create_job(self.intake, record, status="queued")
        claimed = store.claim_next(self.intake, "test-runner")
        jobs = store.load_jobs(self.intake)
        self.assertIsNone(claimed)
        skipped = [job for job in jobs if job["job_id"] == queued["job_id"] and job["status"] == "skipped_duplicate"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["status_note"], "already_auto_processed")

    def test_deterministic_runner_processes_one_job_per_invocation_and_completes_with_wiki_evidence(self) -> None:
        first = self.write_md("one.md", "Hermes Agent Skills", "Hermes Agent 通过 Skills 实现经验复用。")
        second = self.write_md("two.md", "Coordination Agent", "Agent coordination 需要工具编排和审计。")
        first_hash_before = hashlib.sha256(first.read_bytes()).hexdigest()
        self.write_manifest([
            self.manifest_record(first, "src_one"),
            self.manifest_record(second, "src_two"),
        ])
        enqueue_from_manifest(self.intake)
        result_one = process_one(self.runner_args())
        jobs_after_one = store.load_jobs(self.intake)
        self.assertEqual(result_one["status"], "completed")
        self.assertEqual(len([job for job in jobs_after_one if job["status"] == "completed"]), 1)
        self.assertEqual(len([job for job in jobs_after_one if job["status"] == "queued"]), 1)
        result_two = process_one(self.runner_args())
        self.assertEqual(result_two["status"], "completed")
        completed = [job for job in store.load_jobs(self.intake) if job["status"] == "completed"]
        self.assertEqual(len(completed), 2)
        self.assertNotEqual(completed[0]["run_dir"], completed[1]["run_dir"])
        for job in completed:
            self.assertFalse(job["session_strategy"]["reuse_current_conversation"])
            self.assertEqual(job["session_strategy"]["codex"], "fresh_codex_exec_per_job_required")
            artifacts = job["artifacts"]
            self.assertTrue(Path(artifacts["validation_path"]).exists())
            self.assertTrue(Path(artifacts["apply_result_path"]).exists())
            self.assertTrue((Path(job["run_dir"]) / "audit" / "transitions.jsonl").exists())
            execution_record = Path(job["run_dir"]) / "audit" / "deterministic_execution_record.json"
            self.assertTrue(execution_record.exists())
            execution = json.loads(execution_record.read_text(encoding="utf-8"))
            self.assertTrue(execution["fresh_session_required"])
            self.assertFalse(execution["reuse_current_conversation"])
        self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(), first_hash_before)
        processed = read_jsonl(self.intake / "auto_processed_manifest.jsonl")
        self.assertEqual(len(processed), 2)
        self.assertTrue(all(Path(item["raw_article_path"]).exists() for item in processed))
        self.assertTrue(all(Path(item["verified_digest_json_path"]).exists() for item in processed))
        self.assertTrue((self.wiki / "topics" / "agent-harness" / "compile_runs.jsonl").exists())

    def test_low_confidence_topic_uses_fallback_inbox_without_human_review(self) -> None:
        article = self.write_md("unknown.md", "无明确主题", "这是一篇没有明显主题关键词的短文。")
        self.write_manifest([self.manifest_record(article, "src_unknown", topic="")])
        enqueue_from_manifest(self.intake)
        result = process_one(self.runner_args())
        self.assertEqual(result["status"], "completed")
        completed = [job for job in store.load_jobs(self.intake) if job["status"] == "completed"]
        self.assertEqual(len(completed), 1)
        validation = json.loads(Path(completed[0]["artifacts"]["validation_path"]).read_text(encoding="utf-8"))
        self.assertEqual(validation["resolved_topic_id"], "intake-inbox")
        self.assertEqual(validation["route_mode"], "fallback_topic")
        self.assertTrue((self.wiki / "topics" / "intake-inbox" / "topic_profile.json").exists())
        self.assertTrue((self.intake / "auto_processed_manifest.jsonl").exists())

    def test_validator_resolves_needs_review_to_new_topic_suggestion(self) -> None:
        article = self.write_md("markets.md", "港股投资", "港股、南下资金、外资和资产配置。")
        record = self.manifest_record(article, "src_markets", topic="")
        job = store.create_job(self.intake, record)
        run_dir = Path(job["run_dir"])
        output = run_dir / "output"
        output.mkdir(parents=True)
        result = {
            "schema_version": "auto_intake_result_v1",
            "job_id": job["job_id"],
            "status": "complete",
            "input": {"source_id": record["source_id"], "content_hash": record["content_hash"], "title": "港股投资", "images_provided_count": 0},
            "topic_routing": {
                "recommended_topic": "needs_review",
                "recommended_topic_label": "港股/投资市场分析",
                "confidence": "low",
                "confidence_score": 0.18,
                "needs_human_review": True,
                "new_topic_suggestion": {"topic_id": "markets-investing", "description": "资本市场与投资策略"},
            },
            "source_digest": {"one_sentence_summary": "港股投资观点", "main_claim": "港股是离岸市场", "key_points": ["南下资金"], "core_concepts": ["港股"]},
            "verification": {"web_verification_performed": True, "verified_facts": [], "contradicted_or_stale_claims": [], "uncertain_claims": []},
            "safe_wiki": {"safe_summary": "可作为港股市场结构材料。", "do_not_state_as_fact": []},
            "follow_up": {"formal_research_recommended": True},
        }
        result_path = output / "auto_intake_result.json"
        claim_path = output / "claim_ledger.jsonl"
        result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        claim_path.write_text(json.dumps({"claim_id": "c1", "claim_text": "x", "verification_status": "source_only", "safe_wiki_wording": "x"}, ensure_ascii=False) + "\n", encoding="utf-8")
        validation = validate_paths(result_path, claim_path, job_path=Path(job["job_path"]))
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["status"], "valid")
        self.assertEqual(validation["resolved_topic_id"], "markets-investing")
        self.assertEqual(validation["route_mode"], "auto_created_topic")
        self.assertIn("used_new_topic_suggestion", validation["warnings"])

    def test_candidate_selector_uses_full_catalog_and_prior_articles(self) -> None:
        article = self.write_md(
            "aliyun-data-ai.md",
            "AI 时代下阿里云大数据演进与发展",
            "阿里云大数据平台围绕 Data+AI、MaxCompute、DataWorks、PAI、湖仓和 ChatBI 演进。",
        )
        record = self.manifest_record(article, "src_aliyun", topic="agent-harness")
        self.write_manifest([record])
        for topic_id, display_name, keywords in [
            ("agent-harness", "Agent Harness", ["agent", "harness"]),
            ("knowledge-workspace", "知识工作台", ["knowledge", "nl2sql"]),
            ("cloud-data-ai-platform", "Cloud Data and AI Platform", ["cloud", "data", "ai", "platform", "dataworks"]),
        ]:
            topic_dir = self.wiki / "topics" / topic_id
            topic_dir.mkdir(parents=True)
            (topic_dir / "topic_profile.json").write_text(
                json.dumps({"topic_id": topic_id, "display_name": display_name, "topic_keywords": keywords}, ensure_ascii=False),
                encoding="utf-8",
            )
        (self.intake / "auto_processed_manifest.jsonl").write_text(
            json.dumps(
                {
                    "candidate_id": "src_prior",
                    "source_id": "src_prior",
                    "source_md": str(article),
                    "topic_id": "cloud-data-ai-platform",
                    "processed_at": "2026-05-14T10:25:52+08:00",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        context_path = self.tmp / "topic_candidates.json"

        context = write_topic_candidate_context(
            wiki_hub=self.wiki,
            intake_dir=self.intake,
            job=record,
            article_path=article,
            output_path=context_path,
        )

        ids = [item["topic_id"] for item in context["visible_candidate_topics"]]
        self.assertIn("cloud-data-ai-platform", ids)
        self.assertIn("knowledge-workspace", [item["topic_id"] for item in context["topic_catalog"]])
        self.assertLessEqual(len(context["visible_candidate_topics"]), 12)
        self.assertTrue(any(item.get("reasons") for item in context["visible_candidate_topics"]))
        self.assertGreater(
            ids.index("cloud-data-ai-platform"),
            -1,
        )

    def test_validator_reroutes_medium_recommendation_when_new_topic_matches_existing(self) -> None:
        article = self.write_md("aliyun.md", "AI 时代下阿里云大数据演进与发展", "Data+AI 数据平台。")
        record = self.manifest_record(article, "src_aliyun", topic="agent-harness")
        job = store.create_job(self.intake, record)
        run_dir = Path(job["run_dir"])
        output = run_dir / "output"
        output.mkdir(parents=True)
        result = {
            "schema_version": "auto_intake_result_v1",
            "job_id": job["job_id"],
            "status": "complete",
            "input": {"source_id": record["source_id"], "content_hash": record["content_hash"], "title": record["title"], "images_provided_count": 0},
            "topic_routing": {
                "recommended_topic": "knowledge-workspace",
                "recommended_topic_label": "Knowledge Workspace",
                "confidence": "medium",
                "confidence_score": 0.72,
                "needs_human_review": False,
                "new_topic_suggestion": {"topic_id": "data-ai-platforms", "label": "Data+AI Platforms", "description": "Data+AI data platform and lakehouse"},
            },
            "source_digest": {"one_sentence_summary": "Data+AI 平台演进", "main_claim": "数据平台演进", "key_points": ["Data+AI"], "core_concepts": ["Data+AI"]},
            "verification": {"web_verification_performed": False, "verified_facts": [], "contradicted_or_stale_claims": [], "uncertain_claims": []},
            "safe_wiki": {"safe_summary": "可作为 Data+AI 平台材料。", "do_not_state_as_fact": []},
            "follow_up": {"formal_research_recommended": False},
        }
        result_path = output / "auto_intake_result.json"
        claim_path = output / "claim_ledger.jsonl"
        candidates_path = output / "topic_candidates.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        claim_path.write_text(json.dumps({"claim_id": "c1", "claim_text": "x", "verification_status": "source_only", "safe_wiki_wording": "x"}, ensure_ascii=False) + "\n", encoding="utf-8")
        candidates_path.write_text(
            json.dumps(
                {
                    "visible_candidate_topics": [
                        {"topic_id": "knowledge-workspace", "label": "Knowledge Workspace"},
                        {"topic_id": "cloud-data-ai-platform", "label": "Cloud Data and AI Platform"},
                    ],
                    "topic_catalog": [
                        {"topic_id": "knowledge-workspace", "label": "Knowledge Workspace", "keywords": ["nl2sql", "knowledge"]},
                        {"topic_id": "cloud-data-ai-platform", "label": "Cloud Data and AI Platform", "aliases": ["Data+AI Platforms"], "keywords": ["data", "ai", "platform"]},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        validation = validate_paths(result_path, claim_path, allowed_topics_path=candidates_path, job_path=Path(job["job_path"]))

        self.assertTrue(validation["ok"])
        self.assertEqual(validation["resolved_topic_id"], "cloud-data-ai-platform")
        self.assertEqual(validation["route_mode"], "auto_rerouted_existing_from_new_suggestion")
        self.assertEqual(validation["matched_existing_topic_id"], "cloud-data-ai-platform")
        self.assertIn("new_topic_suggestion_matches_existing_topic", validation["reason_codes"])

    def test_validator_keeps_high_confidence_recommended_topic(self) -> None:
        article = self.write_md("workspace.md", "知识工作台", "NL2SQL semantic layer and Data Agent.")
        record = self.manifest_record(article, "src_workspace", topic="knowledge-workspace")
        job = store.create_job(self.intake, record)
        run_dir = Path(job["run_dir"])
        output = run_dir / "output"
        output.mkdir(parents=True)
        result = {
            "schema_version": "auto_intake_result_v1",
            "job_id": job["job_id"],
            "status": "complete",
            "input": {"source_id": record["source_id"], "content_hash": record["content_hash"], "title": record["title"], "images_provided_count": 0},
            "topic_routing": {
                "recommended_topic": "knowledge-workspace",
                "recommended_topic_label": "Knowledge Workspace",
                "confidence": "high",
                "confidence_score": 0.91,
                "needs_human_review": False,
                "new_topic_suggestion": {"topic_id": "data-ai-platforms", "label": "Data+AI Platforms"},
            },
            "source_digest": {"one_sentence_summary": "知识工作台材料", "main_claim": "工作台", "key_points": ["NL2SQL"], "core_concepts": ["NL2SQL"]},
            "verification": {"web_verification_performed": False, "verified_facts": [], "contradicted_or_stale_claims": [], "uncertain_claims": []},
            "safe_wiki": {"safe_summary": "可作为知识工作台材料。", "do_not_state_as_fact": []},
            "follow_up": {"formal_research_recommended": False},
        }
        result_path = output / "auto_intake_result.json"
        claim_path = output / "claim_ledger.jsonl"
        candidates_path = output / "topic_candidates.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        claim_path.write_text(json.dumps({"claim_id": "c1", "claim_text": "x", "verification_status": "source_only", "safe_wiki_wording": "x"}, ensure_ascii=False) + "\n", encoding="utf-8")
        candidates_path.write_text(
            json.dumps(
                {
                    "visible_candidate_topics": [
                        {"topic_id": "knowledge-workspace", "label": "Knowledge Workspace"},
                        {"topic_id": "cloud-data-ai-platform", "label": "Cloud Data and AI Platform"},
                    ],
                    "topic_catalog": [
                        {"topic_id": "knowledge-workspace", "label": "Knowledge Workspace", "keywords": ["nl2sql", "knowledge"]},
                        {"topic_id": "cloud-data-ai-platform", "label": "Cloud Data and AI Platform", "aliases": ["Data+AI Platforms"], "keywords": ["data", "ai", "platform"]},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        validation = validate_paths(result_path, claim_path, allowed_topics_path=candidates_path, job_path=Path(job["job_path"]))

        self.assertTrue(validation["ok"])
        self.assertEqual(validation["resolved_topic_id"], "knowledge-workspace")
        self.assertEqual(validation["route_mode"], "recommended_topic")
        self.assertEqual(validation["resolver_decision_rule"], "accepted_recommended_topic")

    def test_stuck_recovery_marks_stale_running_job(self) -> None:
        article = self.write_md("stuck.md", "Hermes Agent Skills", "Agent runtime")
        self.write_manifest([self.manifest_record(article, "src_stuck")])
        enqueue_from_manifest(self.intake)
        job = store.claim_next(self.intake, "test", 999999)
        self.assertIsNotNone(job)
        assert job is not None
        stale = (datetime.now(timezone.utc).astimezone() - timedelta(hours=2)).isoformat(timespec="seconds")
        job["heartbeat_at"] = stale
        store.heartbeat(self.intake, job)
        # Rewrite the stale heartbeat after heartbeat() updates it to now.
        found = store.find_job_by_id(self.intake, job["job_id"])
        assert found is not None
        loaded, path = found
        loaded["heartbeat_at"] = stale
        store.write_json_atomic(path, loaded)
        recovered = store.recover_stuck(self.intake, stale_seconds=60)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["status"], "stuck")
        self.assertFalse((self.intake / "auto_processed_manifest.jsonl").exists())

    def test_validator_rejects_source_mismatch_and_image_claim_without_images(self) -> None:
        article = self.write_md("bad.md", "Hermes Agent Skills", "Agent runtime")
        record = self.manifest_record(article, "src_bad")
        job = store.create_job(self.intake, record)
        run_dir = Path(job["run_dir"])
        output = run_dir / "output"
        output.mkdir(parents=True)
        result = {
            "schema_version": "auto_intake_result_v1",
            "job_id": job["job_id"],
            "status": "complete",
            "input": {"source_id": "wrong", "content_hash": record["content_hash"], "title": "bad", "images_provided_count": 0},
            "topic_routing": {"recommended_topic": "agent-harness", "confidence": "high", "confidence_score": 0.9, "needs_human_review": False},
            "source_digest": {"one_sentence_summary": "图中显示系统架构", "main_claim": "Agent runtime", "key_points": ["Agent runtime"], "core_concepts": ["agent"]},
            "verification": {"web_verification_performed": False, "verified_facts": [], "contradicted_or_stale_claims": [], "uncertain_claims": []},
            "safe_wiki": {"safe_summary": "图中显示系统架构", "do_not_state_as_fact": []},
            "follow_up": {"formal_research_recommended": False},
        }
        result_path = output / "auto_intake_result.json"
        claim_path = output / "claim_ledger.jsonl"
        result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        claim_path.write_text(json.dumps({"claim_id": "c1", "claim_text": "x", "verification_status": "source_only", "safe_wiki_wording": "x"}, ensure_ascii=False) + "\n", encoding="utf-8")
        validation = validate_paths(result_path, claim_path, job_path=Path(job["job_path"]))
        self.assertFalse(validation["ok"])
        self.assertIn("input_source_id_mismatch", validation["errors"])
        self.assertIn("image_evidence_claim_without_provided_images", validation["errors"])


if __name__ == "__main__":
    unittest.main()
