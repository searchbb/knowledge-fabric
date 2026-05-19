#!/usr/bin/env python3
"""Process one auto-intake job with isolated per-job execution."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import auto_intake_job_store as store
from apply_auto_verified_intake import apply_auto_verified_intake
from topic_candidate_selector import write_topic_candidate_context
from validate_auto_intake_output import extract_json_from_raw, validate_paths


ROOT = Path(__file__).resolve().parent
DEFAULT_INTAKE = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake")
DEFAULT_WIKI = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub")
DEFAULT_CLIPPINGS = Path("/Users/mac/Downloads/OB笔记/Clippings")
FALLBACK_TOPICS = [
    {"topic_id": "agent-harness", "description": "Agent runtime, tools, skills, coordination, Hermes, OpenClaw, Codex"},
    {"topic_id": "knowledge-workspace", "description": "Knowledge Fabric, KFC, knowledge workspace, graph, semantic layer, NL2SQL, Data Agent"},
    {"topic_id": "ai-tokenization", "description": "tokenization, pricing, AI coding cost, Copilot, Claude Code"},
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def plain_excerpt(markdown: str, limit: int = 600) -> str:
    lines: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line or line.startswith("---") or line.startswith("!") or line.startswith(">"):
            continue
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line).strip("#*- ")
        if cleaned:
            lines.append(cleaned)
        if sum(len(item) for item in lines) >= limit:
            break
    return " ".join(lines)[:limit]


def topic_for_job(job: dict[str, Any]) -> tuple[str, float, str]:
    guesses = job.get("guessed_topics") if isinstance(job.get("guessed_topics"), list) else []
    if guesses:
        topic = str((guesses[0] or {}).get("topic_id") or "")
        score = min(0.95, 0.68 + 0.08 * int((guesses[0] or {}).get("score") or 1))
        confidence = "high" if score >= 0.82 else "medium"
        return topic, score, confidence
    title = str(job.get("title") or "").lower()
    if "token" in title or "计费" in title:
        return "ai-tokenization", 0.82, "high"
    if "agent" in title or "hermes" in title.lower():
        return "agent-harness", 0.82, "high"
    return "needs_review", 0.45, "low"


def prompt_topics(topic_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    topics = (topic_context or {}).get("visible_candidate_topics")
    if isinstance(topics, list) and topics:
        return topics
    return FALLBACK_TOPICS


def prompt_for_job(job: dict[str, Any], article_path: Path, assets_manifest_path: Path, output_dir: Path, topic_context: dict[str, Any] | None = None) -> str:
    article_text = article_path.read_text(encoding="utf-8", errors="replace") if article_path.exists() else ""
    existing_topics = prompt_topics(topic_context)
    return f"""You are an isolated auto-intake worker.

Hard session contract:
- Process exactly one Markdown clipping.
- Do not use prior chat/session context.
- If you need to call Codex, it must be a fresh codex exec process, not the current conversation.
- Return durable artifacts only for this job.

Job id: {job.get("job_id")}
Title: {job.get("title")}
Source URL: {job.get("source_url")}
Scanner guessed topics: {json.dumps(job.get("guessed_topics", []), ensure_ascii=False)}
Candidate topics retrieved from the full local topic catalog: {json.dumps(existing_topics, ensure_ascii=False)}
Assets manifest path: {assets_manifest_path}
Output directory you must write to: {output_dir}

Task:
1. Choose one candidate topic, or propose a new durable topic when none fit. Do not choose a weak candidate only because it is visible.
2. Produce source summary, core concepts, lightweight web verification, claim ledger, safe wiki wording, and follow-up research suggestions.
3. Write these files under the output directory:
   - auto_intake_result.json
   - auto_intake_result.md
   - claim_ledger.jsonl
   - sources.json
   - safe_wiki_article.md
4. If you cannot verify, say so explicitly. Do not invent sources.

