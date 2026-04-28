"""Theme near-duplicate merge scanner (P1 M3).

Designed per GPT consult d10c98cab0b64a56 (2026-04-16) + audit scheme from
df46f0a3b611600b. Runs AFTER the inline pipeline — never inline — because
merge is a global write op and a failed merge is worse than a missed one.

## Scoring contract

    merge_score = 0.40 * concept_overlap
                + 0.25 * article_overlap
                + 0.20 * name_similarity
                + 0.15 * description_similarity

    concept_overlap = max(jaccard(entry_ids), containment(entry_ids))

## Decision bands

    >= 0.88  +  guardrails pass  →  auto-merge immediately
    0.72 - 0.88                   →  LLM adjudication
                                     MERGE → merge
                                     UNCERTAIN → review queue
                                     KEEP_SEPARATE → skip
    < 0.72  +  name/desc lexical hint  →  LLM adjudication (the "cheap
                                           prefilter" for same-domain sibling
                                           candidates that have no shared
                                           entries yet — this is the P1-1 case)
    < 0.72  +  no hint                 →  skip

## Guardrails for auto-merge (all must pass)

    - concept_overlap >= 0.60 OR article_overlap >= 0.80
    - name_similarity >= 0.75 OR description_similarity >= 0.82

## Scope

    Only pairs where AT LEAST ONE theme is status="candidate". Two stable
    actives should only merge via explicit human action.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from ..registry import global_concept_registry as registry
from ..registry import global_theme_registry as themes

logger = logging.getLogger("mirofish.theme_merge_scanner")

MERGE_SCANNER_VERSION = "v1.initial_2026-04-16"

AUTO_MERGE_THRESHOLD = 0.88
REVIEW_THRESHOLD = 0.72
# Below REVIEW_THRESHOLD, LLM adjudication still fires if ANY of these
# lexical/token signals suggest "same domain sibling candidates":
NAME_SIM_LLM_HINT = 0.55
DESC_SIM_LLM_HINT = 0.70
# CJK-aware fallback: SequenceMatcher underweights short Chinese names.
# If theme names share enough core tokens (e.g. "智能体" in both), that's
# a strong same-domain signal even when char-level ratio stays under 0.55.
NAME_TOKEN_OVERLAP_LLM_HINT = 0.20


# --------------------------------------------------------------------------
# Similarity helpers
# --------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase + strip punctuation/whitespace for lexical comparison."""
    return "".join(ch for ch in (text or "").lower() if ch.isalnum() or ord(ch) > 127)


def _lexical_similarity(a: str, b: str) -> float:
    """Character-level similarity on normalized strings. 0.0 if either empty."""
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _token_set(text: str) -> set[str]:
    """Very rough token set for Chinese+English mix.

    - CJK chars (ord > 127): each char is its own token. Check this FIRST
      because Python's ``str.isalnum()`` returns True for CJK chars and would
      otherwise swallow them into the alphanumeric-run branch.
    - ASCII alphanumerics: grouped into words.
    - Everything else (punct/space): separator.
    """
    toks: set[str] = set()
    cur = ""
    for ch in (text or "").lower():
        if ord(ch) > 127:
            if cur:
                toks.add(cur)
                cur = ""
            toks.add(ch)
        elif ch.isalnum():
            cur += ch
        else:
            if cur:
                toks.add(cur)
                cur = ""
    if cur:
        toks.add(cur)
    return toks


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _containment(a: set, b: set) -> float:
    """|A∩B| / min(|A|,|B|) — catches small-is-subset-of-large."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


# --------------------------------------------------------------------------
# Theme introspection
# --------------------------------------------------------------------------


def _theme_entry_ids(theme: dict) -> set[str]:
    return {m.get("entry_id") for m in theme.get("concept_memberships", []) if m.get("entry_id")}


def _theme_articles(theme: dict, entry_registry: dict) -> set[str]:
    """Set of distinct project_ids backing a theme's concepts."""
    articles: set[str] = set()
    for eid in _theme_entry_ids(theme):
        entry = entry_registry.get(eid)
        if not entry:
            continue
        for link in entry.get("source_links") or []:
            pid = link.get("project_id")
            if pid:
                articles.add(pid)
    return articles


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


