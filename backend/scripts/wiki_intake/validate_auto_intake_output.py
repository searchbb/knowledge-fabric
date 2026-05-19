#!/usr/bin/env python3
"""Validate GPT-style auto-intake artifacts before wiki mutation."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {"schema_version", "job_id", "status", "topic_routing", "source_digest", "verification", "safe_wiki", "follow_up"}
REQUIRED_TOPIC = {"recommended_topic", "confidence", "confidence_score", "needs_human_review"}
REQUIRED_SOURCE_DIGEST = {"one_sentence_summary", "main_claim", "key_points", "core_concepts"}
REQUIRED_VERIFICATION = {"web_verification_performed", "verified_facts", "contradicted_or_stale_claims", "uncertain_claims"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
FALLBACK_TOPIC_ID = "intake-inbox"
RESERVED_TOPIC_IDS = {"", ".", "..", "needs_review", "raw", "index", "compile", "research"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def extract_json_from_raw(raw_path: Path) -> dict[str, Any]:
    text = raw_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if not match:
        raise ValueError("raw_response_missing_json_block")


def slugify_topic_id(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]+", "-", normalized.lower())).strip("-")


def unsafe_topic_id_intent(value: str) -> bool:
    return any(item in value for item in ["/", "\\", "..", "~", "$", "`", "|", ";", "\x00"])


def valid_topic_id(topic_id: str) -> bool:
    if topic_id in RESERVED_TOPIC_IDS:
        return False
    if len(topic_id) > 80:
        return False
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,78}[a-z0-9]", topic_id) or re.fullmatch(r"[a-z0-9]", topic_id))


def topic_label_from_suggestion(suggestion: dict[str, Any], fallback: str) -> str:
    for key in ["display_name", "label", "topic_label", "description"]:
        value = str(suggestion.get(key) or "").strip()
        if value:
            return value[:120]
    return fallback


def topic_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for raw in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", str(value or "").lower()):
        if raw:
            tokens.add(raw)
            if raw.endswith("s") and len(raw) > 3:
                tokens.add(raw[:-1])
    return tokens


def topic_catalog_match_score(suggestion: dict[str, Any], row: dict[str, Any]) -> float:
    suggested_id = slugify_topic_id(str(suggestion.get("topic_id") or ""))
    row_id = slugify_topic_id(str(row.get("topic_id") or row.get("id") or ""))
    if suggested_id and row_id and suggested_id == row_id:
        return 1.0
    suggestion_text = " ".join(
        [
            str(suggestion.get("topic_id") or ""),
            str(suggestion.get("label") or suggestion.get("display_name") or suggestion.get("topic_label") or ""),
            str(suggestion.get("description") or ""),
        ]
    )
    row_text = " ".join(
        [
            str(row.get("topic_id") or row.get("id") or ""),
            str(row.get("label") or row.get("display_name") or row.get("title") or ""),
            str(row.get("description") or ""),
            " ".join(str(item or "") for item in (row.get("aliases") or [])),
            " ".join(str(item or "") for item in (row.get("keywords") or [])),
            " ".join(str(item or "") for item in (row.get("representative_articles") or [])),
        ]
    )
    suggestion_slugs = {slugify_topic_id(item) for item in [suggestion.get("topic_id", ""), suggestion.get("label", "")] if str(item or "").strip()}
    row_slugs = {
        slugify_topic_id(str(row.get("topic_id") or row.get("id") or "")),
        slugify_topic_id(str(row.get("label") or row.get("display_name") or row.get("title") or "")),
        *{slugify_topic_id(str(item or "")) for item in (row.get("aliases") or [])},
    }
    if suggestion_slugs & row_slugs:
        return 0.98
    primary_left = topic_tokens(" ".join([str(suggestion.get("topic_id") or ""), str(suggestion.get("label") or "")]))
    primary_right = topic_tokens(
        " ".join(
            [
                str(row.get("topic_id") or row.get("id") or ""),
                str(row.get("label") or row.get("display_name") or row.get("title") or ""),
                " ".join(str(item or "") for item in (row.get("aliases") or [])),
            ]
        )
    )
    primary_score = 0.0
    if primary_left and primary_right:
        primary_score = len(primary_left & primary_right) / max(1, min(len(primary_left), len(primary_right)))
    left = topic_tokens(suggestion_text)
    right = topic_tokens(row_text)
    if not left or not right:
        return primary_score
    overlap = left & right
    return max(primary_score, len(overlap) / max(1, min(len(left), len(right))))


def best_existing_topic_match(suggestion: dict[str, Any], topic_catalog: list[dict[str, Any]], threshold: float = 0.67) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = 0.0
    for row in topic_catalog:
        topic_id = str(row.get("topic_id") or row.get("id") or "").strip()
        if not topic_id or not valid_topic_id(slugify_topic_id(topic_id)):
            continue
        score = topic_catalog_match_score(suggestion, row)
        if score > best_score:
            best_score = score
            best = row
    if best and best_score >= threshold:
        return {**best, "_match_score": round(best_score, 4)}
    return None


def resolve_topic_route(topic: dict[str, Any], allowed_topics: set[str] | None = None, topic_catalog: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Resolve GPT routing to a concrete wiki topic.

    `needs_review` is an audit signal, not a terminal topic. The resolver keeps
    the original GPT fields intact and adds normalized routing metadata.
    """
    allowed_topics = allowed_topics or set()
    warnings: list[str] = []
    errors: list[str] = []

    if bool(topic.get("needs_human_review")):
        warnings.append("gpt_requested_human_review")

    confidence = str(topic.get("confidence") or "")
    try:
        score = float(topic.get("confidence_score"))
    except (TypeError, ValueError):
        score = -1.0
    if confidence == "low":
        warnings.append("confidence_low")
    if 0 <= score < 0.7:
        warnings.append("confidence_below_threshold")

    raw_recommended = str(topic.get("recommended_topic") or "").strip()
    suggestion = topic.get("new_topic_suggestion") if isinstance(topic.get("new_topic_suggestion"), dict) else {}
    suggestion_match = best_existing_topic_match(suggestion, topic_catalog or []) if suggestion else None
    if raw_recommended == "needs_review":
        warnings.append("recommended_topic_was_needs_review")
    elif raw_recommended:
        if unsafe_topic_id_intent(raw_recommended):
            errors.append(f"unsafe_recommended_topic:{raw_recommended}")
        else:
            candidate = slugify_topic_id(raw_recommended)
            if not valid_topic_id(candidate):
                errors.append(f"invalid_recommended_topic:{raw_recommended}")
            elif allowed_topics and candidate not in allowed_topics:
                warnings.append("recommended_topic_not_in_allowed_topics")
                return {
                    "resolved_topic_id": candidate,
                    "resolved_topic_label": str(topic.get("recommended_topic_label") or candidate),
                    "route_mode": "auto_created_topic",
                    "routing_warnings": warnings + ["used_recommended_topic_as_new_topic"],
                    "routing_errors": errors,
                    "resolved_by": "auto_intake_topic_resolver_v1",
                    "resolver_decision_rule": "recommended_topic_as_new_topic",
                    "reason_codes": ["recommended_topic_not_in_allowed_topics", "used_recommended_topic_as_new_topic"],
                }
            else:
                if suggestion_match:
                    matched_id = slugify_topic_id(str(suggestion_match.get("topic_id") or suggestion_match.get("id") or ""))
                    recommendation_is_strong = confidence == "high" and score >= 0.8
                    if matched_id and matched_id != candidate and not recommendation_is_strong:
                        warnings.append("new_topic_suggestion_mapped_existing_topic")
                        return {
                            "resolved_topic_id": matched_id,
                            "resolved_topic_label": str(suggestion_match.get("label") or suggestion_match.get("display_name") or suggestion_match.get("title") or matched_id),
                            "route_mode": "auto_rerouted_existing_from_new_suggestion",
                            "routing_warnings": warnings,
                            "routing_errors": errors,
                            "resolved_by": "auto_intake_topic_resolver_v1",
                            "resolver_decision_rule": "medium_recommended_topic_overridden_by_new_topic_existing_match",
                            "matched_existing_topic_id": matched_id,
                            "override_reason": "new_topic_suggestion_matches_existing_topic_and_recommended_topic_not_high_confidence",
                            "reason_codes": [
                                "recommended_topic_not_high_confidence",
                                "new_topic_suggestion_matches_existing_topic",
                                "resolver_rerouted_to_existing_topic",
                            ],
                        }
                return {
                    "resolved_topic_id": candidate,
                    "resolved_topic_label": str(topic.get("recommended_topic_label") or candidate),
                    "route_mode": "recommended_topic",
                    "routing_warnings": warnings,
                    "routing_errors": errors,
                    "resolved_by": "auto_intake_topic_resolver_v1",
                    "resolver_decision_rule": "accepted_recommended_topic",
                    "reason_codes": ["accepted_recommended_topic"],
                }

    raw_suggested = str(suggestion.get("topic_id") or "").strip()
    if raw_suggested:
        if unsafe_topic_id_intent(raw_suggested):
            errors.append(f"unsafe_new_topic_suggestion:{raw_suggested}")
        else:
            candidate = slugify_topic_id(raw_suggested)
            if suggestion_match:
                matched_id = slugify_topic_id(str(suggestion_match.get("topic_id") or suggestion_match.get("id") or ""))
                return {
                    "resolved_topic_id": matched_id,
                    "resolved_topic_label": str(suggestion_match.get("label") or suggestion_match.get("display_name") or suggestion_match.get("title") or matched_id),
                    "route_mode": "new_topic_suggestion_matched_existing_topic",
                    "routing_warnings": warnings + ["used_new_topic_suggestion_existing_match"],
                    "routing_errors": errors,
                    "resolved_by": "auto_intake_topic_resolver_v1",
                    "resolver_decision_rule": "new_topic_suggestion_deduplicated_to_existing_topic",
                    "matched_existing_topic_id": matched_id,
                    "override_reason": "new_topic_suggestion_matches_existing_topic",
                    "reason_codes": ["new_topic_suggestion_matches_existing_topic", "deduplicated_new_topic"],
                }
            if valid_topic_id(candidate):
                return {
                    "resolved_topic_id": candidate,
                    "resolved_topic_label": topic_label_from_suggestion(suggestion, candidate),
                    "route_mode": "auto_created_topic",
                    "routing_warnings": warnings + ["used_new_topic_suggestion"],
                    "routing_errors": errors,
                    "resolved_by": "auto_intake_topic_resolver_v1",
                    "resolver_decision_rule": "used_new_topic_suggestion",
                    "reason_codes": ["used_new_topic_suggestion"],
                }
            errors.append(f"invalid_new_topic_suggestion:{raw_suggested}")

    warnings.append("used_fallback_topic")
    return {
        "resolved_topic_id": FALLBACK_TOPIC_ID,
        "resolved_topic_label": "Intake Inbox",
        "route_mode": "fallback_topic",
        "routing_warnings": warnings,
        "routing_errors": errors,
        "resolved_by": "auto_intake_topic_resolver_v1",
        "resolver_decision_rule": "used_fallback_topic",
        "reason_codes": ["used_fallback_topic"],
    }
    return json.loads(match.group(1))


