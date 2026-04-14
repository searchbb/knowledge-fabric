from __future__ import annotations

import json
from pathlib import Path

from app.services.openclaw_log_monitor import (
    classify_run_status,
    enrich_runs_with_notes,
    filter_runs,
    parse_frontmatter,
    parse_gateway_log_text,
)


def _assistant_payload(text: str) -> str:
    return json.dumps(
        {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def test_parse_gateway_log_text_extracts_completed_article_run():
    assistant_text = """✅ 已收录：《采纳率从7.9%到54%：快手智能Code Review的三阶进化》

## 1. 收录路径
· URL：https://mp.weixin.qq.com/s/VrjerF1ca0U3EUzLqeGO-Q
· MD：AI/笔记库/采纳率从7.9%到54%：快手智能Code Review的三阶进化.md
· 作者：Unknown · 主题：AI
"""
    log_text = "\n".join(
        [
            "2026-04-03T18:45:16.693+08:00 [feishu] feishu[default]: received message from ou_xxx in oc_group_1 (group)",
            "2026-04-03T18:45:16.709+08:00 [feishu] feishu[default]: Feishu[default] message in group oc_group_1: https://mp.weixin.qq.com/s/VrjerF1ca0U3EUzLqeGO-Q",
            "2026-04-03T18:45:16.718+08:00 [feishu] feishu[default]: dispatching to agent (session=agent:knowledge-crew:feishu:group:oc_group_1)",
            "2026-04-03T18:45:16.727+08:00 [plugins] [CozeloopTrace] NEW TraceContext created: hook=message_received, channelId=feishu/oc_group_1, runId=run-1, traceId=trace-1",
            "2026-04-03T18:45:25.033+08:00 [plugins] [CozeloopTrace] Tool call started: exec, spanId=span-exec, traceId=trace-1",
            "2026-04-03T18:45:35.061+08:00 [plugins] [CozeloopTrace] Exported tool span: exec, spanId=span-exec, duration=10023ms, traceId=trace-1",
            "2026-04-03T18:45:39.720+08:00 [plugins] [CozeloopTrace] Tool call started: process, spanId=span-process-1, traceId=trace-1",
            "2026-04-03T18:47:39.760+08:00 [plugins] [CozeloopTrace] Exported tool span: process, spanId=span-process-1, duration=120037ms, traceId=trace-1",
            f"2026-04-03T18:50:12.220+08:00 [plugins] [CozeloopTrace][DEBUG] llm_output event.lastAssistant={_assistant_payload(assistant_text)}",
            '2026-04-03T18:50:12.223+08:00 [plugins] [CozeloopTrace] REUSING TraceContext: hook=llm_output, channelId=agent/knowledge-crew:feishu:group:oc_group_1, runId=run-1, traceId=trace-1',
            "2026-04-03T18:50:13.383+08:00 [feishu] feishu[default]: dispatch complete (queuedFinal=true, replies=2)",
        ]
    )

    runs = parse_gateway_log_text(log_text)

    assert len(runs) == 1
    run = runs[0]
    assert run.source_url == "https://mp.weixin.qq.com/s/VrjerF1ca0U3EUzLqeGO-Q"
    assert run.article_title == "采纳率从7.9%到54%：快手智能Code Review的三阶进化"
    assert run.article_url == "https://mp.weixin.qq.com/s/VrjerF1ca0U3EUzLqeGO-Q"
    assert run.md_path == "AI/笔记库/采纳率从7.9%到54%：快手智能Code Review的三阶进化.md"
    assert run.status == "completed"
    assert run.queued_final is True
    assert run.replies == 2
    assert [tool.name for tool in run.tool_calls] == ["exec", "process"]
    assert [tool.duration_ms for tool in run.tool_calls] == [10023, 120037]


def test_classify_run_status_recognizes_running_pipeline():
    assistant_text = """pipeline还在运行。基于智能匹配结果，我现在可以生成一个**完整的知识拆解报告**：

## ✅ **已收录：《1.9万行Claude Code代码引发百人联名"封杀"》**

### **1. 收录路径**
· URL：https://mp.weixin.qq.com/s/8_GMBlQg2sOdltUMO8l99g
· MD：处理中（pipeline正在运行）
"""
    assert classify_run_status(assistant_text) == "running"


def test_enrich_runs_with_notes_reads_frontmatter(tmp_path):
    assistant_text = """✅ 已收录：《示例文章》

## 1. 收录路径
· URL：https://mp.weixin.qq.com/s/example
· MD：AI/笔记库/示例文章.md
"""
    log_text = "\n".join(
        [
            "2026-04-03T18:45:16.693+08:00 [feishu] feishu[default]: received message from ou_xxx in oc_group_1 (group)",
            "2026-04-03T18:45:16.709+08:00 [feishu] feishu[default]: Feishu[default] message in group oc_group_1: https://mp.weixin.qq.com/s/example",
            "2026-04-03T18:45:16.727+08:00 [plugins] [CozeloopTrace] NEW TraceContext created: hook=message_received, channelId=feishu/oc_group_1, runId=run-1, traceId=trace-1",
            f"2026-04-03T18:50:12.220+08:00 [plugins] [CozeloopTrace][DEBUG] llm_output event.lastAssistant={_assistant_payload(assistant_text)}",
            '2026-04-03T18:50:12.223+08:00 [plugins] [CozeloopTrace] REUSING TraceContext: hook=llm_output, channelId=agent/knowledge-crew:feishu:group:oc_group_1, runId=run-1, traceId=trace-1',
        ]
    )
    note_path = tmp_path / "AI" / "笔记库" / "示例文章.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text(
        "---\nreading_view_url: http://127.0.0.1:3001/process/proj_test?mode=graph&view=reading\nproject_id: proj_test\n---\n\n# 示例文章\n",
        encoding="utf-8",
    )

    runs = enrich_runs_with_notes(parse_gateway_log_text(log_text), tmp_path)
    run = runs[0]

    assert run.note.exists is True
    assert run.note.absolute_path == str(note_path)
    assert run.note.frontmatter["reading_view_url"] == "http://127.0.0.1:3001/process/proj_test?mode=graph&view=reading"
    assert run.note.project_id == "proj_test"
    assert run.note.missing_expected_fields == ["project_url", "graph_id"]
    assert filter_runs(runs, source_url="https://mp.weixin.qq.com/s/example")[0].article_title == "示例文章"


def test_parse_frontmatter_handles_simple_yaml_block():
    text = "---\nsource_url: https://example.com\nreading_view_url: http://localhost:3001/process/proj_1?mode=graph&view=reading\n---\n\n# 标题\n"
    frontmatter = parse_frontmatter(text)
    assert frontmatter == {
        "source_url": "https://example.com",
        "reading_view_url": "http://localhost:3001/process/proj_1?mode=graph&view=reading",
    }
