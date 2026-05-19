#!/usr/bin/env python3
"""Import legacy /Users/mac/wiki processed intake state into KFC-local storage."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.topic_cluster_store import TopicClusterStore, TopicClusterStoreError  # noqa: E402


LEGACY_WIKI_ROOT = Path("/Users/mac/wiki")
KFC_DATA_ROOT = BACKEND_ROOT / "data"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def processed_row_key(row: dict[str, Any]) -> str:
    source_key = str(row.get("source_key") or "").strip()
    if source_key:
        return f"source_key:{source_key}"
    source_id = str(row.get("source_id") or row.get("candidate_id") or "").strip()
    content_hash = str(row.get("content_hash") or "").strip()
    if source_id and content_hash:
        return f"source_hash:{source_id}|{content_hash}"
    source_md = str(row.get("source_md") or row.get("raw_article_path") or row.get("verified_digest_json_path") or "").strip()
    return f"source_path:{source_id}|{source_md}"


def merge_processed_rows(existing: list[dict[str, Any]], remapped: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    merged = list(existing)
    seen = {processed_row_key(row) for row in existing}
    added = 0
    skipped = 0
    for row in remapped:
        key = processed_row_key(row)
        if key in seen:
            skipped += 1
            continue
        merged.append(row)
        seen.add(key)
        added += 1
    return merged, added, skipped


def copy_missing_tree(src: Path, dst: Path) -> tuple[int, int]:
    copied = 0
    skipped = 0
    if not src.exists():
        return copied, skipped
    for source_path in src.rglob("*"):
        target_path = dst / source_path.relative_to(src)
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue
        if target_path.exists():
            skipped += 1
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied += 1
    return copied, skipped


def remap_legacy_path(value: Any, legacy_root: Path, wiki_hub_root: Path) -> Any:
    if not isinstance(value, str):
        return value
    legacy_topics = str(legacy_root / "topics")
    if value.startswith(legacy_topics):
        return str(wiki_hub_root / "topics" / Path(value).relative_to(legacy_topics))
    return value


def topic_title(wiki_hub_root: Path, topic_id: str) -> str:
    profile_path = wiki_hub_root / "topics" / topic_id / "topic_profile.json"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            return str(profile.get("display_name") or profile.get("title") or profile.get("topic_id") or topic_id)
        except (OSError, json.JSONDecodeError):
            return topic_id
    return topic_id


def safe_suffix(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-_")[:100] or "topic"


def ensure_topic_cluster_link(store: TopicClusterStore, wiki_hub_root: Path, topic_id: str) -> str:
    cluster_id = f"tc_wiki_{safe_suffix(topic_id)}"
    title = topic_title(wiki_hub_root, topic_id)
    if store.get_cluster(cluster_id) is None:
        store.create_cluster(
            {
                "cluster_id": cluster_id,
                "title": title,
                "description": f"Legacy Wiki topic imported into KFC wiki hub: {topic_id}",
                "status": "candidate",
                "strategic_relevance": "unknown",
                "created_source": "legacy_wiki_state_import",
            }
        )
    try:
        store.create_cluster_link(
            cluster_id,
            {
                "link_id": f"tcl_{cluster_id}_{safe_suffix(topic_id)}",
                "target_type": "wiki_topic",
                "target_id": topic_id,
                "target_title": title,
                "role": "primary",
                "status": "accepted",
                "source": "legacy_wiki_state_import",
                "confidence": 0.9,
                "rationale": "Backfilled from legacy Wiki auto_processed_manifest.",
            },
        )
        return "created"
    except TopicClusterStoreError as exc:
        if exc.code == "duplicate_link":
            return "existing"
        raise


def import_state(
    *,
    legacy_wiki_root: Path,
    kfc_data_root: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    legacy_intake = legacy_wiki_root / "intake"
    legacy_topics = legacy_wiki_root / "topics"
    kfc_intake = kfc_data_root / "wiki_intake"
    wiki_hub_root = kfc_data_root / "wiki_hub"
    legacy_processed_path = legacy_intake / "auto_processed_manifest.jsonl"
    rows = read_jsonl(legacy_processed_path)
    if not rows:
        raise SystemExit(f"No legacy processed rows found at {legacy_processed_path}")

    remapped: list[dict[str, Any]] = []
    for row in rows:
        item = {key: remap_legacy_path(value, legacy_wiki_root, wiki_hub_root) for key, value in row.items()}
        item["candidate_id"] = item.get("candidate_id") or item.get("source_id")
        item["backfilled_from"] = str(legacy_processed_path)
        remapped.append(item)

    unique_topics = sorted({str(row.get("topic_id") or "").strip() for row in remapped if row.get("topic_id")})
    existing_processed = read_jsonl(kfc_intake / "auto_processed_manifest.jsonl")
    merged_processed, added_rows, skipped_existing_rows = merge_processed_rows(existing_processed, remapped)
    result = {
        "legacy_processed_rows": len(rows),
        "remapped_rows": len(remapped),
        "existing_processed_rows": len(existing_processed),
        "merged_processed_rows": len(merged_processed),
        "added_processed_rows": added_rows,
        "skipped_existing_rows": skipped_existing_rows,
        "unique_topics": unique_topics,
        "copied_topics": False,
        "copied_topic_files": 0,
        "skipped_existing_topic_files": 0,
        "topic_cluster_links": {},
        "auto_processed_manifest": str(kfc_intake / "auto_processed_manifest.jsonl"),
        "wiki_hub_topics": str(wiki_hub_root / "topics"),
    }
    if dry_run:
        return result

    if legacy_topics.exists():
        copied_files, skipped_files = copy_missing_tree(legacy_topics, wiki_hub_root / "topics")
        result["copied_topics"] = copied_files > 0
        result["copied_topic_files"] = copied_files
        result["skipped_existing_topic_files"] = skipped_files
    write_jsonl(kfc_intake / "auto_processed_manifest.jsonl", merged_processed)

    store = TopicClusterStore(
        cluster_dir=kfc_data_root / "topic_clusters",
        link_dir=kfc_data_root / "topic_cluster_links",
    )
    link_counts = {"created": 0, "existing": 0}
    for topic_id in unique_topics:
        status = ensure_topic_cluster_link(store, wiki_hub_root, topic_id)
        link_counts[status] = link_counts.get(status, 0) + 1
    result["topic_cluster_links"] = link_counts
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-wiki-root", type=Path, default=LEGACY_WIKI_ROOT)
    parser.add_argument("--kfc-data-root", type=Path, default=KFC_DATA_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = import_state(
        legacy_wiki_root=args.legacy_wiki_root.expanduser().resolve(),
        kfc_data_root=args.kfc_data_root.expanduser().resolve(),
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