def validate_result(result: dict[str, Any], claim_rows: list[dict[str, Any]], allowed_topics: set[str], require_markers: bool = True, job: dict[str, Any] | None = None, topic_catalog: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL - set(result))
    if missing:
        errors.append("missing_top_level:" + ",".join(missing))
    if result.get("schema_version") != "auto_intake_result_v1":
        errors.append("schema_version_must_be_auto_intake_result_v1")
    job_id = str(result.get("job_id") or "")
    if require_markers:
        if not job_id:
            errors.append("job_id_required_for_markers")
        if result.get("status") != "complete":
            errors.append("status_must_be_complete")

    topic = result.get("topic_routing") if isinstance(result.get("topic_routing"), dict) else {}
    missing_topic = sorted(REQUIRED_TOPIC - set(topic))
    if missing_topic:
        errors.append("missing_topic_fields:" + ",".join(missing_topic))
    recommended_topic = str(topic.get("recommended_topic") or "")
    confidence = str(topic.get("confidence") or "")
    if confidence and confidence not in ALLOWED_CONFIDENCE:
        errors.append(f"invalid_confidence:{confidence}")
    try:
        score = float(topic.get("confidence_score"))
    except (TypeError, ValueError):
        score = -1.0
        errors.append("confidence_score_must_be_number")

    source_digest = result.get("source_digest") if isinstance(result.get("source_digest"), dict) else {}
    missing_digest = sorted(REQUIRED_SOURCE_DIGEST - set(source_digest))
    if missing_digest:
        errors.append("missing_source_digest_fields:" + ",".join(missing_digest))
    if not isinstance(source_digest.get("key_points"), list) or not source_digest.get("key_points"):
        errors.append("source_digest_key_points_required")
    if not isinstance(source_digest.get("core_concepts"), list):
        errors.append("source_digest_core_concepts_must_be_list")
    input_payload = result.get("input") if isinstance(result.get("input"), dict) else {}
    if job:
        if str(input_payload.get("source_id") or "") != str(job.get("source_id") or ""):
            errors.append("input_source_id_mismatch")
        if str(input_payload.get("content_hash") or "") != str(job.get("content_hash") or ""):
            errors.append("input_content_hash_mismatch")

    verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
    missing_verification = sorted(REQUIRED_VERIFICATION - set(verification))
    if missing_verification:
        errors.append("missing_verification_fields:" + ",".join(missing_verification))
    for field in ["verified_facts", "contradicted_or_stale_claims", "uncertain_claims"]:
        if field in verification and not isinstance(verification.get(field), list):
            errors.append(f"verification_{field}_must_be_list")

    safe_wiki = result.get("safe_wiki") if isinstance(result.get("safe_wiki"), dict) else {}
    if not safe_wiki.get("safe_summary"):
        errors.append("safe_wiki_safe_summary_required")
    if not isinstance(safe_wiki.get("do_not_state_as_fact", []), list):
        errors.append("safe_wiki_do_not_state_as_fact_must_be_list")
    joined_text = "\n".join(
        str(item or "")
        for item in [
            source_digest.get("one_sentence_summary", ""),
            source_digest.get("main_claim", ""),
            source_digest.get("mechanism_summary", ""),
            safe_wiki.get("safe_summary", ""),
        ]
    )
    if re.search(r"(/Users/|/tmp/|\\\\|[A-Za-z]:\\\\)", joined_text):
        errors.append("local_path_must_not_be_used_as_fact")
    if int((input_payload or {}).get("images_provided_count") or 0) <= 0 and re.search(r"图中显示|图片显示|截图显示", joined_text):
        errors.append("image_evidence_claim_without_provided_images")

    if not claim_rows:
        errors.append("claim_ledger_required")
    for index, row in enumerate(claim_rows, start=1):
        for field in ["claim_id", "claim_text", "verification_status", "safe_wiki_wording"]:
            if not row.get(field):
                errors.append(f"claim_ledger_row_{index}_missing_{field}")
        if row.get("verification_status") not in {"verified", "source_only", "contradicted", "stale", "uncertain", "not_checked"}:
            errors.append(f"claim_ledger_row_{index}_invalid_status")

    routing = resolve_topic_route(topic, allowed_topics, topic_catalog=topic_catalog or [])
    errors.extend(routing.get("routing_errors") or [])
    warnings.extend(routing.get("routing_warnings") or [])

    status = "invalid" if errors else "valid"
    return {
        "ok": not errors,
        "schema_version": "auto-intake-validation-result.v1",
        "status": status,
        "job_id": job_id,
        "recommended_topic": recommended_topic,
        "resolved_topic_id": routing.get("resolved_topic_id", ""),
        "resolved_topic_label": routing.get("resolved_topic_label", ""),
        "route_mode": routing.get("route_mode", ""),
        "resolved_by": routing.get("resolved_by", ""),
        "resolver_decision_rule": routing.get("resolver_decision_rule", ""),
        "matched_existing_topic_id": routing.get("matched_existing_topic_id", ""),
        "override_reason": routing.get("override_reason", ""),
        "reason_codes": routing.get("reason_codes", []),
        "confidence_score": score,
        "errors": errors,
        "warnings": warnings,
    }


