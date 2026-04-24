"""Migrate legacy domain=unknown themes to domain=tech / methodology.

Follow-up to v3 domain-scoped ontology (GPT priority A, 2026-04-23).

Legacy themes (created before the domain field existed) are runtime-treated
as 'unknown' and excluded from typed domain queries. That isolates them
from new tech articles that would naturally match them. Fix: classify each
legacy theme via LLM and migrate high-confidence ones.

Policy (GPT consult):
- confidence >= 0.80 → auto-migrate to the classified domain
- confidence 0.55-0.80 → output to review_list.json, don't modify
- confidence < 0.55 → leave as unknown

Every migrated theme records migration_source="unknown_v2_<timestamp>" for
auditability and rollback.

Usage:
    python scripts/migrate_legacy_themes.py           # dry-run (no writes)
    python scripts/migrate_legacy_themes.py --apply   # actually migrate
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/mac/Downloads/code/knowledge-fabric/backend")

from app.utils.llm_client import LLMClient


THEMES_PATH = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/uploads/projects/global_themes.json")
CONCEPT_REGISTRY_PATH = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/uploads/projects/concept_registry.json")
REVIEW_LIST_PATH = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/uploads/projects/legacy_theme_migration_review.json")

AUTO_MIGRATE_THRESHOLD = 0.80
REVIEW_THRESHOLD = 0.55


CLASSIFIER_SYSTEM_PROMPT = """你是知识图谱主题归类器。任务：给一个已存在的全局主题判定它属于 tech 还是 methodology。

定义：
- tech：系统架构、技术实现、工程方案、性能优化、产品技术、论文技术方法、AI/软件/硬件工程
- methodology：方法论、认知框架、管理/组织经验、社会心理分析、做事原则、流程套路、个人成长与职业规划

判定依据是**主题名 + 描述 + 成员概念样本**。不要被成员概念的 type 标签误导（那些可能是历史 ontology 产物）。看概念名的语义。

输出严格 JSON：

{
  "domain": "tech" | "methodology",
  "confidence": 0.0-1.0,
  "reason": "一句话说明依据"
}

置信度校准：
- >= 0.90：极其清晰属于某一域（比如主题名直接含"强化学习"/"硬件"/"社会流动性"）
- 0.80-0.90：清晰但有少量混合（占主导方向明确）
- 0.60-0.80：灰区（方向不稳，两边都能讲通）
- < 0.60：判不了，别硬判"""


def classify_theme(llm: LLMClient, theme: dict, concept_names: list[str]) -> dict:
    """Classify a single legacy theme via LLM."""
    name = theme.get("name", "")
    desc = theme.get("description", "")
    samples = "\n".join(f"- {n}" for n in concept_names[:10])

    user_msg = (
        f"主题名：{name}\n"
        f"描述：{desc or '(无)'}\n\n"
        f"成员概念（前 10 个）：\n{samples or '(无)'}\n\n"
        "判定。"
    )
    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    try:
        result = llm.chat_json(messages=messages, temperature=0.0, max_tokens=300)
    except Exception as e:
        return {"domain": "unknown", "confidence": 0.0, "reason": f"llm_error: {e!s}"[:200]}

    primary = str(result.get("domain", "")).strip().lower()
    if primary not in {"tech", "methodology"}:
        return {"domain": "unknown", "confidence": 0.0,
                "reason": f"unknown domain {primary!r}"}
    return {
        "domain": primary,
        "confidence": float(result.get("confidence", 0) or 0),
        "reason": str(result.get("reason", ""))[:200],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write changes")
    args = ap.parse_args()

    themes_data = json.loads(THEMES_PATH.read_text())
    cr_data = json.loads(CONCEPT_REGISTRY_PATH.read_text())
    entries = cr_data.get("entries", {})

    # Find all themes without a domain field (legacy unknown)
    legacy = [
        t for t in themes_data["themes"].values()
        if "domain" not in t
    ]
    print(f"Found {len(legacy)} legacy themes (no domain field)")
    print()

    llm = LLMClient()
    decisions = []
    for t in legacy:
        # Top member concept names
        member_ids = [m.get("entry_id") for m in t.get("concept_memberships", [])
                     if m.get("role") == "member"]
        names = [entries.get(eid, {}).get("canonical_name", eid) for eid in member_ids[:10]]

        decision = classify_theme(llm, t, names)
        decisions.append({
            "theme_id": t["theme_id"],
            "name": t.get("name"),
            "status": t.get("status"),
            "member_count": len(member_ids),
            "classified_domain": decision["domain"],
            "confidence": decision["confidence"],
            "reason": decision["reason"],
        })

    # Print table
    print(f"{'status':10s} | {'conf':5s} | {'→domain':12s} | {'members':7s} | name / reason")
    print("-" * 110)
    auto = []
    review = []
    skip = []
    for d in decisions:
        if d["classified_domain"] != "unknown" and d["confidence"] >= AUTO_MIGRATE_THRESHOLD:
            verdict = "AUTO"
            auto.append(d)
        elif d["classified_domain"] != "unknown" and d["confidence"] >= REVIEW_THRESHOLD:
            verdict = "review"
            review.append(d)
        else:
            verdict = "skip"
            skip.append(d)
        print(f"{verdict:10s} | {d['confidence']:.2f}  | {d['classified_domain']:12s} | {d['member_count']:7d} | {d['name']}")
        print(f"{'':10s} |       | {'':12s} | {'':7s} | ↳ {d['reason']}")
    print()
    print(f"Auto-migrate: {len(auto)}, Review: {len(review)}, Skip: {len(skip)}")
    print()

    if not args.apply:
        print("(dry-run — pass --apply to actually migrate)")
        return

    # Apply
    timestamp = int(time.time())
    migration_source = f"unknown_v2_{timestamp}"
    migrated_count = 0
    for d in auto:
        theme = themes_data["themes"][d["theme_id"]]
        theme["domain"] = d["classified_domain"]
        theme["migration_source"] = migration_source
        theme["migration_classified_confidence"] = d["confidence"]
        theme["migration_reason"] = d["reason"]
        migrated_count += 1
    THEMES_PATH.write_text(json.dumps(themes_data, ensure_ascii=False, indent=2))
    print(f"✅ Wrote {migrated_count} auto-migrations to {THEMES_PATH}")

    # Write review list
    REVIEW_LIST_PATH.write_text(json.dumps({
        "migration_source": migration_source,
        "review_items": review,
        "skipped": skip,
    }, ensure_ascii=False, indent=2))
    print(f"✅ Wrote {len(review)} review items + {len(skip)} skipped to {REVIEW_LIST_PATH}")
    print()
    print("To rollback: strip domain/migration_* fields from themes where "
          f"migration_source='{migration_source}'")


if __name__ == "__main__":
    main()
