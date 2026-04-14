"""Project-internal concept normalization and merge-suggestion engine.

Stage F2: concepts within a single project can be normalized, grouped, and
merged. Cross-project alignment is explicitly out of scope.

The pipeline is: rule-based normalization → deterministic grouping → optional
LLM-assisted gray-zone resolution.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from itertools import combinations
from typing import Any


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

# Common bracket pairs to unify
_BRACKET_MAP = str.maketrans({
    "\uff08": "(",  # （ → (
    "\uff09": ")",  # ） → )
    "\u3010": "[",  # 【 → [
    "\u3011": "]",  # 】 → ]
    "\u300a": "<",  # 《 → <
    "\u300b": ">",  # 》 → >
})

# Known abbreviation expansions (lowercase → lowercase canonical)
_ABBREVIATIONS: dict[str, str] = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "llm": "large language model",
    "api": "application programming interface",
    "db": "database",
    "ui": "user interface",
    "ux": "user experience",
    "ci": "continuous integration",
    "cd": "continuous delivery",
    "k8s": "kubernetes",
}


def normalize_concept_name(raw: str) -> str:
    """Normalize a concept name for dedup grouping.

    Steps:
    1. Unicode NFKC normalization
    2. Bracket unification (full-width → ASCII)
    3. Collapse whitespace
    4. Lowercase
    5. Strip trailing punctuation
    6. Strip common English plural -s (simple heuristic)
    """
    text = unicodedata.normalize("NFKC", str(raw or "").strip())
    text = text.translate(_BRACKET_MAP)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.lower()
    # Strip trailing punctuation (but keep closing brackets)
    text = re.sub(r"[.,;:!?]+$", "", text).strip()
    # Simple English plural: remove trailing 's' for words > 4 chars
    # Avoid stripping from short words, words ending in 'ss'/'us'/'is'/'es' (ambiguous)
    if (
        text
        and text[-1] == "s"
        and len(text) > 5
        and not text.endswith("ss")
        and not text.endswith("us")
        and not text.endswith("is")
        and not text.endswith("es")
    ):
        text = text[:-1]
    return text


def expand_abbreviation(normalized: str) -> str | None:
    """Return expanded form if normalized name is a known abbreviation."""
    return _ABBREVIATIONS.get(normalized)


# ---------------------------------------------------------------------------
# Deterministic grouping
# ---------------------------------------------------------------------------


def group_candidates_by_normalized_name(
    candidates: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group concept candidates by (label, normalized_name).

    Same normalized name but different label → separate groups (per GPT advice).
    Returns: {group_key: [candidates]}
    """
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        label = str(candidate.get("conceptType") or "Node")
        name = normalize_concept_name(candidate.get("displayName") or "")
        if not name:
            continue
        group_key = f"{label}:{name}"
        groups[group_key].append(candidate)
    return dict(groups)


# ---------------------------------------------------------------------------
# Similarity for gray-zone detection
# ---------------------------------------------------------------------------


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance (simple DP)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[len(b)]


def _jaccard_tokens(a: str, b: str) -> float:
    """Token-level Jaccard similarity."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def find_gray_zone_pairs(
    groups: dict[str, list[dict[str, Any]]],
    *,
    edit_distance_threshold: int = 3,
    jaccard_threshold: float = 0.4,
) -> list[dict[str, Any]]:
    """Find pairs of concept groups that are similar but not identical.

    These are candidates for LLM-assisted merge suggestions.
    Only compares groups with the same label (conceptType).
    """
    # Group the group-keys by label
    by_label: dict[str, list[str]] = defaultdict(list)
    for group_key in groups:
        label, name = group_key.split(":", 1)
        by_label[label].append(group_key)

    pairs: list[dict[str, Any]] = []
    for label, keys in by_label.items():
        if len(keys) < 2:
            continue
        for key_a, key_b in combinations(keys, 2):
            name_a = key_a.split(":", 1)[1]
            name_b = key_b.split(":", 1)[1]

            # Check abbreviation expansion
            exp_a = expand_abbreviation(name_a)
            exp_b = expand_abbreviation(name_b)
            if exp_a and exp_a == name_b:
                pairs.append({"a": key_a, "b": key_b, "reason": "abbreviation_match", "confidence": 0.9})
                continue
            if exp_b and exp_b == name_a:
                pairs.append({"a": key_a, "b": key_b, "reason": "abbreviation_match", "confidence": 0.9})
                continue

            # Edit distance check
            dist = _edit_distance(name_a, name_b)
            max_len = max(len(name_a), len(name_b))
            if max_len > 0 and dist <= edit_distance_threshold and dist / max_len < 0.4:
                pairs.append({
                    "a": key_a,
                    "b": key_b,
                    "reason": "edit_distance",
                    "distance": dist,
                    "confidence": 1.0 - (dist / max_len),
                })
                continue

            # Jaccard token similarity
            sim = _jaccard_tokens(name_a, name_b)
            if sim >= jaccard_threshold:
                pairs.append({
                    "a": key_a,
                    "b": key_b,
                    "reason": "jaccard_similarity",
                    "similarity": round(sim, 3),
                    "confidence": sim,
                })

    # Sort by confidence descending
    pairs.sort(key=lambda p: -p.get("confidence", 0))
    return pairs


# ---------------------------------------------------------------------------
# Merge resolution
# ---------------------------------------------------------------------------


def resolve_merge_chains(decisions: dict[str, Any]) -> dict[str, str]:
    """Resolve transitive merge chains: if A→B and B→C, then A→C.

    Returns: {concept_key: final_canonical_key}
    """
    items = decisions.get("items") or {}
    merge_map: dict[str, str] = {}

    for key, item in items.items():
        if item.get("merge_to"):
            merge_map[key] = item["merge_to"]

    # Resolve chains (max 10 hops to prevent cycles)
    resolved: dict[str, str] = {}
    for key in merge_map:
        target = merge_map[key]
        visited = {key}
        hops = 0
        while target in merge_map and hops < 10:
            if target in visited:
                break  # cycle detected
            visited.add(target)
            target = merge_map[target]
            hops += 1
        resolved[key] = target

    return resolved


def build_merge_suggestions(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build deterministic merge suggestions from rule-based analysis.

    Returns a payload with:
    - groups: normalized groups with member counts
    - suggestions: gray-zone pairs that may benefit from LLM review
    - stats: summary counts
    """
    groups = group_candidates_by_normalized_name(candidates)
    gray_pairs = find_gray_zone_pairs(groups)

    # Detect auto-merged groups: either multiple candidates with the same
    # normalized name, or single candidates with mentionCount > 1 (already
    # grouped at the graph level by ConceptViewService).
    multi_groups = {}
    for key, members in groups.items():
        total_mentions = sum(m.get("mentionCount", 1) for m in members)
        if len(members) > 1 or total_mentions > 1:
            multi_groups[key] = {
                "normalizedName": key.split(":", 1)[1],
                "label": key.split(":", 1)[0],
                "memberCount": total_mentions,
                "members": [
                    {"key": m.get("key"), "displayName": m.get("displayName")}
                    for m in members
                ],
            }

    return {
        "totalCandidates": sum(len(m) for m in groups.values()),
        "uniqueGroups": len(groups),
        "autoMergedGroups": len(multi_groups),
        "grayZonePairCount": len(gray_pairs),
        "autoMergedDetails": multi_groups,
        "grayZonePairs": gray_pairs,
    }
