"""
文章 -> 知识工作台 工作流

职责：
1. 抓取网页正文或读取本地 Markdown
2. 生成并保存 OB 笔记中的 Markdown
3. 调用知识工作台后端 API 生成项目与图谱
4. 生成阅读视图链接与截图
5. 将阅读视图链接回写到笔记头部
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import requests


DEFAULT_NOTE_SUBDIR = "知识工作台/微信文章"
DEFAULT_BUILD_CHUNK_SIZE = 900
DEFAULT_BUILD_CHUNK_OVERLAP = 120
READING_VIEW_SCREENSHOT_TIMEOUT_SECONDS = 90
LONG_ARTICLE_WARN_THRESHOLD = 30000
DEFAULT_SIMULATION_REQUIREMENT = (
    "请将这篇文章整理为知识工作台中的可阅读知识结构，优先抽取高价值实体与关系，"
    "输出适合阅读视图展示的主线骨架，并尽量保留问题、方案、架构、机制、技术、指标与案例。"
)
WECHAT_RATE_LIMIT_MARKERS = (
    "Refreshing too often",
    "Verification Code",
)
FRONTMATTER_BLOCK_RE = re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|$)", re.DOTALL)
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


@dataclass
class ArticleWorkspaceResult:
    title: str
    md_path: str
    project_id: str
    graph_id: str
    project_url: str
    reading_view_url: str
    reading_view_screenshot_path: str
    status_summary: str
    source_url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sanitize_note_title(title: str, max_length: int = 90) -> str:
    cleaned = re.sub(r"\s+", " ", title.strip())
    replacements = {
        "/": "／",
        "\\": "＼",
        ":": "：",
        "*": "＊",
        "?": "？",
        "\"": "”",
        "<": "《",
        ">": "》",
        "|": "｜",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.rstrip(".。 ")
    if not cleaned:
        cleaned = "未命名文章"
    return cleaned[:max_length].rstrip()


def extract_title_from_markdown(markdown: str) -> str:
    lines = strip_frontmatter(markdown).splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return sanitize_note_title(stripped.lstrip("#").strip())
        if stripped.startswith("![](") or stripped.startswith("!["):
            continue
        if stripped.startswith(">"):
            continue
        candidate = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", stripped)
        candidate = re.sub(r"[*_`~]", "", candidate).strip()
        if candidate:
            return sanitize_note_title(candidate)
    return "未命名文章"


def strip_frontmatter(markdown: str) -> str:
    match = FRONTMATTER_BLOCK_RE.match(markdown)
    if not match:
        return markdown
    return markdown[match.end():].lstrip()


def _normalize_title_for_compare(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = normalized.replace("？", "?").replace("！", "!").replace("：", ":")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def strip_leading_title(markdown: str, title: str) -> str:
    lines = strip_frontmatter(markdown).splitlines()
    started = False
    kept: list[str] = []
    normalized_title = _normalize_title_for_compare(title)

    for line in lines:
        stripped = line.strip()
        if not started:
            if not stripped:
                continue
            normalized_line = _normalize_title_for_compare(stripped.lstrip("#").strip())
            if normalized_line == normalized_title:
                started = True
                continue
            started = True
        kept.append(line)

    return "\n".join(kept).strip()


def build_project_url(project_id: str, frontend_base_url: str) -> str:
    return f"{frontend_base_url.rstrip('/')}/process/{project_id}"


def build_reading_view_url(project_id: str, frontend_base_url: str) -> str:
    return f"{frontend_base_url.rstrip('/')}/process/{project_id}?mode=graph&view=reading"


def build_note_content(
    *,
    title: str,
    body_markdown: str,
    source_url: Optional[str],
    reading_view_url: Optional[str],
    project_url: Optional[str],
    project_id: Optional[str],
    graph_id: Optional[str],
    screenshot_path: Optional[str],
    processed_at: Optional[str] = None,
) -> str:
    frontmatter_lines = ["---"]
    if source_url:
        frontmatter_lines.append(f"source_url: {source_url}")
    if reading_view_url:
        frontmatter_lines.append(f"reading_view_url: {reading_view_url}")
    if project_url:
        frontmatter_lines.append(f"project_url: {project_url}")
    if project_id:
        frontmatter_lines.append(f"project_id: {project_id}")
    if graph_id:
        frontmatter_lines.append(f"graph_id: {graph_id}")
    if screenshot_path:
        frontmatter_lines.append(f"reading_view_screenshot: {screenshot_path}")
    if processed_at:
        frontmatter_lines.append(f"processed_at: {processed_at}")
    frontmatter_lines.extend(["workflow: 知识工作台文章整理", "---"])

    subtitle_lines = []
    source_label = "微信原文" if source_url and "mp.weixin.qq.com" in source_url else "原文链接"
    if source_url:
        subtitle_lines.append(f"> 来源：[{source_label}]({source_url})")
    if reading_view_url:
        subtitle_lines.append(f"> 阅读视图：[知识工作台]({reading_view_url})")
    if project_url:
        subtitle_lines.append(f"> 项目页面：[项目链接]({project_url})")

    body = strip_leading_title(body_markdown, title)
    sections = [
        "\n".join(frontmatter_lines),
        f"# {title}",
    ]
    if subtitle_lines:
        sections.append("\n".join(subtitle_lines))
    if body:
        sections.append(body)
    return "\n\n".join(section for section in sections if section).strip() + "\n"


def _is_loopback_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.hostname or "").strip().lower() in _LOOPBACK_HOSTS


class ArticleWorkspacePipeline:
    def __init__(
        self,
        *,
        vault_root: str | Path,
        frontend_base_url: str,
        backend_base_url: str,
        fetch_script_path: str | Path,
        note_subdir: str = DEFAULT_NOTE_SUBDIR,
        build_chunk_size: int = DEFAULT_BUILD_CHUNK_SIZE,
        build_chunk_overlap: int = DEFAULT_BUILD_CHUNK_OVERLAP,
        session: Optional[requests.Session] = None,
        command_runner: Optional[Callable[..., subprocess.CompletedProcess[str]]] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.vault_root = Path(vault_root).expanduser().resolve()
        self.frontend_base_url = frontend_base_url.rstrip("/")
        self.backend_base_url = backend_base_url.rstrip("/")
        self.fetch_script_path = Path(fetch_script_path).expanduser().resolve()
        self.python_executable = Path(sys.executable).expanduser().resolve()
        self.note_subdir = note_subdir
        self.build_chunk_size = max(int(build_chunk_size or DEFAULT_BUILD_CHUNK_SIZE), 200)
        self.build_chunk_overlap = max(int(build_chunk_overlap or DEFAULT_BUILD_CHUNK_OVERLAP), 0)
        self.session = session or requests.Session()
        # The desktop environment may export HTTP(S)_PROXY without NO_PROXY.
        # For loopback backend calls that proxy can time out long requests
        # (ontology/build) and return a false 503 while the local Flask
        # handler keeps running. Force direct connections to the local backend.
        if _is_loopback_http_url(self.backend_base_url) and hasattr(self.session, "trust_env"):
            self.session.trust_env = False
        self.command_runner = command_runner or subprocess.run
        self.sleep_func = sleep_func or time.sleep

    def process_url(
        self,
        *,
        url: str,
        simulation_requirement: str = DEFAULT_SIMULATION_REQUIREMENT,
        target_folder: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> ArticleWorkspaceResult:
        markdown = self._fetch_markdown_from_url(url)
        return self._process_markdown(
            markdown=markdown,
            source_url=url,
            simulation_requirement=simulation_requirement,
            target_folder=target_folder,
            project_name=project_name,
        )

    def process_markdown_file(
        self,
        *,
        markdown_file: str | Path,
        source_url: Optional[str] = None,
        simulation_requirement: str = DEFAULT_SIMULATION_REQUIREMENT,
        target_folder: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> ArticleWorkspaceResult:
        markdown_path = Path(markdown_file).expanduser().resolve()
        markdown = markdown_path.read_text(encoding="utf-8")
        return self._process_markdown(
            markdown=markdown,
            source_url=source_url,
            simulation_requirement=simulation_requirement,
            target_folder=target_folder,
            project_name=project_name,
        )

    def _process_markdown(
        self,
        *,
        markdown: str,
        source_url: Optional[str],
        simulation_requirement: str,
        target_folder: Optional[str],
        project_name: Optional[str],
    ) -> ArticleWorkspaceResult:
        normalized_markdown = strip_frontmatter(markdown).strip()
        title = project_name or extract_title_from_markdown(normalized_markdown)
        note_path = self._resolve_note_path(title, target_folder)
        upload_markdown = self._build_upload_markdown(title, normalized_markdown)
        self._write_note(
            note_path,
            title=title,
            body_markdown=normalized_markdown,
            source_url=source_url,
            reading_view_url=None,
            project_url=None,
            project_id=None,
            graph_id=None,
            screenshot_path=None,
        )

        project_id = self._create_project_from_markdown(
            title=title,
            upload_markdown=upload_markdown,
            simulation_requirement=simulation_requirement,
        )
        graph_id = self._build_graph(project_id, title)

        project_url = build_project_url(project_id, self.frontend_base_url)
        reading_view_url = build_reading_view_url(project_id, self.frontend_base_url)
        # Persist the durable project/read-view links before the optional
        # screenshot step so a slow screenshot cannot leave the note in the
        # pre-build placeholder state.
        self._write_note(
            note_path,
            title=title,
            body_markdown=normalized_markdown,
            source_url=source_url,
            reading_view_url=reading_view_url,
            project_url=project_url,
            project_id=project_id,
            graph_id=graph_id,
            screenshot_path=None,
        )
        screenshot_path = str(note_path.with_suffix(".reading-view.png"))
        screenshot_captured = self._capture_reading_view(reading_view_url, screenshot_path)
        persisted_screenshot_path = screenshot_path if screenshot_captured else None

        if persisted_screenshot_path:
            self._write_note(
                note_path,
                title=title,
                body_markdown=normalized_markdown,
                source_url=source_url,
                reading_view_url=reading_view_url,
                project_url=project_url,
                project_id=project_id,
                graph_id=graph_id,
                screenshot_path=persisted_screenshot_path,
            )

        return ArticleWorkspaceResult(
            title=title,
            md_path=str(note_path),
            project_id=project_id,
            graph_id=graph_id,
            project_url=project_url,
            reading_view_url=reading_view_url,
            reading_view_screenshot_path=screenshot_path if screenshot_captured else "",
            status_summary="文章已完成整理，阅读视图可直接打开。",
            source_url=source_url,
        )

    def _fetch_markdown_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.netloc == "applink.feishu.cn" and parsed.path == "/client/message/link/open":
            raise RuntimeError(
                "收到的是飞书消息中转链接，不是实际微信文章链接；请传递 mp.weixin.qq.com 原始链接。"
            )

        if self.fetch_script_path.suffix == ".py":
            command = [
                str(self.python_executable),
                str(self.fetch_script_path),
                url,
                "60000",
            ]
        else:
            command = [
                str(self.fetch_script_path),
                url,
                "60000",
            ]
        if "mp.weixin.qq.com" in url:
            command.append("--stealth")

        result = self.command_runner(command, capture_output=True, text=True)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            raise RuntimeError(f"抓取失败: {stderr or stdout or '未知错误'}")

        if any(marker in stdout for marker in WECHAT_RATE_LIMIT_MARKERS):
            raise RuntimeError("微信文章抓取被平台限流，请稍后重试或改用已保存的 Markdown。")

        if len(stdout) < 200:
            raise RuntimeError("抓取结果过短，无法作为有效文章内容。")

        if len(stdout) > LONG_ARTICLE_WARN_THRESHOLD:
            import logging as _logging
            _logging.getLogger("mirofish.article_workspace_pipeline").warning(
                "长文告警：url=%s 抓取到 %d 字符，按 chunk_size=%d 预计 %d 块，"
                "LLM 抽取可能耗时较长，watchdog 超时上限请检查 "
                "AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS。",
                url,
                len(stdout),
                DEFAULT_BUILD_CHUNK_SIZE,
                max(1, len(stdout) // DEFAULT_BUILD_CHUNK_SIZE),
            )

        return stdout

    def _resolve_note_path(self, title: str, target_folder: Optional[str]) -> Path:
        now = datetime.now()
        folder = Path(target_folder) if target_folder else Path(self.note_subdir) / now.strftime("%Y-%m")
        if not folder.is_absolute():
            folder = self.vault_root / folder
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{sanitize_note_title(title)}.md"
        return folder / filename

    def _build_upload_markdown(self, title: str, markdown: str) -> str:
        body = strip_leading_title(markdown, title)
        if body:
            return f"# {title}\n\n{body}\n"
        return f"# {title}\n"

    def _write_note(
        self,
        note_path: Path,
        *,
        title: str,
        body_markdown: str,
        source_url: Optional[str],
        reading_view_url: Optional[str],
        project_url: Optional[str],
        project_id: Optional[str],
        graph_id: Optional[str],
        screenshot_path: Optional[str],
    ) -> None:
        processed_at = datetime.now().isoformat(timespec="seconds")
        content = build_note_content(
            title=title,
            body_markdown=body_markdown,
            source_url=source_url,
            reading_view_url=reading_view_url,
            project_url=project_url,
            project_id=project_id,
            graph_id=graph_id,
            screenshot_path=screenshot_path,
            processed_at=processed_at,
        )
        note_path.write_text(content, encoding="utf-8")

    def _create_project_from_markdown(
        self,
        *,
        title: str,
        upload_markdown: str,
        simulation_requirement: str,
    ) -> str:
        with tempfile.TemporaryDirectory(prefix="knowledge-workspace-") as temp_dir:
            temp_path = Path(temp_dir) / f"{sanitize_note_title(title)}.md"
            temp_path.write_text(upload_markdown, encoding="utf-8")

            with temp_path.open("rb") as handle:
                response = self.session.post(
                    f"{self.backend_base_url}/api/graph/ontology/generate",
                    data={
                        "simulation_requirement": simulation_requirement,
                        "project_name": title,
                    },
                    files={
                        "files": (temp_path.name, handle, "text/markdown"),
                    },
                    # 2026-04-16: Bailian/qwen3.5-plus 偶发把 ontology generate
                    # 推到 5min 以上（特别是和 graph build 并跑、Bailian
                    # semaphore 被吃满时）。原 300s 太紧，bump 到 600s 给
                    # provider 端的尾延迟留出余量；watchdog 仍在外层兜底。
                    timeout=600,
                )

        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(payload.get("error") or "本体生成失败")

        data = payload["data"]
        project_id = data.get("project_id")
        if not project_id:
            raise RuntimeError("本体生成成功，但未返回 project_id")
        return project_id

    def _build_graph(self, project_id: str, graph_name: str) -> str:
        response = self.session.post(
            f"{self.backend_base_url}/api/graph/build",
            json={
                "project_id": project_id,
                "graph_name": graph_name,
                "chunk_size": self.build_chunk_size,
                "chunk_overlap": self.build_chunk_overlap,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(payload.get("error") or "图谱构建任务启动失败")

        task_id = payload["data"]["task_id"]
        self._poll_task(task_id, project_id=project_id)

        project_response = self.session.get(
            f"{self.backend_base_url}/api/graph/project/{project_id}",
            timeout=60,
        )
        project_response.raise_for_status()
        project_payload = project_response.json()
        if not project_payload.get("success"):
            raise RuntimeError(project_payload.get("error") or "项目查询失败")

        graph_id = project_payload["data"].get("graph_id")
        if not graph_id:
            raise RuntimeError("图谱构建完成，但项目中没有 graph_id")
        return graph_id

    def _poll_task(
        self,
        task_id: str,
        *,
        project_id: str,
        timeout_seconds: int = 1800,
        interval_seconds: int = 5,
    ) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response = self.session.get(
                f"{self.backend_base_url}/api/graph/task/{task_id}",
                timeout=60,
            )
            if response.status_code == 404:
                if self._check_project_completion(project_id):
                    return
                self.sleep_func(interval_seconds)
                continue

            response.raise_for_status()
            payload = response.json()
            if not payload.get("success"):
                if "任务不存在" in (payload.get("error") or "") and self._check_project_completion(project_id):
                    return
                raise RuntimeError(payload.get("error") or "任务查询失败")

            task = payload["data"]
            status = task.get("status")
            if status == "completed":
                return
            if status == "failed":
                raise RuntimeError(task.get("message") or task.get("error") or "图谱构建失败")
            self.sleep_func(interval_seconds)

        raise TimeoutError(f"等待图谱构建超时: {task_id}")

    def _check_project_completion(self, project_id: str) -> bool:
        response = self.session.get(
            f"{self.backend_base_url}/api/graph/project/{project_id}",
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            return False
        project = payload["data"]
        status = project.get("status")
        if status == "graph_completed" and project.get("graph_id"):
            return True
        if status == "failed":
            raise RuntimeError(project.get("error") or "图谱构建失败")
        return False

    def _capture_reading_view(self, reading_view_url: str, screenshot_path: str) -> bool:
        """尝试为阅读视图截屏。

        2026-04-12 修复：截图失败 **不再致命**。

        此前如果前端开发服务器不在预期端口（硬编码 127.0.0.1:3001），
        playwright 会抛 ERR_CONNECTION_REFUSED，整个 process_url 抛到
        pipeline_runner 的 except，后面的 concept / registry / theme 三
        个 phase2 阶段全部被跳过。用户看到 UI 上"概念/已确认/已链接/
        主题簇"全是 0，但 Neo4j 里图谱其实已经落库了。

        截图只是一个"锦上添花"的缓存产物，数据平面不依赖它。失败就
        降级成 warning，让 phase2 继续跑。
        """
        output_path = Path(screenshot_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "npx",
            "playwright",
            "screenshot",
            "--wait-for-selector",
            ".graph-svg",
            "--wait-for-timeout",
            "5000",
            "--viewport-size",
            "1600,1000",
            reading_view_url,
            screenshot_path,
        ]
        try:
            result = self.command_runner(
                command,
                capture_output=True,
                text=True,
                timeout=READING_VIEW_SCREENSHOT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            import logging as _logging
            _logging.getLogger("mirofish.article_workspace_pipeline").warning(
                "阅读视图截图降级 (非致命): 调用 playwright 超时(timeout=%ss): %s",
                READING_VIEW_SCREENSHOT_TIMEOUT_SECONDS,
                exc,
            )
            return False
        except Exception as exc:  # noqa: BLE001
            import logging as _logging
            _logging.getLogger("mirofish.article_workspace_pipeline").warning(
                "阅读视图截图降级 (非致命): 调用 playwright 失败: %s", exc
            )
            return False

        if result.returncode != 0:
            import logging as _logging
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            _logging.getLogger("mirofish.article_workspace_pipeline").warning(
                "阅读视图截图降级 (非致命): returncode=%s stderr=%s stdout=%s",
                result.returncode,
                stderr[:500],
                stdout[:500],
            )
            return False
        if not output_path.exists():
            import logging as _logging
            _logging.getLogger("mirofish.article_workspace_pipeline").warning(
                "阅读视图截图降级 (非致命): playwright 返回成功但未生成文件: %s",
                screenshot_path,
            )
            return False
        return True