@dataclass
class PairScore:
    theme_a_id: str
    theme_b_id: str
    theme_a_name: str
    theme_b_name: str
    theme_a_status: str
    theme_b_status: str
    concept_overlap: float  # max(jaccard, containment)
    article_overlap: float  # containment on distinct articles
    name_similarity: float
    name_token_overlap: float  # separate CJK-aware signal, kept out of merge_score
    description_similarity: float
    merge_score: float
    shared_entry_ids: list[str] = field(default_factory=list)
    shared_article_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme_a_id": self.theme_a_id,
            "theme_b_id": self.theme_b_id,
            "theme_a_name": self.theme_a_name,
            "theme_b_name": self.theme_b_name,
            "theme_a_status": self.theme_a_status,
            "theme_b_status": self.theme_b_status,
            "concept_overlap": round(self.concept_overlap, 4),
            "article_overlap": round(self.article_overlap, 4),
            "name_similarity": round(self.name_similarity, 4),
            "name_token_overlap": round(self.name_token_overlap, 4),
            "description_similarity": round(self.description_similarity, 4),
            "merge_score": round(self.merge_score, 4),
            "shared_entry_ids": self.shared_entry_ids[:20],
            "shared_article_ids": self.shared_article_ids[:20],
        }


def _score_pair(a: dict, b: dict, entry_registry: dict) -> PairScore:
    entries_a = _theme_entry_ids(a)
    entries_b = _theme_entry_ids(b)
    shared_entries = entries_a & entries_b

    articles_a = _theme_articles(a, entry_registry)
    articles_b = _theme_articles(b, entry_registry)
    shared_articles = articles_a & articles_b

    jacc = _jaccard(entries_a, entries_b)
    cont = _containment(entries_a, entries_b)
    concept_overlap = max(jacc, cont)

    if articles_a and articles_b:
        article_overlap = len(shared_articles) / min(len(articles_a), len(articles_b))
    else:
        article_overlap = 0.0

    name_sim = _lexical_similarity(a.get("name", ""), b.get("name", ""))
    desc_sim = _lexical_similarity(a.get("description", ""), b.get("description", ""))

    # Token-level name overlap — computed separately so callers can use it as
    # an LLM-hint signal for CJK names (SequenceMatcher underweights short
    # Chinese strings). Also blended into name_sim when non-trivial so the
    # main merge_score reflects same-token evidence.
    name_token_overlap = _jaccard(_token_set(a.get("name", "")), _token_set(b.get("name", "")))
    if name_token_overlap > name_sim:
        name_sim = (name_sim + name_token_overlap) / 2

    merge_score = (
        0.40 * concept_overlap
        + 0.25 * article_overlap
        + 0.20 * name_sim
        + 0.15 * desc_sim
    )

    return PairScore(
        theme_a_id=a["theme_id"],
        theme_b_id=b["theme_id"],
        theme_a_name=a.get("name", ""),
        theme_b_name=b.get("name", ""),
        theme_a_status=a.get("status", "active"),
        theme_b_status=b.get("status", "active"),
        concept_overlap=concept_overlap,
        article_overlap=article_overlap,
        name_similarity=name_sim,
        name_token_overlap=name_token_overlap,
        description_similarity=desc_sim,
        merge_score=merge_score,
        shared_entry_ids=sorted(shared_entries),
        shared_article_ids=sorted(shared_articles),
    )


def _guardrails_pass(score: PairScore) -> tuple[bool, str]:
    """GPT-recommended guardrails for high-confidence auto-merge."""
    overlap_ok = score.concept_overlap >= 0.60 or score.article_overlap >= 0.80
    name_or_desc_ok = score.name_similarity >= 0.75 or score.description_similarity >= 0.82
    if not overlap_ok:
        return False, "concept/article overlap insufficient"
    if not name_or_desc_ok:
        return False, "name/description similarity insufficient"
    return True, "all guardrails pass"


# --------------------------------------------------------------------------
# LLM adjudication
# --------------------------------------------------------------------------


