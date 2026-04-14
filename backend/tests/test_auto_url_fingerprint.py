"""Tests for ``app.services.auto.url_fingerprint``."""

from __future__ import annotations

from app.services.auto.url_fingerprint import (
    compute_content_hash,
    compute_fingerprint,
    fingerprints_match,
    first_collision,
    normalize_url,
)


class TestNormalizeUrl:
    def test_strips_utm_params(self):
        raw = "https://example.com/article?utm_source=feishu&utm_medium=share&id=42"
        normalized = normalize_url(raw)
        assert "utm_" not in normalized
        assert "id=42" in normalized

    def test_strips_wechat_share_params(self):
        raw = "https://mp.weixin.qq.com/s/AAAAAA?chksm=abc&scene=23&mid=1&idx=2&sn=zzz"
        normalized = normalize_url(raw)
        # WeChat share params are all in the strip set
        assert "chksm" not in normalized
        assert "scene" not in normalized
        assert "mid" not in normalized
        assert "idx" not in normalized
        assert "sn=" not in normalized

    def test_lowercases_host(self):
        raw = "HTTPS://Example.COM/article"
        normalized = normalize_url(raw)
        assert normalized.startswith("https://example.com/")

    def test_drops_fragment(self):
        raw = "https://example.com/article#section-2"
        normalized = normalize_url(raw)
        assert "#" not in normalized

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/foo/") == "https://example.com/foo"

    def test_preserves_root_slash(self):
        # Root path slash must stay
        normalized = normalize_url("https://example.com/")
        assert normalized.endswith("example.com/")

    def test_sorts_query_params_deterministically(self):
        a = normalize_url("https://example.com/a?id=1&type=foo")
        b = normalize_url("https://example.com/a?type=foo&id=1")
        assert a == b

    def test_rejects_empty_input(self):
        import pytest
        with pytest.raises(ValueError):
            normalize_url("")


class TestComputeFingerprint:
    def test_drops_scheme_so_http_and_https_collide(self):
        a = compute_fingerprint("http://example.com/article")
        b = compute_fingerprint("https://example.com/article")
        assert a == b

    def test_wechat_real_world_collision(self):
        # Two ways the same WeChat article can be shared
        share_a = "https://mp.weixin.qq.com/s/iP9StbK2Y5dgG1TH3NG1LA"
        share_b = "https://mp.weixin.qq.com/s/iP9StbK2Y5dgG1TH3NG1LA?chksm=cafe&scene=23&from=share"
        assert compute_fingerprint(share_a) == compute_fingerprint(share_b)

    def test_distinct_articles_distinct_fingerprints(self):
        a = compute_fingerprint("https://mp.weixin.qq.com/s/AAAA")
        b = compute_fingerprint("https://mp.weixin.qq.com/s/BBBB")
        assert a != b


class TestFingerprintsMatch:
    def test_match_returns_true(self):
        assert fingerprints_match(
            "https://example.com/x?utm_source=a",
            "https://example.com/x?utm_source=b",
        )

    def test_mismatch_returns_false(self):
        assert not fingerprints_match(
            "https://example.com/x",
            "https://example.com/y",
        )


class TestFirstCollision:
    def test_finds_existing(self):
        existing = [
            {"url": "https://example.com/article", "url_fingerprint": "//example.com/article"}
        ]
        hit = first_collision("https://example.com/article?utm_source=zzz", existing)
        assert hit is not None
        assert hit["url"].endswith("article")

    def test_no_match_returns_none(self):
        existing = [{"url": "https://example.com/x", "url_fingerprint": "//example.com/x"}]
        assert first_collision("https://other.com/y", existing) is None


class TestContentHash:
    def test_deterministic(self):
        a = compute_content_hash("hello world")
        b = compute_content_hash("hello world")
        assert a == b
        assert a.startswith("sha256:")

    def test_whitespace_trim(self):
        a = compute_content_hash("hello")
        b = compute_content_hash("  hello\n")
        assert a == b

    def test_distinct_bodies_distinct_hashes(self):
        assert compute_content_hash("a") != compute_content_hash("b")