def validate_paths(result_path: Path, claim_ledger_path: Path, allowed_topics_path: Path | None = None, job_path: Path | None = None) -> dict[str, Any]:
    result = load_json(result_path)
    claims = load_jsonl(claim_ledger_path)
    allowed_topics: set[str] = set()
    topic_catalog: list[dict[str, Any]] = []
    if allowed_topics_path and allowed_topics_path.exists():
        payload = load_json(allowed_topics_path)
        topic_catalog = [
            item for item in (payload.get("topic_catalog") or payload.get("allowed_topics") or [])
            if isinstance(item, dict)
        ]
        for item in (payload.get("visible_candidate_topics") or payload.get("allowed_topics", [])):
            if isinstance(item, dict):
                value = str(item.get("topic_id") or item.get("id") or "")
            else:
                value = str(item or "")
            if value:
                allowed_topics.add(value)
    job = load_json(job_path) if job_path and job_path.exists() else None
    return validate_result(result, claims, allowed_topics, job=job, topic_catalog=topic_catalog)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate auto-intake GPT artifacts.")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--claim-ledger", type=Path, required=True)
    parser.add_argument("--allowed-topics", type=Path)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        validation = validate_paths(
            args.result.expanduser().resolve(),
            args.claim_ledger.expanduser().resolve(),
            args.allowed_topics.expanduser().resolve() if args.allowed_topics else None,
            args.job.expanduser().resolve() if args.job else None,
        )
    except Exception as exc:
        validation = {"ok": False, "schema_version": "auto-intake-validation-result.v1", "status": "invalid", "errors": [str(exc)], "warnings": []}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if validation.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