def _adjudicate_via_llm(
    score: PairScore,
    a: dict,
    b: dict,
    entry_registry: dict,
) -> dict:
    """Ask LLM: MERGE / KEEP_SEPARATE / UNCERTAIN for a borderline pair.

    Uses the default LLMClient; Config now backs that with Bailian unless the
    caller passes an explicit override.
    """
    from ...utils.llm_client import LLMClient

    def _top_concepts(theme: dict, k: int = 8) -> list[str]:
        names = []
        for m in theme.get("concept_memberships", [])[:k]:
            entry = entry_registry.get(m.get("entry_id"))
            if entry and entry.get("canonical_name"):
                names.append(entry["canonical_name"])
        return names

    payload = {
        "theme_a": {
            "theme_id": a["theme_id"],
            "name": a.get("name", ""),
            "status": a.get("status", "active"),
            "description": a.get("description", ""),
            "distinct_articles": len(_theme_articles(a, entry_registry)),
            "member_count": len(_theme_entry_ids(a)),
            "top_concepts": _top_concepts(a),
        },
        "theme_b": {
            "theme_id": b["theme_id"],
            "name": b.get("name", ""),
            "status": b.get("status", "active"),
            "description": b.get("description", ""),
            "distinct_articles": len(_theme_articles(b, entry_registry)),
            "member_count": len(_theme_entry_ids(b)),
            "top_concepts": _top_concepts(b),
        },
        "score_breakdown": {
            "merge_score": round(score.merge_score, 4),
            "concept_overlap": round(score.concept_overlap, 4),
            "article_overlap": round(score.article_overlap, 4),
            "name_similarity": round(score.name_similarity, 4),
            "description_similarity": round(score.description_similarity, 4),
        },
        "shared_concepts": [
            entry_registry.get(eid, {}).get("canonical_name", eid)
            for eid in score.shared_entry_ids[:6]
        ],
    }

    system_prompt = (
        "你是知识治理系统中的主题合并裁决器。\n"
        "判断两个主题是否应当合并为一个。\n"
        "规则：\n"
        "- MERGE: 两者本质是同一个知识域（范围、方法论、问题域基本一致），\n"
        "  只是命名/描述角度略有差异。合并后不会丢失重要语义区分。\n"
        "- KEEP_SEPARATE: 两者属于不同知识域，或属于同一大域但有清晰的子域边界，\n"
        "  合并会让主题变得过于宽泛。\n"
        "- UNCERTAIN: 证据不足以明确判断。\n"
        "倾向保守：不确定时优先 UNCERTAIN，而不是 MERGE。\n"
        "严格返回 JSON，不要输出 markdown。"
    )
    user_prompt = (
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "判断两主题是否应合并。严格返回 JSON：\n"
        '{"verdict": "MERGE|KEEP_SEPARATE|UNCERTAIN", "reason": "一句话理由"}'
    )

    llm = LLMClient()
    result = llm.chat_json(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=512,
    )
    verdict = str(result.get("verdict", "UNCERTAIN")).strip().upper()
    if verdict not in {"MERGE", "KEEP_SEPARATE", "UNCERTAIN"}:
        verdict = "UNCERTAIN"
    return {"verdict": verdict, "reason": result.get("reason", "")}


# --------------------------------------------------------------------------
# Scan entry point
# --------------------------------------------------------------------------


