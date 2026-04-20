from __future__ import annotations

import requests
import subprocess
import sys
from pathlib import Path

from app.services.article_workspace_pipeline import (
    ArticleWorkspacePipeline,
    build_note_content,
    build_project_url,
    build_reading_view_url,
    extract_title_from_markdown,
    sanitize_note_title,
    strip_frontmatter,
    strip_leading_title,
)


def test_extract_title_from_markdown_prefers_heading():
    markdown = "# 从文本到结构\n\n正文内容"
    assert extract_title_from_markdown(markdown) == "从文本到结构"


def test_strip_leading_title_removes_duplicate_title_line():
    markdown = "从 Harness 到 Environment? 这波 Agent 创业还有护城河吗？\n\n第一段\n第二段"
    assert strip_leading_title(markdown, "从 Harness 到 Environment？ 这波 Agent 创业还有护城河吗？") == "第一段\n第二段"


def test_extract_title_from_markdown_ignores_frontmatter():
    markdown = (
        "---\n"
        "title: 旧标题\n"
        "---\n\n"
        "# 新标题\n\n"
        "正文内容"
    )
    assert extract_title_from_markdown(markdown) == "新标题"
    assert strip_frontmatter(markdown).startswith("# 新标题")


def test_build_note_content_includes_links_and_frontmatter():
    content = build_note_content(
        title="从文本到结构",
        body_markdown="# 从文本到结构\n\n正文",
        source_url="https://example.com/source",
        reading_view_url="http://localhost:3001/process/proj_1?mode=graph&view=reading",
        project_url="http://localhost:3001/process/proj_1",
        project_id="proj_1",
        graph_id="graph_1",
        screenshot_path="/tmp/test.png",
        processed_at="2026-04-03T18:00:00",
    )
    assert "reading_view_url:" in content
    assert "> 阅读视图：[知识工作台]" in content
    assert "# 从文本到结构" in content
    assert "正文" in content


def test_build_urls_use_expected_query_format():
    assert build_project_url("proj_1", "http://localhost:3001") == "http://localhost:3001/process/proj_1"
    assert build_reading_view_url("proj_1", "http://localhost:3001") == (
        "http://localhost:3001/process/proj_1?mode=graph&view=reading"
    )


def test_pipeline_disables_env_proxies_for_loopback_backend(tmp_path):
    session = requests.Session()
    assert session.trust_env is True

    ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="http://127.0.0.1:5001",
        fetch_script_path="/tmp/fetch.py",
        session=session,
    )

    assert session.trust_env is False


def test_pipeline_keeps_env_proxies_for_remote_backend(tmp_path):
    session = requests.Session()
    assert session.trust_env is True

    ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="https://backend.example.com",
        fetch_script_path="/tmp/fetch.py",
        session=session,
    )

    assert session.trust_env is True


def test_fetch_markdown_from_url_rejects_feishu_applink(tmp_path):
    def unexpected_command(*args, **kwargs):
        raise AssertionError("command runner should not be called for Feishu applink")

    pipeline = ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="http://localhost:5001",
        fetch_script_path="/tmp/fetch.py",
        note_subdir="知识工作台/微信文章",
        session=_FakeSession(),
        command_runner=unexpected_command,
        sleep_func=lambda _: None,
    )

    try:
        pipeline._fetch_markdown_from_url(
            "https://applink.feishu.cn/client/message/link/open?token=test"
        )
    except RuntimeError as exc:
        assert "不是实际微信文章链接" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for Feishu applink")