Markdown:
```markdown
{article_text[:60000]}
```
"""


def attachment_prompt_for_job(job: dict[str, Any], assets_manifest_path: Path, article_path: Path, topic_context: dict[str, Any] | None = None) -> str:
    article_text = article_path.read_text(encoding="utf-8", errors="replace") if article_path.exists() else ""
    existing_topics = prompt_topics(topic_context)
    topic_choices = " | ".join([str(item.get("topic_id") or "") for item in existing_topics if item.get("topic_id")])
    return f"""请只处理当前这个 auto-intake job，不要使用任何历史对话上下文。

你刚才收到的附件里至少包含 article.md；如果图片也已上传，可以使用图片，但如果你无法确认看到了图片，不能写“图中显示”。
如果 article.md 附件在当前时刻暂时不可读，请使用本提示末尾的 INLINE_ARTICLE_MD_FALLBACK。附件仍然是生产路径的主输入，fallback 只用于避免桌面客户端上传延迟导致只凭标题判断。

Job:
- job_id: {job.get("job_id")}
- source_id: {job.get("source_id")}
- content_hash: {job.get("content_hash")}
- title: {job.get("title")}
- source_url: {job.get("source_url")}
- scanner guessed topics: {json.dumps(job.get("guessed_topics", []), ensure_ascii=False)}
- candidate topics retrieved from the full local topic catalog: {json.dumps(existing_topics, ensure_ascii=False)}
- assets_manifest_path: {assets_manifest_path}

请用 Thinking 模式做一次 one-shot intake：
1. 读取 article.md 附件。
2. 优先从 candidate topics 里选择一个语义准确的主题；不要仅因为某个候选可见就勉强选择。如果候选都不适合，请给出新的英文 topic_id 和 label，并说明是否可能是已有主题的 alias/narrower/broader variant。
3. 总结 source digest、核心概念。
4. 如有 source_url 或正文链接，做轻量联网核验，区分 verified/source_only/stale/uncertain。
5. 给出安全 wiki 表述、不能当事实写的说法、后续 formal Research 建议。

只输出一个 JSON 代码块，不要输出任何额外解释。JSON 格式必须是：
{{
  "auto_intake_result": {{
    "schema_version": "auto_intake_result_v1",
    "job_id": "{job.get("job_id")}",
    "status": "complete",
    "input": {{
      "source_id": "{job.get("source_id")}",
      "content_hash": "{job.get("content_hash")}",
      "title": "...",
      "source_url": "{job.get("source_url")}",
      "images_provided_count": 0,
      "images_used_count": 0,
      "image_limitations": []
    }},
    "topic_routing": {{
      "scanner_guessed_topics": [],
      "recommended_topic": "{topic_choices} | <new-topic-id> | needs_review",
      "recommended_topic_label": "...",
      "confidence": "high | medium | low",
      "confidence_score": 0.0,
      "rationale": "...",
      "secondary_topics": [],
      "needs_human_review": false,
      "new_topic_suggestion": {{
        "topic_id": "lowercase-kebab-case-new-topic",
        "label": "...",
        "description": "..."
      }}
    }},
    "source_digest": {{
      "one_sentence_summary": "...",
      "main_claim": "...",
      "key_points": [],
      "core_concepts": [],
      "mechanism_summary": "...",
      "author_position": "...",
      "source_limitations": []
    }},
    "verification": {{
      "web_verification_performed": true,
      "verification_depth": "lightweight",
      "verified_facts": [],
      "contradicted_or_stale_claims": [],
      "uncertain_claims": [],
      "not_verified_due_to_limits": []
    }},
    "claim_ledger_summary": {{
      "total_claims": 0,
      "verified": 0,
      "source_only": 0,
      "contradicted_or_stale": 0,
      "uncertain": 0
    }},
    "safe_wiki": {{
      "recommended_wording_policy": "verified_or_attributed",
      "safe_summary": "...",
      "do_not_state_as_fact": []
    }},
    "follow_up": {{
      "formal_research_recommended": true,
      "formal_research_priority": "low | medium | high",
      "questions": [],
      "kfc_promotion_recommended": false,
      "reason": "..."
    }}
  }},
  "claim_ledger": [
    {{
      "claim_id": "c001",
      "claim_text": "...",
      "claim_type": "architecture | product_capability | benchmark | opinion | prediction | source_claim",
      "from_source_section": "...",
      "source_evidence": "...",
      "verification_status": "verified | source_only | contradicted | stale | uncertain | not_checked",
      "verification_notes": "...",
      "supporting_urls": [],
      "contradicting_urls": [],
      "safe_wiki_wording": "...",
      "needs_formal_research": false
    }}
  ],
  "sources": {{
    "schema_version": "verification_sources_v1",
    "sources": []
  }},
  "auto_intake_result_md": "# Auto Intake Result\\n...",
  "safe_wiki_article_md": "# ...\\n..."
}}