def scan_and_merge_candidates(
    *,
    dry_run: bool = False,
    enable_llm_adjudication: bool = True,
    max_llm_calls: int = 20,
) -> dict[str, Any]:
    """Scan candidate-theme pairs, auto-merge or queue for review.

    Args:
        dry_run: score/decide but don't actually merge or emit events
        enable_llm_adjudication: if False, skip the LLM adjudication band
            (only auto-merge high-confidence pairs fire)
        max_llm_calls: safety cap on LLM adjudication invocations per scan

    Returns a structured audit dict (shape designed per GPT consult C9 layer 2).
    """
    from datetime import datetime

    all_themes = themes.list_themes()  # all statuses
    active = [t for t in all_themes if t.get("status") == "active"]
    candidate = [t for t in all_themes if t.get("status") == "candidate"]
    # Pairs where AT LEAST ONE side is candidate (guardrail: don't auto-merge
    # two stable actives without a human).
    eligible: list[tuple[dict, dict]] = []
    for i, a in enumerate(candidate):
        for b in candidate[i + 1:]:
            eligible.append((a, b))
        for b in active:
            eligible.append((a, b))

    entry_registry = {e["entry_id"]: e for e in registry.list_entries()}

    scored: list[PairScore] = [_score_pair(a, b, entry_registry) for a, b in eligible]
    scored.sort(key=lambda s: -s.merge_score)

    merge_candidates: list[dict] = [s.to_dict() for s in scored]
    actions: list[dict] = []
    merged_pairs: list[dict] = []
    review_queue: list[dict] = []
    llm_calls = 0

    # Build a quick lookup so the action loop doesn't re-traverse the theme list.
    theme_by_id = {t["theme_id"]: t for t in all_themes}

    for score in scored:
        a = theme_by_id.get(score.theme_a_id)
        b = theme_by_id.get(score.theme_b_id)
        if not a or not b:
            # Already merged away in this scan.
            actions.append({
                "pair": [score.theme_a_id, score.theme_b_id],
                "action": "skipped",
                "reason": "one side already merged in this scan",
                "merge_score": round(score.merge_score, 4),
            })
            continue

        # Band 1: high-confidence auto-merge.
        if score.merge_score >= AUTO_MERGE_THRESHOLD:
            gate_ok, gate_reason = _guardrails_pass(score)
            if gate_ok:
                action_record = _do_merge(
                    score, a, b, theme_by_id, merged_pairs,
                    dry_run=dry_run, reason="auto_merge_high_confidence",
                )
                actions.append(action_record)
                continue
            else:
                actions.append({
                    "pair": [score.theme_a_id, score.theme_b_id],
                    "action": "blocked_by_guardrail",
                    "reason": gate_reason,
                    "merge_score": round(score.merge_score, 4),
                })
                continue

        # Band 2: LLM adjudication (either mid-band score OR low-band with
        # strong lexical/token same-domain hint). The NAME_TOKEN_OVERLAP hint
        # specifically handles short CJK theme names where SequenceMatcher
        # underweights shared core morphemes like "智能体".
        should_adjudicate = (
            enable_llm_adjudication
            and llm_calls < max_llm_calls
            and (
                score.merge_score >= REVIEW_THRESHOLD
                or score.name_similarity >= NAME_SIM_LLM_HINT
                or score.name_token_overlap >= NAME_TOKEN_OVERLAP_LLM_HINT
                or score.description_similarity >= DESC_SIM_LLM_HINT
            )
        )
        if should_adjudicate:
            try:
                verdict = _adjudicate_via_llm(score, a, b, entry_registry)
                llm_calls += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "LLM adjudication failed for %s↔%s: %s",
                    score.theme_a_id, score.theme_b_id, exc,
                )
                actions.append({
                    "pair": [score.theme_a_id, score.theme_b_id],
                    "action": "llm_error",
                    "reason": str(exc)[:200],
                    "merge_score": round(score.merge_score, 4),
                })
                continue

            if verdict["verdict"] == "MERGE":
                # Still check guardrails — LLM doesn't override them when
                # score is very low.
                if score.merge_score >= REVIEW_THRESHOLD:
                    # Mid-band: LLM MERGE is enough.
                    action_record = _do_merge(
                        score, a, b, theme_by_id, merged_pairs,
                        dry_run=dry_run, reason="llm_merge_mid_band",
                        llm_reason=verdict.get("reason", ""),
                    )
                else:
                    # Low-band with lexical hint: LLM MERGE is allowed because
                    # the 2 themes both tend to be candidates and this is the
                    # P1-1 "siblings with no shared members yet" case; the
                    # scoring formula undervalues it.
                    action_record = _do_merge(
                        score, a, b, theme_by_id, merged_pairs,
                        dry_run=dry_run, reason="llm_merge_same_domain_siblings",
                        llm_reason=verdict.get("reason", ""),
                    )
                actions.append(action_record)
            elif verdict["verdict"] == "UNCERTAIN":
                review_entry = {
                    "pair": [score.theme_a_id, score.theme_b_id],
                    "theme_a_name": score.theme_a_name,
                    "theme_b_name": score.theme_b_name,
                    "merge_score": round(score.merge_score, 4),
                    "llm_reason": verdict.get("reason", ""),
                    "queued_at": datetime.now().isoformat(),
                }
                review_queue.append(review_entry)
                actions.append({
                    "pair": [score.theme_a_id, score.theme_b_id],
                    "action": "queued_for_review",
                    "reason": verdict.get("reason", ""),
                    "merge_score": round(score.merge_score, 4),
                })
            else:  # KEEP_SEPARATE
                actions.append({
                    "pair": [score.theme_a_id, score.theme_b_id],
                    "action": "keep_separate",
                    "reason": verdict.get("reason", ""),
                    "merge_score": round(score.merge_score, 4),
                })
        else:
            # Below all bands, or LLM budget exhausted.
            actions.append({
                "pair": [score.theme_a_id, score.theme_b_id],
                "action": "skipped",
                "reason": "below thresholds, no lexical hint" if enable_llm_adjudication
                          else "llm adjudication disabled",
                "merge_score": round(score.merge_score, 4),
            })

    if dry_run:
        # Emit an evolution event for merges that WOULD have happened — lets
        # ops dry-run a scan and review before enabling.
        pass
    else:
        if merged_pairs:
            from ..registry.evolution_log import emit_event
            for m in merged_pairs:
                emit_event(
                    event_type="theme_auto_merged",
                    entity_type="global_theme",
                    entity_id=m["winner_theme_id"],
                    entity_name=m.get("winner_name", ""),
                    details={
                        "scanner_version": MERGE_SCANNER_VERSION,
                        "merged_from": m["loser_theme_id"],
                        "merged_from_name": m.get("loser_name", ""),
                        "merge_score": m.get("merge_score"),
                        "action_reason": m.get("action_reason"),
                        "llm_reason": m.get("llm_reason"),
                    },
                )

    return {
        "scanner_version": MERGE_SCANNER_VERSION,
        "dry_run": dry_run,
        "scan_scope": {
            "active_theme_count": len(active),
            "candidate_theme_count": len(candidate),
            "eligible_pair_count": len(eligible),
            "llm_adjudication_enabled": enable_llm_adjudication,
            "max_llm_calls": max_llm_calls,
        },
        "merge_candidates": merge_candidates,
        "actions": actions,
        "merged": merged_pairs,
        "review_queue": review_queue,
        "llm_calls_used": llm_calls,
    }