def test_fetch_markdown_from_url_uses_current_python_for_python_scripts(tmp_path):
    commands = []

    class _Result:
        returncode = 0
        stdout = "# 标题\n\n" + ("正文" * 120)
        stderr = ""

    def fake_command_runner(command, capture_output=True, text=True, timeout=None):
        commands.append(command)
        return _Result()

    pipeline = ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="http://localhost:5001",
        fetch_script_path="/tmp/fetch.py",
        note_subdir="知识工作台/微信文章",
        session=_FakeSession(),
        command_runner=fake_command_runner,
        sleep_func=lambda _: None,
    )

    markdown = pipeline._fetch_markdown_from_url("https://mp.weixin.qq.com/s/example")

    assert markdown.startswith("# 标题")
    assert commands == [[
        str(Path(sys.executable).resolve()),
        str(Path("/tmp/fetch.py").resolve()),
        "https://mp.weixin.qq.com/s/example",
        "60000",
        "--stealth",
    ]]


def test_fetch_markdown_from_url_executes_wrapper_directly(tmp_path):
    commands = []

    class _Result:
        returncode = 0
        stdout = "# 标题\n\n" + ("正文" * 120)
        stderr = ""

    def fake_command_runner(command, capture_output=True, text=True, timeout=None):
        commands.append(command)
        return _Result()

    wrapper = tmp_path / "fetch.sh"
    wrapper.write_text("#!/bin/sh\n", encoding="utf-8")
    wrapper.chmod(0o755)

    pipeline = ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="http://localhost:5001",
        fetch_script_path=wrapper,
        note_subdir="知识工作台/微信文章",
        session=_FakeSession(),
        command_runner=fake_command_runner,
        sleep_func=lambda _: None,
    )

    markdown = pipeline._fetch_markdown_from_url("https://example.com/article")

    assert markdown.startswith("# 标题")
    assert commands == [[str(wrapper.resolve()), "https://example.com/article", "60000"]]


def _attach_list_handler(logger_name: str):
    import logging

    records: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _ListHandler(level=logging.WARNING)
    target = logging.getLogger(logger_name)
    target.addHandler(handler)
    return records, (lambda: target.removeHandler(handler))


def test_fetch_markdown_from_url_warns_when_markdown_exceeds_long_article_threshold(
    tmp_path,
):
    long_body = "# 长文标题\n\n" + ("这是一段正文内容" * 4000)
    assert len(long_body) > 30000

    class _Result:
        returncode = 0
        stdout = long_body
        stderr = ""

    def fake_command_runner(command, capture_output=True, text=True, timeout=None):
        return _Result()

    pipeline = ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="http://localhost:5001",
        fetch_script_path="/tmp/fetch.py",
        note_subdir="知识工作台/微信文章",
        session=_FakeSession(),
        command_runner=fake_command_runner,
        sleep_func=lambda _: None,
    )

    records, detach = _attach_list_handler("mirofish.article_workspace_pipeline")
    try:
        pipeline._fetch_markdown_from_url("https://example.com/very-long-article")
    finally:
        detach()

    warnings = [r for r in records if r.levelname == "WARNING"]
    assert any("长文" in r.getMessage() for r in warnings), (
        f"expected a 长文 warning, got: {[r.getMessage() for r in warnings]}"
    )


def test_fetch_markdown_from_url_does_not_warn_for_normal_article(tmp_path):
    normal_body = "# 标题\n\n" + ("普通正文" * 200)
    assert len(normal_body) < 30000

    class _Result:
        returncode = 0
        stdout = normal_body
        stderr = ""

    def fake_command_runner(command, capture_output=True, text=True, timeout=None):
        return _Result()

    pipeline = ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="http://localhost:5001",
        fetch_script_path="/tmp/fetch.py",
        note_subdir="知识工作台/微信文章",
        session=_FakeSession(),
        command_runner=fake_command_runner,
        sleep_func=lambda _: None,
    )

    records, detach = _attach_list_handler("mirofish.article_workspace_pipeline")
    try:
        pipeline._fetch_markdown_from_url("https://example.com/normal-article")
    finally:
        detach()

    assert not any("长文" in r.getMessage() for r in records)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.task_calls = 0
        self.build_payload = None

    def post(self, url, data=None, files=None, json=None, timeout=None):
        if url.endswith("/api/graph/ontology/generate"):
            return _FakeResponse({"success": True, "data": {"project_id": "proj_test"}})
        if url.endswith("/api/graph/build"):
            self.build_payload = json
            return _FakeResponse({"success": True, "data": {"task_id": "task_test"}})
        raise AssertionError(f"unexpected POST url: {url}")

    def get(self, url, timeout=None):
        if url.endswith("/api/graph/task/task_test"):
            self.task_calls += 1
            if self.task_calls == 1:
                return _FakeResponse({"success": True, "data": {"status": "processing", "message": "处理中"}})
            return _FakeResponse({"success": True, "data": {"status": "completed", "message": "完成"}})
        if url.endswith("/api/graph/project/proj_test"):
            return _FakeResponse({"success": True, "data": {"graph_id": "mirofish_test"}})
        raise AssertionError(f"unexpected GET url: {url}")


