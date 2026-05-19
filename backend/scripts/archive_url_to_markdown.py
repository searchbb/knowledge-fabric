#!/usr/bin/env python3
"""Archive one URL as a local Markdown clipping without queueing graph parsing.

This intentionally reuses Knowledge Fabric Center's URL -> Markdown fetch path,
but does not call ``ArticleWorkspacePipeline.process_url()``. It only writes a
standalone Markdown file plus local image assets.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from urllib.parse import quote, urlparse


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.article_workspace_pipeline import (  # noqa: E402
    ArticleWorkspacePipeline,
    extract_title_from_markdown,
    sanitize_note_title,
    strip_leading_title,
)


DEFAULT_FETCH_SCRIPT = Path("/Users/mac/.openclaw/workspace/skills/web-content-fetcher/fetch.sh")
DEFAULT_VAULT_ROOT = Path(os.environ.get("KNOWLEDGE_WORKSPACE_VAULT_ROOT", "~/Downloads/OB笔记")).expanduser()
DEFAULT_OUTPUT_DIR = DEFAULT_VAULT_ROOT / "Clippings"
IMAGE_MD_RE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")


def _run_with_timeout(command, **kwargs):
    return subprocess.run(command, timeout=240, **kwargs)


def _safe_filename_stem(title: str, url: str) -> str:
    base = sanitize_note_title(title)
    digest = sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{base}-{digest}"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}-{timestamp}{path.suffix}")


def _guess_extension(url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext

    query = parsed.query.lower()
    if "wx_fmt=png" in query:
        return ".png"
    if "wx_fmt=webp" in query:
        return ".webp"
    if "wx_fmt=gif" in query:
        return ".gif"
    if "wx_fmt=jpeg" in query or "wx_fmt=jpg" in query:
        return ".jpg"

    guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
    if guessed == ".jpe":
        return ".jpg"
    return guessed or ".jpg"


def _download_image(url: str, dest: Path, referer: str) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            ),
            "Referer": referer,
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        content_type = response.headers.get("Content-Type")
        ext = _guess_extension(url, content_type)
        final_dest = dest.with_suffix(ext)
        with final_dest.open("wb") as handle:
            handle.write(response.read())


def _localize_markdown_images(markdown: str, *, asset_dir: Path, output_dir: Path, source_url: str) -> tuple[str, list[str]]:
    image_urls: list[str] = []
    for match in IMAGE_MD_RE.finditer(markdown):
        url = match.group(2).strip()
        if url.startswith(("http://", "https://")) and url not in image_urls:
            image_urls.append(url)

    if not image_urls:
        return markdown, []

    asset_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, str] = {}
    saved: list[str] = []
    for index, image_url in enumerate(image_urls, start=1):
        dest_without_ext = asset_dir / f"{index:02d}-image"
        try:
            _download_image(image_url, dest_without_ext, referer=source_url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"图片下载失败: {image_url}: {exc}") from exc

        candidates = sorted(asset_dir.glob(f"{index:02d}-image.*"))
        if not candidates:
            raise RuntimeError(f"图片下载后未找到本地文件: {image_url}")
        local_path = candidates[0]
        rel_path = quote(local_path.relative_to(output_dir).as_posix(), safe="/._-")
        replacements[image_url] = rel_path
        saved.append(str(local_path))

    for remote, local in replacements.items():
        markdown = markdown.replace(remote, local)
    return markdown, saved


def archive_url(
    url: str,
    *,
    output_dir: Path,
    fetch_script: Path,
    download_images: bool,
) -> dict:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    vault_root = output_dir.parent

    pipeline = ArticleWorkspacePipeline(
        vault_root=vault_root,
        frontend_base_url="http://localhost:5179",
        backend_base_url="http://localhost:5001",
        fetch_script_path=fetch_script,
        note_subdir=str(output_dir),
        command_runner=_run_with_timeout,
    )
    markdown = pipeline._fetch_markdown_from_url(url)
    title = extract_title_from_markdown(markdown)
    stem = _safe_filename_stem(title, url)
    article_path = _unique_path(output_dir / f"{stem}.md")
    asset_dir = output_dir / "assets" / article_path.stem

    body = strip_leading_title(markdown, title)
    saved_images: list[str] = []
    if download_images:
        body, saved_images = _localize_markdown_images(
            body,
            asset_dir=asset_dir,
            output_dir=output_dir,
            source_url=url,
        )

    archived_at = datetime.now().astimezone().isoformat(timespec="seconds")
    content = "\n".join(
        [
            "---",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            f"source_url: {json.dumps(url, ensure_ascii=False)}",
            f"archived_at: {json.dumps(archived_at, ensure_ascii=False)}",
            "workflow: clippings_archive",
            "---",
            "",
            f"# {title}",
            "",
            f"> 来源：[原文链接]({url})",
            "",
            body.strip(),
            "",
        ]
    )
    article_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "url": url,
        "title": title,
        "md_path": str(article_path),
        "image_count": len(saved_images),
        "images": saved_images,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL to archive")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for Markdown clippings")
    parser.add_argument("--fetch-script", default=str(DEFAULT_FETCH_SCRIPT), help="KFC fetch wrapper path")
    parser.add_argument("--no-images", action="store_true", help="Do not download and localize images")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = archive_url(
            args.url,
            output_dir=Path(args.output_dir),
            fetch_script=Path(args.fetch_script),
            download_images=not args.no_images,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc), "url": args.url}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["md_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
