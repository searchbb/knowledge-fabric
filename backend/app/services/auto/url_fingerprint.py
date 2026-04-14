"""URL fingerprinting + content hashing for the auto pipeline.

The fingerprint is the primary dedup key for ``pending-urls.json``. The
content hash is the secondary dedup key, computed after the article markdown
is fetched, to catch the case where two different URLs resolve to the same
article body (e.g. shortlinks, redirects, mirror domains).

Both functions are deterministic and have no I/O.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


# Query parameters that we always strip when computing the fingerprint.
# These are tracking, share-source, and analytics parameters that vary
# per-share but always point to the same canonical article.
_TRACKING_PARAM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^utm_"),
    re.compile(r"^spm$"),
    re.compile(r"^spm_"),
    re.compile(r"^from$"),
    re.compile(r"^from_"),
    re.compile(r"^source$"),
    re.compile(r"^ref$"),
    re.compile(r"^referer$"),
    re.compile(r"^referrer$"),
    re.compile(r"^share$"),
    re.compile(r"^share_"),
    re.compile(r"^scene$"),
    re.compile(r"^chksm$"),
    re.compile(r"^mid$"),
    re.compile(r"^idx$"),
    re.compile(r"^sn$"),
    re.compile(r"^poc_token$"),
    re.compile(r"^session_id$"),
    re.compile(r"^_track$"),
    re.compile(r"^track$"),
    re.compile(r"^trk$"),
    re.compile(r"^channel$"),
)


def _is_tracking_param(name: str) -> bool:
    """Return True if the given query parameter name is a tracking marker."""
    lowered = name.lower()
    return any(pat.match(lowered) for pat in _TRACKING_PARAM_PATTERNS)


def _filter_query(query: str) -> str:
    """Drop tracking params and return a deterministically sorted query."""
    if not query:
        return ""
    pairs = parse_qsl(query, keep_blank_values=True)
    kept = [(k, v) for k, v in pairs if not _is_tracking_param(k)]
    if not kept:
        return ""
    kept.sort(key=lambda kv: (kv[0], kv[1]))
    return urlencode(kept, doseq=True)


def normalize_url(raw_url: str) -> str:
    """Normalize a URL into its canonical comparison form.

    Steps:
    1. Lowercase the host.
    2. Drop the fragment.
    3. Strip tracking query parameters.
    4. Sort remaining query parameters deterministically.
    5. Remove a trailing slash from the path (but keep ``"/"`` itself).
    """
    if not raw_url or not isinstance(raw_url, str):
        raise ValueError("normalize_url requires a non-empty string")

    parsed = urlparse(raw_url.strip())
    if not parsed.scheme or not parsed.netloc:
        # Allow path-only inputs to round-trip unchanged so the caller
        # can decide whether to reject them. We do not silently invent
        # a scheme.
        return raw_url.strip()

    host = parsed.netloc.lower()
    path = parsed.path or ""
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    elif path == "":
        path = "/"

    cleaned_query = _filter_query(parsed.query)

    return urlunparse(
        (
            parsed.scheme.lower(),
            host,
            path,
            "",  # params (rarely used)
            cleaned_query,
            "",  # fragment
        )
    )


def compute_fingerprint(raw_url: str) -> str:
    """Compute a stable, comparison-friendly fingerprint for a URL.

    The fingerprint is the normalized URL with the scheme stripped, since
    ``http`` vs ``https`` should not split a single article into two
    fingerprints. The result is what gets stored in ``url_fingerprint`` on
    each pending-urls.json entry.
    """
    normalized = normalize_url(raw_url)
    parsed = urlparse(normalized)
    if not parsed.scheme:
        return normalized
    return urlunparse(("", parsed.netloc, parsed.path, "", parsed.query, ""))


def compute_content_hash(markdown_body: str) -> str:
    """Return a sha256 hash of the article body, prefixed with ``sha256:``.

    Whitespace at the leading and trailing ends is stripped before hashing
    so that minor formatting drift does not split the same article into
    two distinct hashes. We do NOT canonicalize internal whitespace — that
    would mask real content changes.
    """
    if not isinstance(markdown_body, str):
        raise TypeError("compute_content_hash requires a string body")
    digest = hashlib.sha256(markdown_body.strip().encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def fingerprints_match(a: str, b: str) -> bool:
    """Compare two URLs by their fingerprints. Both inputs may be raw URLs."""
    return compute_fingerprint(a) == compute_fingerprint(b)


def first_collision(
    new_url: str, existing: Iterable[dict],
) -> dict | None:
    """Find the first existing item whose fingerprint matches ``new_url``.

    ``existing`` is an iterable of url-item dicts as stored in pending /
    in_flight / processed buckets. Returns the matching dict or ``None``.
    """
    target = compute_fingerprint(new_url)
    for item in existing:
        candidate = item.get("url_fingerprint") or compute_fingerprint(
            item.get("url") or ""
        )
        if candidate == target:
            return item
    return None
