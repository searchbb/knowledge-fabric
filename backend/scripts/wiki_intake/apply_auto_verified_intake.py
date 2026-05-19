#!/usr/bin/env python3
"""Apply a validated auto-intake result into the local topic wiki."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import auto_intake_job_store as store
from apply_intake_decision import ProcessorContext, apply_decision, safe_filename
from incremental_compile_topic import incremental_compile, update_frontmatter
from validate_auto_intake_output import validate_paths


DEFAULT_INTAKE = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake")
DEFAULT_WIKI = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub")
DEFAULT_CLIPPINGS = Path("/Users/mac/Downloads/OB笔记/Clippings")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_topic_root(wiki_hub: Path, topic_id: str, display_name: str = "", creation_context: dict[str, Any] | None = None) -> Path:
    if not topic_id or topic_id == "needs_review":
        raise ValueError("valid_topic_id_required")
    topic_root = wiki_hub / "topics" / topic_id
    (topic_root / "raw" / "articles").mkdir(parents=True, exist_ok=True)
    (topic_root / "raw" / "clippings").mkdir(parents=True, exist_ok=True)
    (topic_root / "wiki").mkdir(parents=True, exist_ok=True)
    profile_path = topic_root / "topic_profile.json"
    if not profile_path.exists():
        profile = {
            "schema_version": "topic-profile.v1",
            "topic_id": topic_id,
            "display_name": display_name or topic_id,
            "created_at": store.now_iso(),
            "created_by": "auto_intake_pipeline",
        }
        if creation_context:
            profile.update(creation_context)
        write_json(profile_path, profile)
    return topic_root


def routing_decision_from_validation(result: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    topic = result.get("topic_routing") or {}
    return {
        "schema_version": "auto-intake-routing-decision.v1",
        "original_recommended_topic": topic.get("recommended_topic", ""),
        "original_recommended_topic_label": topic.get("recommended_topic_label", ""),
        "original_confidence": topic.get("confidence", ""),
        "original_confidence_score": topic.get("confidence_score"),
        "original_needs_human_review": bool(topic.get("needs_human_review")),
        "new_topic_suggestion": topic.get("new_topic_suggestion"),
        "resolved_topic_id": validation.get("resolved_topic_id", ""),
        "resolved_topic_label": validation.get("resolved_topic_label", ""),
        "route_mode": validation.get("route_mode", ""),
        "resolver_decision_rule": validation.get("resolver_decision_rule", ""),
        "matched_existing_topic_id": validation.get("matched_existing_topic_id", ""),
        "override_reason": validation.get("override_reason", ""),
        "reason_codes": validation.get("reason_codes", []),
        "warnings": validation.get("warnings", []),
        "resolved_by": validation.get("resolved_by", "auto_intake_topic_resolver_v1"),
    }


def decision_digest_from_result(job: dict[str, Any], result: dict[str, Any], result_path: Path) -> dict[str, Any]:
    topic = result.get("topic_routing") or {}
    source_digest = result.get("source_digest") or {}
    verification = result.get("verification") or {}
    safe_wiki = result.get("safe_wiki") or {}
    follow_up = result.get("follow_up") or {}
    title = ((result.get("input") or {}).get("title") or job.get("title") or "").strip()
    recommended_topic = str(topic.get("recommended_topic") or "")
    return {
        "accepted_at": store.now_iso(),
        "digest_path": str(result_path),
        "decision_digest": {
            "digest_version": "decision_digest_v1",
            "candidate_id": job.get("job_id", ""),
            "source_fingerprint": job.get("content_hash", ""),
            "source_title": title,
            "source_language": "zh",
            "source_only": False,
            "web_research_used": bool((verification or {}).get("web_verification_performed")),
            "wiki_mutation": False,
            "scanner_signal": {
                "primary_topic": ((job.get("guessed_topics") or [{}])[0] or {}).get("topic_id", ""),
                "guessed_topics": job.get("guessed_topics", []),
            },
            "article_understanding": {
                "article_type": "auto_intake_verified_digest",
                "summary": source_digest.get("one_sentence_summary") or safe_wiki.get("safe_summary") or "",
                "main_claim": source_digest.get("main_claim") or "",
                "key_points": source_digest.get("key_points") or [],
                "important_entities": source_digest.get("core_concepts") or [],
                "mechanisms": [source_digest.get("mechanism_summary") or ""] if source_digest.get("mechanism_summary") else [],
                "evidence_in_source": source_digest.get("source_limitations") or [],
                "uncertainties": (verification.get("uncertain_claims") or []) + (verification.get("not_verified_due_to_limits") or []),
            },
            "topic_recommendation": {
                "scanner_topic_id": ((job.get("guessed_topics") or [{}])[0] or {}).get("topic_id", ""),
                "recommended_topic_id": recommended_topic,
                "recommended_topic_label": topic.get("recommended_topic_label") or recommended_topic,
                "confidence": topic.get("confidence") or "",
                "fit_status": "strong_fit" if topic.get("confidence") == "high" else "medium_fit",
                "rationale": topic.get("rationale") or "",
                "alternative_topics": topic.get("secondary_topics") or [],
                "scanner_differs": recommended_topic != (((job.get("guessed_topics") or [{}])[0] or {}).get("topic_id", "")),
                "new_topic_proposal": topic.get("new_topic_suggestion"),
            },
            "apply_recommendation": {
                "recommended_research_depth": "basic" if follow_up.get("formal_research_recommended") else "none",
                "safe_wiki_summary": safe_wiki.get("safe_summary", ""),
                "do_not_state_as_fact": safe_wiki.get("do_not_state_as_fact", []),
            },
        },
    }


def write_verified_artifacts(
    topic_root: Path,
    job: dict[str, Any],
    result: dict[str, Any],
    result_path: Path,
    claim_ledger_path: Path,
    sources_path: Path,
    safe_article_path: Path | None,
    raw_article_path: Path,
) -> dict[str, str]:
    source_id = raw_article_path.stem
    verified_dir = topic_root / "digests" / "verified_digest"
    ledger_dir = topic_root / "digests" / "claim_ledger"
    verified_json = verified_dir / f"{source_id}.json"
    verified_md = verified_dir / f"{source_id}.md"
    ledger_target = ledger_dir / f"{source_id}.jsonl"
    sources_target = ledger_dir / f"{source_id}.sources.json"
    verified_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(claim_ledger_path, ledger_target)
    if sources_path.exists():
        shutil.copy2(sources_path, sources_target)
    safe_summary = (result.get("safe_wiki") or {}).get("safe_summary", "")
    verified_payload = {
        "digest_version": "verified_digest_v1",
        "job_id": job.get("job_id"),
        "source_id": source_id,
        "original_source_url": job.get("source_url", ""),
        "topic": topic_root.name,
        "source_summary": (result.get("source_digest") or {}).get("one_sentence_summary", ""),
        "verified_summary": safe_summary,
        "core_concepts": (result.get("source_digest") or {}).get("core_concepts", []),
        "claim_ledger_path": str(ledger_target),
        "sources_path": str(sources_target) if sources_path.exists() else "",
        "safe_wiki_wording": safe_summary,
        "research_gaps": (result.get("verification") or {}).get("uncertain_claims", []),
        "recommended_next_action": "formal_research" if ((result.get("follow_up") or {}).get("formal_research_recommended")) else "none",
        "raw_auto_intake_result_path": str(result_path),
        "raw_article_path": str(raw_article_path),
        "created_at": store.now_iso(),
    }
    write_json(verified_json, verified_payload)
    verified_md.write_text(
        "\n".join(
            [
                f"# Verified Digest: {job.get('title', source_id)}",
                "",
                f"- Topic: `{topic_root.name}`",
                f"- Job: `{job.get('job_id')}`",
                f"- Raw article: `{raw_article_path}`",
                f"- Claim ledger: `{ledger_target}`",
                "",
                "## 安全表述",
                "",
                safe_summary or "-",
                "",
                "## 后续 Research 缺口",
                "",
                "\n".join(f"- {item}" for item in verified_payload["research_gaps"]) or "-",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if safe_article_path and safe_article_path.exists():
        shutil.copy2(safe_article_path, ledger_dir / f"{source_id}.safe_wiki_article.md")
    return {
        "verified_digest_json_path": str(verified_json),
        "verified_digest_md_path": str(verified_md),
        "claim_ledger_path": str(ledger_target),
        "sources_path": str(sources_target) if sources_path.exists() else "",
    }


def apply_auto_verified_intake(
    intake_dir: Path,
    wiki_hub: Path,
    clippings_root: Path,
    job: dict[str, Any],
    result_path: Path,
    claim_ledger_path: Path,
    sources_path: Path,
    safe_article_path: Path | None = None,
    allowed_topics_path: Path | None = None,
) -> dict[str, Any]:
    intake_dir = intake_dir.expanduser().resolve()
    wiki_hub = wiki_hub.expanduser().resolve()
    clippings_root = clippings_root.expanduser().resolve()
    job_validation_path = Path(str(job.get("job_path") or ""))
    validation = validate_paths(
        result_path,
        claim_ledger_path,
        allowed_topics_path=allowed_topics_path,
        job_path=job_validation_path if job_validation_path.exists() else None,
    )
    if not validation.get("ok"):
        raise ValueError("auto_intake_output_invalid: " + "; ".join(validation.get("errors") or []))
    result = read_json(result_path)
    topic = result.get("topic_routing") or {}
    topic_id = str(validation.get("resolved_topic_id") or topic.get("recommended_topic") or "")
    topic_label = str(validation.get("resolved_topic_label") or topic.get("recommended_topic_label") or topic_id)
    routing_decision = routing_decision_from_validation(result, validation)
    topic_root = ensure_topic_root(
        wiki_hub,
        topic_id,
        topic_label,
        {
            "status": "provisional" if validation.get("route_mode") in {"auto_created_topic", "fallback_topic"} else "active",
            "created_reason": validation.get("route_mode") or "auto_intake",
            "first_source_id": job.get("source_id", ""),
            "first_job_id": job.get("job_id", ""),
            "routing_decision": routing_decision,
        },
    )
    source_path = Path(str(job.get("source_file_path") or "")).expanduser().resolve()
    content_hash = str(job.get("content_hash") or "")
    if not content_hash.startswith("sha256:") and source_path.exists():
        content_hash = f"sha256:{sha256_file(source_path)}"
    decision = {
        "candidate_id": job.get("job_id", ""),
        "decision_id": f"autodec_{job.get('job_id', '')}",
        "title": ((result.get("input") or {}).get("title") or job.get("title") or source_path.stem),
        "source_file_path": str(source_path),
        "source_url": job.get("source_url", ""),
        "content_hash": content_hash,
        "decision_status": "accepted",
        "gate1_destination": "llm_wiki_only",
        "gate2_promote_to_kfc": False,
        "topic_id": topic_id,
        "topic_name": topic_label,
        "topic_display_name": topic_label,
        "recommended_topic": topic_id,
        "decided_by": "auto_intake_pipeline",
        "strategy_mode": "ingest_only",
        "automation": {"auto_initial_compile": True, "auto_basic_research": False, "auto_compile_research_if_pass": False},
        "accepted_decision_digest": decision_digest_from_result(job, result, result_path),
    }
    ctx = ProcessorContext(intake_dir=intake_dir, wiki_hub=wiki_hub, clippings_root=clippings_root, archive_processed=False, execute=True)
    apply_result = apply_decision(decision, ctx)
    wiki = apply_result.get("wiki") or {}
    ingest = wiki.get("ingest") or {}
    compile_status = ingest.get("compile_status")
    if compile_status != "compiled":
        raise RuntimeError(f"auto_intake_compile_failed:{ingest.get('compile_error') or compile_status}")
    raw_article_path = Path(ingest.get("path") or "").expanduser().resolve()
    verified_paths = write_verified_artifacts(topic_root, job, result, result_path, claim_ledger_path, sources_path, safe_article_path, raw_article_path)
    verified_json_path = Path(verified_paths.get("verified_digest_json_path", ""))
    if verified_json_path.exists():
        verified_payload = read_json(verified_json_path)
        verified_payload["routing_decision"] = routing_decision
        write_json(verified_json_path, verified_payload)
    raw_markdown = raw_article_path.read_text(encoding="utf-8", errors="replace")
    raw_article_path.write_text(
        update_frontmatter(
            raw_markdown,
            {
                "digest_status": "generated",
                "digest_version": "verified_digest_v1",
                "digest_json_path": verified_paths.get("verified_digest_json_path", ""),
                "digest_markdown_path": verified_paths.get("verified_digest_md_path", ""),
                "digest_error": "",
                "auto_intake_route_mode": validation.get("route_mode", ""),
                "auto_intake_resolved_by": validation.get("resolved_by", ""),
            },
        ),
        encoding="utf-8",
    )
    verified_compile = incremental_compile(
        topic_root=topic_root,
        source_paths=[raw_article_path],
        trigger="auto_intake_verified_digest",
        candidate_id=str(job.get("job_id") or ""),
        intake_dir=intake_dir,
    )
    verified_source = (verified_compile.get("source_results") or [{}])[0]
    if verified_source.get("digest_source") != "verified_digest_v1":
        raise RuntimeError(f"auto_intake_verified_compile_not_llm_backed:{verified_source.get('digest_source')}")
    processed = {
        "schema_version": "auto-processed-source.v1",
        "processed_at": store.now_iso(),
        "job_id": job.get("job_id"),
        "source_key": job.get("source_key"),
        "source_id": job.get("source_id"),
        "source_md": str(source_path),
        "topic_id": topic_id,
        "route_mode": validation.get("route_mode", ""),
        "raw_article_path": str(raw_article_path),
        "compile_run_id": verified_compile.get("run_id", ""),
        **verified_paths,
    }
    append_jsonl(intake_dir / "auto_processed_manifest.jsonl", processed)
    store.append_jsonl(
        intake_dir / "auto_intake_events.jsonl",
        {
            "schema_version": "auto-intake-event.v1",
            "event_type": "auto_intake_applied",
            "event_at": store.now_iso(),
            "job_id": job.get("job_id"),
            "topic_id": topic_id,
            "route_mode": validation.get("route_mode", ""),
            "raw_article_path": str(raw_article_path),
            "compile_run_id": ingest.get("compile_run_id", ""),
        },
    )
    return {
        "ok": True,
        "schema_version": "auto-intake-apply-result.v1",
        "job_id": job.get("job_id"),
        "topic_id": topic_id,
        "routing_decision": routing_decision,
        "apply_result": apply_result,
        "processed": processed,
        "verified_artifacts": verified_paths,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Apply a validated auto-intake result into a topic wiki.")
    parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--wiki-hub", type=Path, default=DEFAULT_WIKI)
    parser.add_argument("--clippings-root", type=Path, default=DEFAULT_CLIPPINGS)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--claim-ledger", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--safe-article", type=Path)
    args = parser.parse_args(argv)
    job = read_json(args.job.expanduser().resolve())
    result = apply_auto_verified_intake(
        args.intake_dir,
        args.wiki_hub,
        args.clippings_root,
        job,
        args.result.expanduser().resolve(),
        args.claim_ledger.expanduser().resolve(),
        args.sources.expanduser().resolve(),
        args.safe_article.expanduser().resolve() if args.safe_article else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