def test_pipeline_process_markdown_file_updates_note_and_returns_links(tmp_path):
    markdown_path = tmp_path / "article.md"
    markdown_path.write_text(
        "---\n"
        "title: 旧标题\n"
        "---\n\n"
        "# 示例文章\n\n"
        "正文内容",
        encoding="utf-8",
    )

    screenshots = []

    def fake_command_runner(command, capture_output=True, text=True, timeout=None):
        if command[:3] == ["npx", "playwright", "screenshot"]:
            screenshot_path = Path(command[-1])
            screenshot_path.write_bytes(b"png")
            screenshots.append(str(screenshot_path))
            class _Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return _Result()
        raise AssertionError(f"unexpected command: {command}")

    session = _FakeSession()

    pipeline = ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="http://localhost:5001",
        fetch_script_path="/tmp/fetch.py",
        note_subdir="知识工作台/微信文章",
        session=session,
        command_runner=fake_command_runner,
        sleep_func=lambda _: None,
    )

    result = pipeline.process_markdown_file(
        markdown_file=markdown_path,
        source_url="https://example.com/article",
    )

    note_path = Path(result.md_path)
    assert note_path.exists()
    note_text = note_path.read_text(encoding="utf-8")
    assert "reading_view_url:" in note_text
    assert "http://localhost:3001/process/proj_test?mode=graph&view=reading" in note_text
    assert "title: 旧标题" not in note_text
    assert "# 示例文章" in note_text
    assert result.project_id == "proj_test"
    assert result.graph_id == "mirofish_test"
    assert screenshots
    assert session.build_payload["chunk_size"] == 900
    assert session.build_payload["chunk_overlap"] == 120


def test_pipeline_process_markdown_file_continues_when_screenshot_times_out(tmp_path):
    markdown_path = tmp_path / "article.md"
    markdown_path.write_text("# 示例文章\n\n正文内容", encoding="utf-8")

    def fake_command_runner(command, capture_output=True, text=True, timeout=None):
        if command[:3] == ["npx", "playwright", "screenshot"]:
            raise subprocess.TimeoutExpired(cmd=command, timeout=timeout or 0)
        raise AssertionError(f"unexpected command: {command}")

    pipeline = ArticleWorkspacePipeline(
        vault_root=tmp_path / "vault",
        frontend_base_url="http://localhost:3001",
        backend_base_url="http://localhost:5001",
        fetch_script_path="/tmp/fetch.py",
        note_subdir="知识工作台/微信文章",
        session=_FakeSession(),
        command_runner=fake_command_runner,
        sleep_func=lambda _: None,
    )

    result = pipeline.process_markdown_file(
        markdown_file=markdown_path,
        source_url="https://example.com/article",
    )

    note_text = Path(result.md_path).read_text(encoding="utf-8")
    assert "reading_view_url:" in note_text
    assert "project_id: proj_test" in note_text
    assert "reading_view_screenshot:" not in note_text
    assert result.reading_view_screenshot_path == ""