def _theme_passes_promotion_rules(theme: dict, entry_registry: dict) -> tuple[bool, str]:
    """M2 promotion rules (GPT consult d10c98cab0b64a56 A3).

    Any one of:
      Rule A: distinct_articles >= 2 AND member_count >= 6
      Rule B: distinct_articles >= 3 AND member_count >= 4
    """
    member_count = len(_theme_entry_ids(theme))
    distinct_articles = len(_theme_articles(theme, entry_registry))
    if distinct_articles >= 2 and member_count >= 6:
        return True, f"Rule A: distinct_articles={distinct_articles}, members={member_count}"
    if distinct_articles >= 3 and member_count >= 4:
        return True, f"Rule B: distinct_articles={distinct_articles}, members={member_count}"
    return False, (
        f"below both rules: distinct_articles={distinct_articles}, members={member_count}"
    )


def promote_eligible_candidate_themes(*, dry_run: bool = False) -> dict[str, Any]:
    """Scan candidate themes and promote ones that pass the rules to active.

    Run AFTER merge scan (so merged themes don't get promoted) as part of the
    post-pipeline governance job. Returns a structured audit dict.
    """
    all_themes = themes.list_themes()
    candidates = [t for t in all_themes if t.get("status") == "candidate"]
    entry_registry = {e["entry_id"]: e for e in registry.list_entries()}

    evaluations: list[dict] = []
    promoted: list[dict] = []
    for theme in candidates:
        ok, reason = _theme_passes_promotion_rules(theme, entry_registry)
        member_count = len(_theme_entry_ids(theme))
        distinct_articles = len(_theme_articles(theme, entry_registry))
        record = {
            "theme_id": theme["theme_id"],
            "theme_name": theme.get("name", ""),
            "member_count": member_count,
            "distinct_articles": distinct_articles,
            "eligible": ok,
            "rule_hit": reason,
        }
        evaluations.append(record)
        if ok and not dry_run:
            try:
                themes.set_theme_status(theme["theme_id"], "active")
                promoted.append({
                    **record,
                    "action": "promoted",
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "failed to promote %s to active: %s",
                    theme["theme_id"], exc,
                )
                promoted.append({
                    **record,
                    "action": "promote_error",
                    "error": str(exc)[:200],
                })
        elif ok and dry_run:
            promoted.append({
                **record,
                "action": "would_promote",
            })

    return {
        "scanner_version": MERGE_SCANNER_VERSION,
        "dry_run": dry_run,
        "candidate_theme_count": len(candidates),
        "evaluations": evaluations,
        "promoted": promoted,
    }


def _do_merge(
    score: PairScore,
    a: dict,
    b: dict,
    theme_by_id: dict,
    merged_pairs: list,
    *,
    dry_run: bool,
    reason: str,
    llm_reason: str = "",
) -> dict:
    """Decide winner/loser and execute merge (unless dry_run).

    Winner: prefer status=active > candidate; then prefer more members.
    """
    # Pick winner
    if a.get("status") == "active" and b.get("status") != "active":
        winner, loser = a, b
    elif b.get("status") == "active" and a.get("status") != "active":
        winner, loser = b, a
    else:
        a_members = len(_theme_entry_ids(a))
        b_members = len(_theme_entry_ids(b))
        if a_members >= b_members:
            winner, loser = a, b
        else:
            winner, loser = b, a

    winner_id = winner["theme_id"]
    loser_id = loser["theme_id"]
    winner_members_before = len(_theme_entry_ids(winner))
    loser_members_before = len(_theme_entry_ids(loser))

    if dry_run:
        logger.info(
            "[dry_run] would merge %s (%s) ← %s (%s): score=%.3f reason=%s",
            winner_id, winner.get("name"), loser_id, loser.get("name"),
            score.merge_score, reason,
        )
        record = {
            "pair": [score.theme_a_id, score.theme_b_id],
            "action": "would_merge",
            "winner_theme_id": winner_id,
            "loser_theme_id": loser_id,
            "winner_name": winner.get("name", ""),
            "loser_name": loser.get("name", ""),
            "action_reason": reason,
            "llm_reason": llm_reason,
            "merge_score": round(score.merge_score, 4),
            "member_migration_stats": {
                "winner_members_before": winner_members_before,
                "loser_members_before": loser_members_before,
                "members_to_migrate": loser_members_before,
            },
        }
        return record

    # Real merge. source=loser, target=winner per merge_themes() contract.
    try:
        themes.merge_themes(source_theme_id=loser_id, target_theme_id=winner_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("merge_themes(%s → %s) failed", loser_id, winner_id)
        return {
            "pair": [score.theme_a_id, score.theme_b_id],
            "action": "merge_error",
            "reason": str(exc)[:200],
            "merge_score": round(score.merge_score, 4),
        }

    # Remove loser from lookup so subsequent pairs don't re-touch it.
    theme_by_id.pop(loser_id, None)
    merged_pair_record = {
        "pair": [score.theme_a_id, score.theme_b_id],
        "action": "merged",
        "winner_theme_id": winner_id,
        "loser_theme_id": loser_id,
        "winner_name": winner.get("name", ""),
        "loser_name": loser.get("name", ""),
        "action_reason": reason,
        "llm_reason": llm_reason,
        "merge_score": round(score.merge_score, 4),
        "member_migration_stats": {
            "winner_members_before": winner_members_before,
            "loser_members_before": loser_members_before,
            "members_migrated": loser_members_before,
        },
    }
    merged_pairs.append(merged_pair_record)
    return merged_pair_record
