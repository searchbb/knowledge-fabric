#!/usr/bin/env python3
"""Validate or post a Codex-produced external research pack.

This helper is intentionally a writeback client. It does not perform external
research, call models, or schedule work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


REQUIRED_FIELDS = ("idempotency_key", "title", "source_type", "evidence_candidates")


def load_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


def validate_payload(payload: dict) -> dict:
    missing = [field for field in REQUIRED_FIELDS if not payload.get(field)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    candidates = payload.get("evidence_candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("evidence_candidates must be a non-empty array")
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            raise ValueError(f"candidate {index} must be an object")
        for field in ("claim", "evidence_text", "source_refs"):
            if field not in candidate:
                raise ValueError(f"candidate {index} missing required field: {field}")
    return {
        "title": payload.get("title", ""),
        "source_type": payload.get("source_type", ""),
        "scope": payload.get("scope", "C2_external"),
        "candidate_count": len(candidates),
        "source_ref_count": len(payload.get("source_refs") or []),
        "idempotency_key": payload.get("idempotency_key", ""),
    }


def post_payload(api_base: str, project_id: str, payload: dict) -> dict:
    url = f"{api_base.rstrip('/')}/api/research-projects/{project_id}/external-research-packs/import"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"POST failed: HTTP {exc.code} {detail}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or post a P3 external research writeback payload")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--api-base", default="http://127.0.0.1:5001")
    parser.add_argument("--post", action="store_true", help="POST the payload to KFC after validation")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; this is the default")
    args = parser.parse_args(argv)

    try:
        payload = load_payload(args.payload)
        summary = validate_payload(payload)
        result = {
            "mode": "post" if args.post else "dry-run",
            "project_id": args.project_id,
            "payload": summary,
            "posted": False,
        }
        if args.post:
            result["response"] = post_payload(args.api_base, args.project_id, payload)
            result["posted"] = True
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI should return a concise failure.
        print(f"research_writeback failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