强约束：
- `auto_intake_result.input.source_id` 和 content_hash 必须逐字等于上面的 Job 值。
- 默认所有 Markdown 都要进入 wiki。只有 JSON 结构、source identity 或安全问题才需要 human review；主题不匹配时请自动建议新主题。
- 如果最合适主题不在候选里，不要强行选弱相关候选；可用 `needs_review` 或新主题建议表达 missing better topic。
- 如果 `recommended_topic` 是新主题，`new_topic_suggestion.topic_id` 必须同值；topic_id 只能用小写英文、数字和连字符。
- `claim_ledger` 只写 3-5 条关键 claim，除非文章极短。
- 每个字段保持简洁，不要输出 Markdown 表格，不要长篇引用原文。
- 不要把未经核验的强断言写成 verified。
- 如果联网核验失败，明确写入 not_verified_due_to_limits，不要伪装成功。
- 最后一行仍然必须在 JSON 代码块内结束；不要在代码块外加说明。

INLINE_ARTICLE_MD_FALLBACK:
```markdown
{article_text[:60000]}
```
"""


def write_prompt(job: dict[str, Any], article_path: Path, assets_manifest_path: Path, topic_context: dict[str, Any] | None = None) -> Path:
    run_dir = Path(str(job["run_dir"]))
    output_dir = run_dir / "output"
    prompt_path = run_dir / "input" / "prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_for_job(job, article_path, assets_manifest_path, output_dir, topic_context), encoding="utf-8")
    return prompt_path


def write_deterministic_artifacts(job: dict[str, Any], article_path: Path) -> dict[str, str]:
    run_dir = Path(str(job["run_dir"]))
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    execution_record_path = run_dir / "audit" / "deterministic_execution_record.json"
    write_json(
        execution_record_path,
        {
            "schema_version": "auto-intake-execution-record.v1",
            "adapter": "deterministic",
            "fresh_session_required": True,
            "fresh_codex_exec_required_for_codex_work": True,
            "reuse_current_conversation": False,
            "job_id": job.get("job_id"),
            "attempt": job.get("attempt"),
            "run_dir": str(run_dir),
            "started_at": store.now_iso(),
        },
    )
    article = article_path.read_text(encoding="utf-8", errors="replace")
    if "AUTO_INTAKE_TEST_MODE: fail_once_then_pass" in article and int(job.get("attempt") or 1) == 1:
        raise RuntimeError("deterministic_fail_once_then_pass")
    topic, score, confidence = topic_for_job(job)
    if "AUTO_INTAKE_TEST_MODE: needs_review" in article:
        topic, score, confidence = "needs_review", 0.35, "low"
    title = str(job.get("title") or article_path.stem)
    excerpt = plain_excerpt(article)
    needs_review = topic == "needs_review" or score < 0.7
    result = {
        "schema_version": "auto_intake_result_v1",
        "job_id": job["job_id"],
        "status": "complete",
        "input": {
            "source_id": job.get("source_id", ""),
            "content_hash": job.get("content_hash", ""),
            "title": title,
            "source_url": job.get("source_url", ""),
            "images_provided_count": job.get("image_refs_resolved", 0),
            "images_used_count": 0,
            "image_limitations": ["deterministic adapter does not perform visual image reading"],
        },
        "topic_routing": {
            "scanner_guessed_topics": [item.get("topic_id") for item in (job.get("guessed_topics") or []) if item.get("topic_id")],
            "recommended_topic": topic,
            "recommended_topic_label": topic,
            "confidence": confidence,
            "confidence_score": score,
            "rationale": "Deterministic adapter mirrors scanner topic for local pipeline validation.",
            "secondary_topics": [],
            "needs_human_review": needs_review,
            "new_topic_suggestion": None,
        },
        "source_digest": {
            "one_sentence_summary": excerpt[:180] or title,
            "main_claim": excerpt[:240] or title,
            "key_points": [excerpt[:180] or title],
            "core_concepts": [topic, "auto-intake"],
            "mechanism_summary": "自动 intake 先保留原文主张，再用轻量核验结果限制 wiki 表述。",
            "author_position": "source-framing",
            "source_limitations": ["deterministic adapter is for local validation, not external research"],
        },
        "verification": {
            "web_verification_performed": False,
            "verification_depth": "deterministic_test",
            "verified_facts": [],
            "contradicted_or_stale_claims": [],
            "uncertain_claims": ["需要正式 GPT/Research adapter 进行外部核验"],
            "not_verified_due_to_limits": ["deterministic adapter did not browse the web"],
        },
        "claim_ledger_summary": {"total_claims": 1, "verified": 0, "source_only": 1, "contradicted_or_stale": 0, "uncertain": 0},
        "safe_wiki": {
            "recommended_wording_policy": "verified_or_attributed",
            "safe_summary": f"原文认为：{excerpt[:220] or title}",
            "do_not_state_as_fact": ["未经外部核验的唯一、最佳、首次、性能或安全强断言"],
        },
        "follow_up": {
            "formal_research_recommended": True,
            "formal_research_priority": "medium",
            "questions": ["外部核验原文关键事实和强断言"],
            "kfc_promotion_recommended": False,
            "reason": "自动 intake 默认不进入 KFC。",
        },
    }
    result_path = output_dir / "auto_intake_result.json"
    markdown_path = output_dir / "auto_intake_result.md"
    claim_path = output_dir / "claim_ledger.jsonl"
    sources_path = output_dir / "sources.json"
    safe_path = output_dir / "safe_wiki_article.md"
    write_json(result_path, result)
    markdown_path.write_text(f"# Auto Intake Result\n\n{result['safe_wiki']['safe_summary']}\n", encoding="utf-8")
    append_jsonl(
        claim_path,
        [
            {
                "claim_id": "c001",
                "claim_text": result["source_digest"]["main_claim"],
                "claim_type": "source_claim",
                "from_source_section": "excerpt",
                "source_evidence": excerpt[:240],
                "verification_status": "source_only",
                "verification_notes": "Deterministic adapter did not perform external verification.",
                "supporting_urls": [],
                "contradicting_urls": [],
                "safe_wiki_wording": result["safe_wiki"]["safe_summary"],
                "needs_formal_research": True,
            }
        ],
    )
    write_json(sources_path, {"schema_version": "verification_sources_v1", "sources": []})
    safe_path.write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                "## Intake 结论",
                "",
                result["safe_wiki"]["safe_summary"],
                "",
                "## 后续 Research 建议",
                "",
                "- 外部核验原文关键事实和强断言",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "result_path": str(result_path),
        "markdown_path": str(markdown_path),
        "claim_ledger_path": str(claim_path),
        "sources_path": str(sources_path),
        "safe_article_path": str(safe_path),
        "execution_record_path": str(execution_record_path),
    }


def run_chatgpt_app_adapter(job: dict[str, Any], prompt_path: Path, timeout_seconds: int) -> dict[str, str]:
    run_dir = Path(str(job["run_dir"]))
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "gpt_response_raw.md"
    helper = Path("/Users/mac/.codex/skills/问GPT/scripts/consult_chatgpt.py")
    cmd = [
        sys.executable,
        str(helper),
        "--new-chat",
        "--timeout",
        str(timeout_seconds),
        "--question-type",
        "design-next-step",
        "--prompt-file",
        str(prompt_path),
    ]
    record = {
        "schema_version": "auto-intake-execution-record.v1",
        "adapter": "chatgpt_app",
        "fresh_session_required": True,
        "fresh_session_command": cmd,
        "started_at": store.now_iso(),
        "prompt_path": str(prompt_path),
        "reuse_current_conversation": False,
    }


def extract_json_bundle(raw_text: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL)
    if match:
        return json.loads(match.group(1))
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(raw_text[start : end + 1])
    raise ValueError("chatgpt_attachment_response_missing_json")


def chatgpt_read_text(stdout: str) -> str:
    """Extract assistant-readable text from opencli json output when possible."""
    def collect(value: Any, out: list[str]) -> None:
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list):
            for item in value:
                collect(item, out)
        elif isinstance(value, dict):
            preferred = ["text", "content", "message", "answer", "response", "markdown", "value"]
            for key in preferred:
                if key in value:
                    collect(value[key], out)
            for key, item in value.items():
                if key not in preferred:
                    collect(item, out)

    try:
        parsed = json.loads(stdout)
    except Exception:
        return stdout
    strings: list[str] = []
    collect(parsed, strings)
    return "\n".join(item for item in strings if item).strip() or stdout


def write_bundle_artifacts(job: dict[str, Any], bundle: dict[str, Any], output_dir: Path) -> dict[str, str]:
    result = bundle.get("auto_intake_result")
    if not isinstance(result, dict):
        raise ValueError("bundle_missing_auto_intake_result")
    claim_ledger = bundle.get("claim_ledger")
    if not isinstance(claim_ledger, list) or not claim_ledger:
        raise ValueError("bundle_missing_claim_ledger")
    sources = bundle.get("sources") if isinstance(bundle.get("sources"), dict) else {"schema_version": "verification_sources_v1", "sources": []}
    result_path = output_dir / "auto_intake_result.json"
    markdown_path = output_dir / "auto_intake_result.md"
    claim_path = output_dir / "claim_ledger.jsonl"
    sources_path = output_dir / "sources.json"
    safe_path = output_dir / "safe_wiki_article.md"
    write_json(result_path, result)
    markdown_path.write_text(str(bundle.get("auto_intake_result_md") or "# Auto Intake Result\n"), encoding="utf-8")
    append_jsonl(claim_path, claim_ledger)
    write_json(sources_path, sources)
    safe_path.write_text(str(bundle.get("safe_wiki_article_md") or result.get("safe_wiki", {}).get("safe_summary") or "# Safe Wiki Article\n"), encoding="utf-8")
    return {
        "result_path": str(result_path),
        "markdown_path": str(markdown_path),
        "claim_ledger_path": str(claim_path),
        "sources_path": str(sources_path),
        "safe_article_path": str(safe_path),
    }


def run_chatgpt_app_attachment_adapter(job: dict[str, Any], article_path: Path, assets_manifest_path: Path, timeout_seconds: int, image_limit: int = 4, topic_context: dict[str, Any] | None = None) -> dict[str, str]:
    run_dir = Path(str(job["run_dir"]))
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "gpt_response_raw.md"
    prompt_path = run_dir / "input" / "attachment_prompt.md"
    prompt_path.write_text(attachment_prompt_for_job(job, assets_manifest_path, article_path, topic_context), encoding="utf-8")
    upload_script = ROOT / "upload_chatgpt_attachment.sh"
    model_cmd = ["opencli", "chatgpt-app", "model", "thinking", "-f", "json"]
    new_cmd = ["opencli", "chatgpt-app", "new", "-f", "json"]
    send_cmd = ["opencli", "chatgpt-app", "send", prompt_path.read_text(encoding="utf-8"), "-f", "json"]
    read_cmd = ["opencli", "chatgpt-app", "read", "-f", "json"]
    record = {
        "schema_version": "auto-intake-execution-record.v1",
        "adapter": "chatgpt_app_attachment",
        "fresh_session_required": True,
        "fresh_chatgpt_thinking_required": True,
        "fresh_codex_exec_required_for_codex_work": True,
        "reuse_current_conversation": False,
        "started_at": store.now_iso(),
        "job_id": job.get("job_id"),
        "attempt": job.get("attempt"),
        "run_dir": str(run_dir),
        "prompt_path": str(prompt_path),
        "article_attachment": str(article_path),
        "image_limit": image_limit,
        "attachments_uploaded": [],
        "attachment_upload_failures": [],
    }
    execution_record_path = run_dir / "audit" / "chatgpt_attachment_execution_record.json"
    write_json(execution_record_path, record)

    def checked_run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                f"command_failed rc={completed.returncode} cmd={cmd!r} stdout={completed.stdout[-1000:]!r} stderr={completed.stderr[-1000:]!r}"
            )
        return completed

    def try_upload(path: Path) -> None:
        completed = subprocess.run([str(upload_script), str(path)], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90, check=False)
        if completed.returncode == 0:
            record["attachments_uploaded"].append(str(path))
            return
        record["attachment_upload_failures"].append({
            "path": str(path),
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
        })

    checked_run(new_cmd, 30)
    checked_run(model_cmd, 30)
    try_upload(article_path)
    try:
        assets = json.loads(assets_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        assets = {}
    images = [Path(item.get("input_path", "")) for item in assets.get("images", []) if item.get("input_path")]
    for image_path in images[:image_limit]:
        if image_path.exists():
            try_upload(image_path)
    write_json(execution_record_path, record)
    time.sleep(int(os.environ.get("CHATGPT_BEFORE_SEND_SETTLE_SECONDS", "12")))
    sent = subprocess.run(send_cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    if sent.returncode != 0:
        raise RuntimeError(f"chatgpt_attachment_send_failed:{sent.stderr or sent.stdout}")
    deadline = time.monotonic() + timeout_seconds
    last_text = ""
    while time.monotonic() < deadline:
        time.sleep(15)
        read = subprocess.run(read_cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
        if read.returncode != 0:
            continue
        last_text = chatgpt_read_text(read.stdout or "")
        raw_path.write_text(last_text, encoding="utf-8")
        if "auto_intake_result" in last_text and "claim_ledger" in last_text:
            try:
                bundle = extract_json_bundle(last_text)
                artifacts = write_bundle_artifacts(job, bundle, output_dir)
                artifacts["raw_response_path"] = str(raw_path)
                artifacts["execution_record_path"] = str(execution_record_path)
                return artifacts
            except Exception:
                # Keep polling; the visible message may still be streaming.
                pass
    raw_path.write_text(last_text, encoding="utf-8")
    raise TimeoutError(f"chatgpt_attachment_response_not_parseable_after_{timeout_seconds}s")
    execution_record_path = run_dir / "audit" / "chatgpt_execution_record.json"
    write_json(execution_record_path, record)
    completed = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds + 60, check=False)
    raw_path.write_text((completed.stdout or "") + ("\n\nSTDERR:\n" + completed.stderr if completed.stderr else ""), encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"chatgpt_app_adapter_failed:{completed.returncode}")
    # A production prompt should ask GPT to emit JSON; this keeps the adapter strict.
    extracted = extract_json_from_raw(raw_path)
    result_path = output_dir / "auto_intake_result.json"
    write_json(result_path, extracted)
    return {
        "result_path": str(result_path),
        "markdown_path": str(output_dir / "auto_intake_result.md"),
        "claim_ledger_path": str(output_dir / "claim_ledger.jsonl"),
        "sources_path": str(output_dir / "sources.json"),
        "safe_article_path": str(output_dir / "safe_wiki_article.md"),
        "raw_response_path": str(raw_path),
        "execution_record_path": str(execution_record_path),
    }


def run_codex_exec_adapter(job: dict[str, Any], prompt_path: Path, timeout_seconds: int, codex_bin: str, model: str = "") -> dict[str, str]:
    run_dir = Path(str(job["run_dir"]))
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [codex_bin, "exec", "--cd", str(ROOT), "--dangerously-bypass-approvals-and-sandbox"]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt_path.read_text(encoding="utf-8"))
    record = {
        "schema_version": "auto-intake-execution-record.v1",
        "adapter": "codex_exec",
        "fresh_session_required": True,
        "fresh_session_command": [codex_bin, "exec", "--cd", str(ROOT), "--dangerously-bypass-approvals-and-sandbox", "<prompt>"],
        "started_at": store.now_iso(),
        "prompt_path": str(prompt_path),
        "reuse_current_conversation": False,
    }
    execution_record_path = run_dir / "audit" / "codex_execution_record.json"
    write_json(execution_record_path, record)
    completed = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, check=False)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "codex_stdout.log").write_text(completed.stdout or "", encoding="utf-8")
    (run_dir / "logs" / "codex_stderr.log").write_text(completed.stderr or "", encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"codex_exec_adapter_failed:{completed.returncode}")
    return {
        "result_path": str(output_dir / "auto_intake_result.json"),
        "markdown_path": str(output_dir / "auto_intake_result.md"),
        "claim_ledger_path": str(output_dir / "claim_ledger.jsonl"),
        "sources_path": str(output_dir / "sources.json"),
        "safe_article_path": str(output_dir / "safe_wiki_article.md"),
        "execution_record_path": str(execution_record_path),
    }


def process_one(args: argparse.Namespace) -> dict[str, Any]:
    intake_dir = args.intake_dir.expanduser().resolve()
    job = store.claim_next(intake_dir, f"auto-intake-runner:{store.now_iso()}", os.getpid())
    if not job:
        return {"ok": True, "status": "no_queued_jobs"}
    try:
        job = store.move_job(intake_dir, job, "preparing_input")
        bundle = store.copy_input_bundle(job)
        article_path = Path(bundle["article_path"])
        assets_manifest_path = Path(bundle["assets_manifest_path"])
        topic_context_path = Path(str(job["run_dir"])) / "input" / "topic_candidates.json"
        topic_context = write_topic_candidate_context(
            wiki_hub=args.wiki_hub,
            intake_dir=intake_dir,
            job=job,
            article_path=article_path,
            output_path=topic_context_path,
        )
        prompt_path = write_prompt(job, article_path, assets_manifest_path, topic_context)
        job.setdefault("artifacts", {}).update({**bundle, "prompt_path": str(prompt_path), "topic_candidates_path": str(topic_context_path)})
        job = store.heartbeat(intake_dir, job, "input_prepared")

        job = store.move_job(intake_dir, job, "gpt_running", f"adapter={args.adapter}")
        if args.adapter == "deterministic":
            artifacts = write_deterministic_artifacts(job, article_path)
        elif args.adapter == "chatgpt_app":
            artifacts = run_chatgpt_app_adapter(job, prompt_path, args.timeout_seconds)
        elif args.adapter == "chatgpt_app_attachment":
            artifacts = run_chatgpt_app_attachment_adapter(job, article_path, assets_manifest_path, args.timeout_seconds, args.image_limit, topic_context)
        elif args.adapter == "codex_exec":
            artifacts = run_codex_exec_adapter(job, prompt_path, args.timeout_seconds, args.codex_bin, args.model)
        elif args.adapter == "manual_file":
            output_dir = Path(str(job["run_dir"])) / "output"
            artifacts = {
                "result_path": str(output_dir / "auto_intake_result.json"),
                "markdown_path": str(output_dir / "auto_intake_result.md"),
                "claim_ledger_path": str(output_dir / "claim_ledger.jsonl"),
                "sources_path": str(output_dir / "sources.json"),
                "safe_article_path": str(output_dir / "safe_wiki_article.md"),
            }
        else:
            raise ValueError(f"unknown_adapter:{args.adapter}")

        job.setdefault("artifacts", {}).update(artifacts)
        job = store.move_job(intake_dir, job, "gpt_output_received")
        job = store.move_job(intake_dir, job, "validating_output")
        validation_path = Path(str(job["run_dir"])) / "output" / "validation.json"
        validation = validate_paths(
            Path(artifacts["result_path"]),
            Path(artifacts["claim_ledger_path"]),
            allowed_topics_path=topic_context_path,
            job_path=Path(str(job.get("job_path") or "")),
        )
        write_json(validation_path, validation)
        job.setdefault("artifacts", {})["validation_path"] = str(validation_path)
        if not validation.get("ok"):
            return store.fail_or_retry(intake_dir, job, "failed_validation", "; ".join(validation.get("errors") or []))
        job = store.move_job(intake_dir, job, "topic_resolved", validation.get("resolved_topic_id") or validation.get("recommended_topic", ""))
        job = store.move_job(intake_dir, job, "ingesting_wiki")
        apply_result = apply_auto_verified_intake(
            intake_dir,
            args.wiki_hub,
            args.clippings_root,
            job,
            Path(artifacts["result_path"]),
            Path(artifacts["claim_ledger_path"]),
            Path(artifacts["sources_path"]),
            Path(artifacts["safe_article_path"]),
            allowed_topics_path=topic_context_path,
        )
        job.setdefault("artifacts", {})["apply_result_path"] = str(Path(str(job["run_dir"])) / "output" / "apply_result.json")
        write_json(Path(job["artifacts"]["apply_result_path"]), apply_result)
        job = store.move_job(intake_dir, job, "compiling_wiki", "compile_completed_by_apply_wrapper")
        return store.move_job(intake_dir, job, "completed", "auto_intake_completed", {"apply": apply_result})
    except subprocess.TimeoutExpired as exc:
        return store.fail_or_retry(intake_dir, job, "failed_gpt", f"timeout:{exc}")
    except Exception as exc:
        status = str(job.get("status") or "")
        failed_status = "failed_compile" if status == "ingesting_wiki" else "failed_gpt" if status == "gpt_running" else "failed"
        return store.fail_or_retry(intake_dir, job, failed_status, str(exc))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Process one auto-intake job in an isolated fresh runner.")
    parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--wiki-hub", type=Path, default=DEFAULT_WIKI)
    parser.add_argument("--clippings-root", type=Path, default=DEFAULT_CLIPPINGS)
    parser.add_argument("--adapter", choices=["deterministic", "manual_file", "chatgpt_app", "chatgpt_app_attachment", "codex_exec"], default=os.environ.get("AUTO_INTAKE_ADAPTER", "chatgpt_app_attachment"))
    parser.add_argument("--timeout-seconds", type=int, default=1500)
    parser.add_argument("--image-limit", type=int, default=int(os.environ.get("AUTO_INTAKE_IMAGE_LIMIT", "4")))
    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "/opt/homebrew/bin/codex"))
    parser.add_argument("--model", default=os.environ.get("CODEX_AUTO_INTAKE_MODEL", ""))
    args = parser.parse_args(argv)
    result = process_one(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") not in {"failed", "failed_gpt", "failed_validation", "failed_compile"} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
