"""Persist paste-entry notes as content-hashed markdown files.

The downstream auto pipeline already knows how to process a local
markdown file (``PendingUrlStore.add_pending(md_path=...)`` +
``_invoke_article_pipeline_from_file``). This module's only job is to
turn a ``(title, body_markdown)`` pair from the API into a file on disk
whose path is a stable function of the content — that gives us dedup
for free (same content → same path → same fingerprint).

Normalization rules for the content hash:
- CRLF → LF
- Trailing whitespace on each line stripped
- Triple+ blank lines collapsed to double
- Leading/trailing whitespace of whole document stripped

The file itself gets the FULL, unnormalized body written under a
``# {title}`` heading so ``extract_title_from_markdown`` picks up the
title downstream.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

NOTE_DIR_ENV_VAR = "KNOWLEDGE_FABRIC_NOTE_DIR"

_DEFAULT_NOTE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "notes"
)


def _note_dir() -> Path:
    override = os.environ.get(NOTE_DIR_ENV_VAR)
    if override:
        return Path(override)
    return _DEFAULT_NOTE_DIR


def _normalize_for_hash(markdown: str) -> str:
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    # Strip trailing whitespace on every line.
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Collapse runs of 3+ newlines down to 2.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compute_content_fingerprint(markdown: str) -> str:
    """Return ``sha256:<hex>`` of the normalized markdown content."""
    normalized = _normalize_for_hash(markdown)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _hex_digest(markdown: str, title: str) -> str:
    """Hash over BOTH title and body so different titles get different files.

    Callers get this back via the filename stem (no ``sha256:`` prefix).
    """
    combined = f"{title.strip()}\n---\n{_normalize_for_hash(markdown)}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def save_note_to_file(*, title: str, body_markdown: str) -> Path:
    """Write ``# {title}\n\n{body}`` to a content-hashed file.

    Returns the absolute Path. Idempotent: the same ``(title, body)`` pair
    always produces the same path, and writing it again leaves the file
    contents unchanged.
    """
    if not title.strip():
        raise ValueError("note title is empty")
    if not body_markdown.strip():
        raise ValueError("note body_markdown is empty")

    digest = _hex_digest(body_markdown, title)
    target_dir = _note_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{digest}.md"

    content = f"# {title.strip()}\n\n{body_markdown.strip()}\n"

    # Atomic write via tempfile + rename so a partial write can't leave a
    # half-baked file behind. Idempotent: if the target already exists
    # with identical content, the rename is a no-op in effect.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_dir,
        prefix=".tmp-note-",
        suffix=".md",
        delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target_path)

    return target_path.resolve()
