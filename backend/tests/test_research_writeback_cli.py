from __future__ import annotations

import json

from scripts import research_writeback


def _payload(path):
    path.write_text(json.dumps({
        "idempotency_key": "cli-pack-001",
        "title": "Huawei Cloud Agent-ready external evidence pack",
        "source_type": "deep_research",
        "scope": "C2_external",
        "evidence_candidates": [{
            "claim": "企业级 Agent 的核心控制点在执行治理外壳。",
            "evidence_text": "企业 Agent 需要身份、权限、审批、日志、监控和补救机制。",
            "source_refs": ["src_001"],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    return path


def test_research_writeback_cli_dry_run_does_not_post(tmp_path, capsys):
    payload = _payload(tmp_path / "pack.json")

    code = research_writeback.main([
        "--project-id",
        "rp_000000000001",
        "--payload",
        str(payload),
        "--dry-run",
    ])

    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["mode"] == "dry-run"
    assert data["posted"] is False
    assert data["payload"]["candidate_count"] == 1


def test_research_writeback_cli_invalid_payload_returns_nonzero(tmp_path, capsys):
    payload = tmp_path / "bad.json"
    payload.write_text("{}", encoding="utf-8")

    code = research_writeback.main([
        "--project-id",
        "rp_000000000001",
        "--payload",
        str(payload),
    ])

    assert code == 2
    assert "missing required fields" in capsys.readouterr().err
