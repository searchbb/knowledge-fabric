"""Unit tests for the note_store helper.

note_store is responsible for turning a (title, body_markdown) pair into
a content-hashed markdown file on disk that downstream consumers
(add_pending, article_workspace_pipeline) can treat exactly like any
other local markdown source.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.auto.note_store import (
    NOTE_DIR_ENV_VAR,
    compute_content_fingerprint,
    save_note_to_file,
)


@pytest.fixture
def note_dir(tmp_path, monkeypatch):
    """Redirect note_store writes to a pytest tmpdir so the test suite
    never scribbles in the real backend/data/notes/."""
    monkeypatch.setenv(NOTE_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


class TestComputeContentFingerprint:
    def test_identical_content_same_hash(self):
        a = compute_content_fingerprint("# hello\n\nworld")
        b = compute_content_fingerprint("# hello\n\nworld")
        assert a == b

    def test_crlf_normalized_to_lf(self):
        unix = compute_content_fingerprint("a\nb\nc")
        windows = compute_content_fingerprint("a\r\nb\r\nc")
        assert unix == windows

    def test_trailing_whitespace_stripped(self):
        a = compute_content_fingerprint("hello world")
        b = compute_content_fingerprint("hello world   \n\n\n")
        assert a == b

    def test_triple_newlines_collapsed(self):
        a = compute_content_fingerprint("p1\n\np2")
        b = compute_content_fingerprint("p1\n\n\n\n\np2")
        assert a == b

    def test_fingerprint_format_is_sha256_prefixed(self):
        fp = compute_content_fingerprint("anything")
        assert fp.startswith("sha256:")
        # 7 chars for "sha256:" + 64 hex chars
        assert len(fp) == 7 + 64


class TestSaveNoteToFile:
    def test_creates_file_with_title_as_h1(self, note_dir):
        path = save_note_to_file(title="My Note", body_markdown="hello world")
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert content.startswith("# My Note\n")
        assert "hello world" in content

    def test_filename_is_content_hash(self, note_dir):
        path = save_note_to_file(title="T", body_markdown="body text")
        assert path.parent == note_dir
        assert path.suffix == ".md"
        # stem should be the 64-char hex digest (no sha256: prefix)
        assert len(path.stem) == 64
        assert all(c in "0123456789abcdef" for c in path.stem)

    def test_same_content_same_path(self, note_dir):
        p1 = save_note_to_file(title="T", body_markdown="body")
        p2 = save_note_to_file(title="T", body_markdown="body")
        assert p1 == p2

    def test_different_body_different_path(self, note_dir):
        p1 = save_note_to_file(title="T", body_markdown="body one")
        p2 = save_note_to_file(title="T", body_markdown="body two")
        assert p1 != p2

    def test_different_title_different_path(self, note_dir):
        p1 = save_note_to_file(title="Title A", body_markdown="body")
        p2 = save_note_to_file(title="Title B", body_markdown="body")
        assert p1 != p2

    def test_returns_absolute_path(self, note_dir):
        path = save_note_to_file(title="T", body_markdown="body")
        assert path.is_absolute()

    def test_idempotent_write(self, note_dir):
        """Writing the same content twice must not corrupt the file."""
        p1 = save_note_to_file(title="T", body_markdown="body")
        first = p1.read_text(encoding="utf-8")
        p2 = save_note_to_file(title="T", body_markdown="body")
        second = p2.read_text(encoding="utf-8")
        assert first == second

    def test_title_sanitization_for_filesystem_safety(self, note_dir):
        """Titles with path separators or null bytes must not break the write."""
        path = save_note_to_file(
            title="weird/title\x00with:chars",
            body_markdown="body",
        )
        assert path.exists()

    def test_empty_markdown_rejected(self, note_dir):
        with pytest.raises(ValueError, match="empty"):
            save_note_to_file(title="T", body_markdown="")

    def test_empty_title_rejected(self, note_dir):
        with pytest.raises(ValueError, match="empty"):
            save_note_to_file(title="", body_markdown="body")
