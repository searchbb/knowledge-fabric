"""
OpenClaw 日志监控工具。

用途：
1. 解析 ~/.openclaw/logs/gateway.log 中的飞书会话事件
2. 识别 OpenClaw 对文章收录流程的执行状态
3. 可选读取对应 Markdown，确认 reading_view_url 等回写字段是否存在
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


RECEIVED_MESSAGE_RE = re.compile(
    r"^(?P<timestamp>\S+) \[feishu\] feishu\[(?P<channel>[^\]]+)\]: received message from "
    r"(?P<sender>\S+) in (?P<conversation>\S+) \((?P<scope>[^)]+)\)$"
)
MESSAGE_TEXT_RE = re.compile(
    r"^(?P<timestamp>\S+) \[feishu\] feishu\[(?P<channel>[^\]]+)\]: "
    r"Feishu\[(?P=channel)\] message in (?P<scope>\w+) (?P<conversation>\S+): (?P<message>.+)$"
)
DISPATCH_AGENT_RE = re.compile(
    r"^(?P<timestamp>\S+) \[feishu\] feishu\[(?P<channel>[^\]]+)\]: "
    r"dispatching to agent \(session=(?P<session_key>[^)]+)\)$"
)
TRACE_CREATED_RE = re.compile(
    r"^(?P<timestamp>\S+) \[plugins\] \[CozeloopTrace\] NEW TraceContext created: "
    r"hook=message_received, channelId=feishu/(?P<conversation>[^,]+), runId=(?P<run_id>[^,]+), "
    r"traceId=(?P<trace_id>\S+)$"
)
TOOL_STARTED_RE = re.compile(
    r"^(?P<timestamp>\S+) \[plugins\] \[CozeloopTrace\] Tool call started: "
    r"(?P<tool_name>[^,]+), spanId=(?P<span_id>[^,]+), traceId=(?P<trace_id>\S+)$"
)
TOOL_FINISHED_RE = re.compile(
    r"^(?P<timestamp>\S+) \[plugins\] \[CozeloopTrace\] Exported tool span: "
    r"(?P<tool_name>[^,]+), spanId=(?P<span_id>[^,]+), duration=(?P<duration_ms>\d+)ms, "
    r"traceId=(?P<trace_id>\S+)$"
)
AGENT_END_RE = re.compile(
    r'^(?P<timestamp>\S+) \[plugins\] \[CozeloopTrace\] agent_end hookCtx: '
    r'\{"channelId":"feishu","sessionKey":"(?P<session_key>[^"]+)"\}$'
)
LLM_OUTPUT_TRACE_RE = re.compile(
    r"^(?P<timestamp>\S+) \[plugins\] \[CozeloopTrace\] REUSING TraceContext: "
    r"hook=llm_output, channelId=agent/(?P<session_suffix>[^,]+), runId=(?P<run_id>[^,]+), "
    r"traceId=(?P<trace_id>\S+)$"
)
DISPATCH_COMPLETE_RE = re.compile(
    r"^(?P<timestamp>\S+) \[feishu\] feishu\[(?P<channel>[^\]]+)\]: "
    r"dispatch complete \(queuedFinal=(?P<queued_final>true|false), replies=(?P<replies>\d+)\)$"
)
TITLE_RE = re.compile(r"已收录[：:]\s*\*{0,2}《(?P<title>[^》]+)》")
URL_LINE_RE = re.compile(r"^[·\-]\s*URL：(?P<url>https?://\S+)$", re.MULTILINE)
MD_LINE_RE = re.compile(r"^[·\-]\s*MD：(?P<md_path>[^\n]+)$", re.MULTILINE)
SOURCE_URL_RE = re.compile(r"https?://\S+")
FRONTMATTER_RE = re.compile(r"\A---\n(?P<frontmatter>.*?)\n---\n", re.DOTALL)


@dataclass
class ToolCallRecord:
    name: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NoteStatus:
    exists: bool = False
    absolute_path: Optional[str] = None
    frontmatter: dict[str, str] = field(default_factory=dict)
    reading_view_url: Optional[str] = None
    project_url: Optional[str] = None
    project_id: Optional[str] = None
    graph_id: Optional[str] = None
    missing_expected_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OpenClawArticleRun:
    channel: str
    conversation_id: str
    scope: str
    sender_id: Optional[str] = None
    received_at: Optional[str] = None
    source_text: Optional[str] = None
    source_url: Optional[str] = None
    session_key: Optional[str] = None
    trace_id: Optional[str] = None
    run_id: Optional[str] = None
    status: str = "received"
    finished_at: Optional[str] = None
    agent_finished_at: Optional[str] = None
    queued_final: Optional[bool] = None
    replies: Optional[int] = None
    assistant_text: Optional[str] = None
    article_title: Optional[str] = None
    article_url: Optional[str] = None
    md_path: Optional[str] = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    note: NoteStatus = field(default_factory=NoteStatus)

    def to_dict(self, *, include_raw_assistant: bool = False) -> dict[str, Any]:
        payload = {
            "channel": self.channel,
            "conversation_id": self.conversation_id,
            "scope": self.scope,
            "sender_id": self.sender_id,
            "received_at": self.received_at,
            "source_text": self.source_text,
            "source_url": self.source_url,
            "session_key": self.session_key,
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "status": self.status,
            "finished_at": self.finished_at,
            "agent_finished_at": self.agent_finished_at,
            "queued_final": self.queued_final,
            "replies": self.replies,
            "article_title": self.article_title,
            "article_url": self.article_url,
            "md_path": self.md_path,
            "tool_calls": [tool.to_dict() for tool in self.tool_calls],
            "note": self.note.to_dict(),
        }
        if include_raw_assistant:
            payload["assistant_text"] = self.assistant_text
        return payload


def _extract_first_url(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = SOURCE_URL_RE.search(text)
    return match.group(0) if match else None


def _extract_assistant_text(payload_json: str) -> Optional[str]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return None

    content = payload.get("content")
    if not isinstance(content, list):
        return None

    text_parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            text_parts.append(item["text"])
    if text_parts:
        return "\n".join(text_parts).strip()
    return None


def classify_run_status(assistant_text: Optional[str]) -> str:
    if not assistant_text:
        return "received"

    if "pipeline还在运行" in assistant_text or "处理中（pipeline正在运行）" in assistant_text:
        return "running"
    if "已收录" in assistant_text:
        return "completed"
    if "失败" in assistant_text or "报错" in assistant_text or "错误" in assistant_text:
        return "failed"
    return "unknown"


def extract_article_details(assistant_text: Optional[str]) -> dict[str, Optional[str]]:
    if not assistant_text:
        return {"article_title": None, "article_url": None, "md_path": None}

    title_match = TITLE_RE.search(assistant_text)
    url_match = URL_LINE_RE.search(assistant_text)
    md_match = MD_LINE_RE.search(assistant_text)
    return {
        "article_title": title_match.group("title").strip() if title_match else None,
        "article_url": url_match.group("url").strip() if url_match else None,
        "md_path": md_match.group("md_path").strip() if md_match else None,
    }


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}

    data: dict[str, str] = {}
    for line in match.group("frontmatter").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def resolve_note_status(md_path: Optional[str], vault_root: Optional[str | Path]) -> NoteStatus:
    if not md_path or not vault_root:
        return NoteStatus()

    absolute_path = Path(md_path).expanduser()
    if not absolute_path.is_absolute():
        absolute_path = Path(vault_root).expanduser().resolve() / md_path

    if not absolute_path.exists():
        return NoteStatus(exists=False, absolute_path=str(absolute_path))

    note_text = absolute_path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(note_text)
    expected_fields = ("reading_view_url", "project_url", "project_id", "graph_id")
    return NoteStatus(
        exists=True,
        absolute_path=str(absolute_path),
        frontmatter=frontmatter,
        reading_view_url=frontmatter.get("reading_view_url"),
        project_url=frontmatter.get("project_url"),
        project_id=frontmatter.get("project_id"),
        graph_id=frontmatter.get("graph_id"),
        missing_expected_fields=[field for field in expected_fields if not frontmatter.get(field)],
    )


def parse_gateway_log_text(text: str) -> list[OpenClawArticleRun]:
    runs: list[OpenClawArticleRun] = []
    active_by_conversation: dict[str, OpenClawArticleRun] = {}
    by_trace_id: dict[str, OpenClawArticleRun] = {}
    pending_tool_starts: dict[str, dict[str, list[str]]] = {}
    pending_assistant: Optional[tuple[str, str]] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        received_match = RECEIVED_MESSAGE_RE.match(line)
        if received_match:
            run = OpenClawArticleRun(
                channel=received_match.group("channel"),
                conversation_id=received_match.group("conversation"),
                scope=received_match.group("scope"),
                sender_id=received_match.group("sender"),
                received_at=received_match.group("timestamp"),
            )
            runs.append(run)
            active_by_conversation[run.conversation_id] = run
            continue

        message_match = MESSAGE_TEXT_RE.match(line)
        if message_match:
            run = active_by_conversation.get(message_match.group("conversation"))
            if run:
                run.source_text = message_match.group("message").strip()
                run.source_url = _extract_first_url(run.source_text)
            continue

        dispatch_match = DISPATCH_AGENT_RE.match(line)
        if dispatch_match:
            session_key = dispatch_match.group("session_key")
            conversation_id = session_key.rsplit(":", 1)[-1]
            run = active_by_conversation.get(conversation_id)
            if run:
                run.session_key = session_key
            continue

        trace_match = TRACE_CREATED_RE.match(line)
        if trace_match:
            conversation_id = trace_match.group("conversation")
            run = active_by_conversation.get(conversation_id)
            if run:
                run.trace_id = trace_match.group("trace_id")
                run.run_id = trace_match.group("run_id")
                by_trace_id[run.trace_id] = run
            continue

        tool_started_match = TOOL_STARTED_RE.match(line)
        if tool_started_match:
            trace_id = tool_started_match.group("trace_id")
            tool_name = tool_started_match.group("tool_name")
            pending_tool_starts.setdefault(trace_id, {}).setdefault(tool_name, []).append(
                tool_started_match.group("timestamp")
            )
            continue

        tool_finished_match = TOOL_FINISHED_RE.match(line)
        if tool_finished_match:
            trace_id = tool_finished_match.group("trace_id")
            run = by_trace_id.get(trace_id)
            if run:
                tool_name = tool_finished_match.group("tool_name")
                start_bucket = pending_tool_starts.get(trace_id, {}).get(tool_name, [])
                started_at = start_bucket.pop(0) if start_bucket else None
                run.tool_calls.append(
                    ToolCallRecord(
                        name=tool_name,
                        started_at=started_at,
                        finished_at=tool_finished_match.group("timestamp"),
                        duration_ms=int(tool_finished_match.group("duration_ms")),
                    )
                )
                if run.status == "received":
                    run.status = "running"
            continue

        agent_end_match = AGENT_END_RE.match(line)
        if agent_end_match:
            session_key = agent_end_match.group("session_key")
            conversation_id = session_key.rsplit(":", 1)[-1]
            run = active_by_conversation.get(conversation_id)
            if run:
                run.agent_finished_at = agent_end_match.group("timestamp")
                if not run.finished_at:
                    run.finished_at = run.agent_finished_at
            continue

        if "event.lastAssistant=" in line:
            timestamp, _, payload = line.partition(" [plugins] ")
            payload_json = line.partition("event.lastAssistant=")[2]
            assistant_text = _extract_assistant_text(payload_json)
            if assistant_text:
                pending_assistant = (timestamp, assistant_text)
            continue

        llm_output_trace_match = LLM_OUTPUT_TRACE_RE.match(line)
        if llm_output_trace_match and pending_assistant:
            trace_id = llm_output_trace_match.group("trace_id")
            run = by_trace_id.get(trace_id)
            if run:
                timestamp, assistant_text = pending_assistant
                run.assistant_text = assistant_text
                run.finished_at = timestamp
                run.status = classify_run_status(assistant_text)
                details = extract_article_details(assistant_text)
                run.article_title = details["article_title"]
                run.article_url = details["article_url"]
                run.md_path = details["md_path"]
            pending_assistant = None
            continue

        dispatch_complete_match = DISPATCH_COMPLETE_RE.match(line)
        if dispatch_complete_match:
            for run in reversed(runs):
                if run.queued_final is None:
                    run.queued_final = dispatch_complete_match.group("queued_final") == "true"
                    run.replies = int(dispatch_complete_match.group("replies"))
                    if not run.finished_at:
                        run.finished_at = dispatch_complete_match.group("timestamp")
                    break
            continue

    return runs


def enrich_runs_with_notes(runs: list[OpenClawArticleRun], vault_root: Optional[str | Path]) -> list[OpenClawArticleRun]:
    if not vault_root:
        return runs

    for run in runs:
        run.note = resolve_note_status(run.md_path, vault_root)
    return runs


def filter_runs(
    runs: list[OpenClawArticleRun],
    *,
    source_url: Optional[str] = None,
    title_keyword: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> list[OpenClawArticleRun]:
    filtered = runs
    if source_url:
        filtered = [run for run in filtered if run.source_url == source_url or run.article_url == source_url]
    if title_keyword:
        lowered = title_keyword.casefold()
        filtered = [
            run
            for run in filtered
            if lowered in (run.article_title or "").casefold() or lowered in (run.assistant_text or "").casefold()
        ]
    if conversation_id:
        filtered = [run for run in filtered if run.conversation_id == conversation_id]
    return filtered
