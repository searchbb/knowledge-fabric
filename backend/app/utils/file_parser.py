"""
文件解析工具
支持PDF、Markdown、TXT文件的文本提取
"""

import os
import re
from pathlib import Path
from typing import List, Optional

FRONTMATTER_BLOCK_RE = re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|$)", re.DOTALL)
STRUCTURED_SECTION_CHUNK_CAP = 900


def _read_text_with_fallback(file_path: str) -> str:
    """
    读取文本文件，UTF-8失败时自动探测编码。
    
    采用多级回退策略：
    1. 首先尝试 UTF-8 解码
    2. 使用 charset_normalizer 检测编码
    3. 回退到 chardet 检测编码
    4. 最终使用 UTF-8 + errors='replace' 兜底
    
    Args:
        file_path: 文件路径
        
    Returns:
        解码后的文本内容
    """
    data = Path(file_path).read_bytes()
    
    # 首先尝试 UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # 尝试使用 charset_normalizer 检测编码
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # 回退到 chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # 最终兜底：使用 UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


MARKDOWN_FOOTER_MARKERS = (
    "写留言",
    "阅读原文",
    "继续滑动看下一个",
    "推荐阅读",
    "微信扫一扫关注",
    "分享",
    "点赞",
    "在看",
)

COLLAPSED_CODE_KEYWORDS = (
    "select",
    "from",
    "where",
    "join",
    "group by",
    "order by",
    "limit",
    "with",
    "case when",
    "over (",
    "group_concat",
    "row_number",
    "substring_index",
    "concat(",
)


def _looks_like_collapsed_code_line(line: str) -> bool:
    """Detect long SQL/code lines that leaked out of markdown code fences."""
    normalized = (line or "").strip().lower()
    if len(normalized) < 160:
        return False

    keyword_hits = sum(1 for token in COLLAPSED_CODE_KEYWORDS if token in normalized)
    punctuation_ratio = sum(
        1 for ch in normalized if ch in "()[]_=><,;:`'\""
    ) / max(len(normalized), 1)

    return keyword_hits >= 2 or (keyword_hits >= 1 and punctuation_ratio > 0.08)


def clean_markdown_text(text: str) -> str:
    """
    清洗技术文章 Markdown，去掉图片、公众号噪音和尾部无关内容。
    """
    text = text.replace('\ufeff', '')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('\u00a0', ' ')
    text = FRONTMATTER_BLOCK_RE.sub('', text, count=1).lstrip()

    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    text = re.sub(r'<img\b[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'\1', text)

    cleaned_lines: list[str] = []
    in_code_block = False
    content_line_count = 0

    for raw_line in text.split('\n'):
        stripped = raw_line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if not stripped:
            cleaned_lines.append("")
            continue

        if re.match(r'^原创\s+', stripped):
            continue
        if stripped == "听全文":
            continue
        if re.match(r'^_?\d{4}年\d{1,2}月\d{1,2}日', stripped):
            continue

        if content_line_count > 20 and any(marker in stripped for marker in MARKDOWN_FOOTER_MARKERS):
            break

        line = stripped
        if not line.startswith('#'):
            line = re.sub(r'[`*_~]+', '', line)
        line = re.sub(r'\s+', ' ', line).strip()

        # WeChat exports sometimes flatten fenced SQL/code blocks into huge lines.
        if _looks_like_collapsed_code_line(line):
            continue

        if line:
            cleaned_lines.append(line)
            content_line_count += 1

    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class FileParser:
    """文件解析器"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        从文件中提取文本
        
        Args:
            file_path: 文件路径
            
        Returns:
            提取的文本内容
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        
        raise ValueError(f"无法处理的文件格式: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """从PDF提取文本"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("需要安装PyMuPDF: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """从Markdown提取文本，支持自动编码检测"""
        return clean_markdown_text(_read_text_with_fallback(file_path))
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """从TXT提取文本，支持自动编码检测"""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        从多个文件提取文本并合并
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            合并后的文本
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== 文档 {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== 文档 {i}: {file_path} (提取失败: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def _split_by_length(
    text: str,
    chunk_size: int,
    overlap: int,
) -> List[str]:
    """纯长度切分（带边界检测），作为 section 内的二级切分。"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            for sep in ['\n\n', '。\n', '！\n', '？\n', '.\n', '!\n', '?\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else len(text)
    return chunks


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    结构感知文本切分：先按 Markdown 章节切分，再按长度切分。
    每个 chunk 会带上所属章节的上下文前缀。

    Args:
        text: 原始文本
        chunk_size: 每块的字符数
        overlap: 重叠字符数

    Returns:
        文本块列表
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # ---- 第一级：按 Markdown 标题切分为 sections ----
    import re
    heading_pattern = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)

    sections: List[tuple] = []  # (heading, body)
    last_end = 0
    last_heading = ""

    for match in heading_pattern.finditer(text):
        # 保存上一段
        body = text[last_end:match.start()].strip()
        if body or last_heading:
            sections.append((last_heading, body))
        last_heading = match.group(2).strip()
        last_end = match.end()

    # 最后一段
    body = text[last_end:].strip()
    if body or last_heading:
        sections.append((last_heading, body))

    # 如果没有任何标题结构，回退到纯长度切分
    if len(sections) <= 1:
        return _split_by_length(text, chunk_size, overlap)

    # ---- 合并过短的相邻 section，确保每个 chunk 有足够内容 ----
    # 策略：只合并极短（<200字符）的 section 到相邻 section
    # 保留有实质内容的 section 独立性
    min_standalone = 200  # 短于这个长度的 section 才合并到相邻
    merged_sections: List[tuple] = []
    buffer_heading = ""
    buffer_body = ""

    for heading, body in sections:
        if not body:
            continue
        if buffer_body and len(body) < min_standalone and len(buffer_body) + len(body) < chunk_size:
            # 当前 section 太短，合并到 buffer
            if heading:
                buffer_body += f"\n\n## {heading}\n\n{body}"
            else:
                buffer_body += f"\n\n{body}"
        elif buffer_body and len(buffer_body) < min_standalone:
            # buffer 太短，吸收当前 section
            if heading:
                buffer_body += f"\n\n## {heading}\n\n{body}"
            else:
                buffer_body += f"\n\n{body}"
        else:
            if buffer_body:
                merged_sections.append((buffer_heading, buffer_body))
            buffer_heading = heading
            buffer_body = body

    if buffer_body:
        merged_sections.append((buffer_heading, buffer_body))

    # ---- 第二级：section 内按长度切分，并注入上下文前缀 ----
    chunks = []
    base_chunk_size = min(chunk_size, STRUCTURED_SECTION_CHUNK_CAP)
    for heading, body in merged_sections:
        if not body:
            continue
        prefix = f"--- Section: {heading} ---\n\n" if heading else ""
        # 为 prefix 留出空间
        effective_size = base_chunk_size - len(prefix)
        if effective_size < 200:
            effective_size = max(200, chunk_size - len(prefix))

        sub_chunks = _split_by_length(body, effective_size, overlap)
        for sc in sub_chunks:
            chunks.append(f"{prefix}{sc}" if prefix else sc)

    return chunks if chunks else _split_by_length(text, chunk_size, overlap)
