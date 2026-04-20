from __future__ import annotations

import re

from app.services.graph_quality_gate import GraphQualityGate


class _FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_json(self, messages, temperature=0.2, max_tokens=2000):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.responses.pop(0)


def _node_names_from_prompt(prompt: str) -> list[str]:
    return re.findall(r"- \[[^\]]+\] (.+)", prompt)


def test_backfill_summaries_batches_requests_and_merges_results():
    llm_client = _FakeLLMClient(
        [
            {
                "summaries": [
                    {"name": "节点A", "summary": "节点A摘要"},
                    {"name": "节点B", "summary": "节点B摘要"},
                ]
            },
            {
                "summaries": [
                    {"name": "节点C", "summary": "节点C摘要"},
                ]
            },
        ]
    )
    gate = GraphQualityGate(llm_client=llm_client)
    gate.SUMMARY_BATCH_SIZE = 2

    result = gate.backfill_summaries(
        graph_data={
            "nodes": [
                {"name": "节点A", "labels": ["Problem"], "summary": ""},
                {"name": "节点B", "labels": ["Solution"], "summary": ""},
                {"name": "节点C", "labels": ["Evidence"], "summary": ""},
            ]
        },
        document_text="节点A 节点B 节点C 都在正文里出现。",
    )

    assert result == {
        "节点A": "节点A摘要",
        "节点B": "节点B摘要",
        "节点C": "节点C摘要",
    }
    assert len(llm_client.calls) == 2
    assert _node_names_from_prompt(llm_client.calls[0]["messages"][1]["content"]) == ["节点A", "节点B"]
    assert _node_names_from_prompt(llm_client.calls[1]["messages"][1]["content"]) == ["节点C"]
    assert gate.last_summary_backfill_meta == {
        "requested": 3,
        "completed": 3,
        "missing": [],
    }


def test_backfill_summaries_retries_missing_nodes_individually():
    llm_client = _FakeLLMClient(
        [
            {
                "summaries": [
                    {"name": "节点A", "summary": "节点A摘要"},
                ]
            },
            {
                "summaries": [
                    {"name": "节点B", "summary": "节点B摘要"},
                ]
            },
        ]
    )
    gate = GraphQualityGate(llm_client=llm_client)
    gate.SUMMARY_BATCH_SIZE = 2

    result = gate.backfill_summaries(
        graph_data={
            "nodes": [
                {"name": "节点A", "labels": ["Problem"], "summary": ""},
                {"name": "节点B", "labels": ["Mechanism"], "summary": ""},
            ]
        },
        document_text="节点A 在前文。节点B 在后文，且节点B有自己的上下文。",
    )

    assert result == {
        "节点A": "节点A摘要",
        "节点B": "节点B摘要",
    }
    assert len(llm_client.calls) == 2
    assert _node_names_from_prompt(llm_client.calls[0]["messages"][1]["content"]) == ["节点A", "节点B"]
    assert _node_names_from_prompt(llm_client.calls[1]["messages"][1]["content"]) == ["节点B"]
    assert "节点B 在后文" in llm_client.calls[1]["messages"][1]["content"]
    assert gate.last_summary_backfill_meta == {
        "requested": 2,
        "completed": 2,
        "missing": [],
    }


def test_backfill_summaries_reports_progress_for_batches_and_retries():
    llm_client = _FakeLLMClient(
        [
            {
                "summaries": [
                    {"name": "节点A", "summary": "节点A摘要"},
                ]
            },
            {
                "summaries": []
            },
            {
                "summaries": [
                    {"name": "节点B", "summary": "节点B摘要"},
                ]
            },
        ]
    )
    gate = GraphQualityGate(llm_client=llm_client)
    gate.SUMMARY_BATCH_SIZE = 1
    progress_messages: list[str] = []

    result = gate.backfill_summaries(
        graph_data={
            "nodes": [
                {"name": "节点A", "labels": ["Problem"], "summary": ""},
                {"name": "节点B", "labels": ["Mechanism"], "summary": ""},
            ]
        },
        document_text="节点A 在前文。节点B 在后文，且节点B有自己的上下文。",
        progress_callback=progress_messages.append,
    )

    assert result == {
        "节点A": "节点A摘要",
        "节点B": "节点B摘要",
    }
    assert progress_messages == [
        "回填节点摘要... 批次 1/2 （已生成 1/2 个）",
        "回填节点摘要... 批次 2/2 （已生成 1/2 个）",
        "回填节点摘要... 补充 1/1 （已生成 2/2 个）",
    ]


def test_backfill_summaries_ignores_unrequested_names_from_llm():
    llm_client = _FakeLLMClient(
        [
            {
                "summaries": [
                    {"name": "节点A", "summary": "节点A摘要"},
                    {"name": "幻觉节点", "summary": "不该被计数"},
                ]
            },
            {
                "summaries": [
                    {"name": "节点B", "summary": "节点B摘要"},
                ]
            },
        ]
    )
    gate = GraphQualityGate(llm_client=llm_client)
    gate.SUMMARY_BATCH_SIZE = 2
    progress_messages: list[str] = []

    result = gate.backfill_summaries(
        graph_data={
            "nodes": [
                {"name": "节点A", "labels": ["Problem"], "summary": ""},
                {"name": "节点B", "labels": ["Mechanism"], "summary": ""},
            ]
        },
        document_text="节点A 与 节点B 都在正文里出现。",
        progress_callback=progress_messages.append,
    )

    assert result == {
        "节点A": "节点A摘要",
        "节点B": "节点B摘要",
    }
    assert progress_messages == [
        "回填节点摘要... 批次 1/1 （已生成 1/2 个）",
        "回填节点摘要... 补充 1/1 （已生成 2/2 个）",
    ]
    assert gate.last_summary_backfill_meta == {
        "requested": 2,
        "completed": 2,
        "missing": [],
    }
