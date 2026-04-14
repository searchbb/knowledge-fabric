from app.config import Config
from app.services.text_processor import TextProcessor
from app.utils.file_parser import clean_markdown_text, split_text_into_chunks


def test_clean_markdown_text_removes_noise_and_footer():
    body_lines = "\n".join(f"正文第{i}行" for i in range(1, 23))
    raw = f"""<!-- comment -->
# OpenClaw 可观测体系
![image](https://example.com/image.png)
[参考链接](https://example.com)

```python
print("debug")
```

{body_lines}
写留言
这部分不应该保留
"""

    cleaned = clean_markdown_text(raw)

    assert "<!--" not in cleaned
    assert "image.png" not in cleaned
    assert "print(\"debug\")" not in cleaned
    assert "写留言" not in cleaned
    assert "这部分不应该保留" not in cleaned
    assert "参考链接" in cleaned
    assert "# OpenClaw 可观测体系" in cleaned


def test_text_processor_uses_configured_default_chunk_size():
    # Build text larger than 2x chunk size to guarantee at least 3 chunks
    text = "x" * (Config.DEFAULT_CHUNK_SIZE * 2 + Config.DEFAULT_CHUNK_OVERLAP + 100)
    chunks = TextProcessor.split_text(text)

    assert TextProcessor.split_text.__defaults__ == (
        Config.DEFAULT_CHUNK_SIZE,
        Config.DEFAULT_CHUNK_OVERLAP,
    )
    assert len(chunks) >= 3
    assert len(chunks[0]) <= Config.DEFAULT_CHUNK_SIZE


def test_clean_markdown_text_strips_yaml_frontmatter():
    raw = (
        "---\n"
        "source_url: https://example.com/article\n"
        "processed_at: 2026-04-08T09:25:51\n"
        "---\n\n"
        "# 标题\n\n"
        "正文内容"
    )

    cleaned = clean_markdown_text(raw)

    assert "source_url" not in cleaned
    assert "processed_at" not in cleaned
    assert cleaned.startswith("# 标题")


def test_clean_markdown_text_drops_collapsed_sql_like_lines():
    raw = (
        "# OpenClaw 诊断\n\n"
        "文章解释如何在 SQL 中分析 Agent Trace。\n\n"
        "WITH TaskBoundaries AS ( SELECT * FROM logs WHERE role IS NOT NULL ) "
        "SELECT session_id, GROUP_CONCAT(content ORDER BY row_id) FROM TaskChains "
        "JOIN audits ON audits.chain_id = TaskChains.chain_id ORDER BY created_at DESC;\n\n"
        "> 执行结果：1484 行日志 → 171 个任务链。\n\n"
        "内置 ai_classify 和 ai_generate 函数可直接复用。\n"
    )

    cleaned = clean_markdown_text(raw)

    assert "WITH TaskBoundaries" not in cleaned
    assert "执行结果：1484 行日志" in cleaned
    assert "内置 aiclassify 和 aigenerate 函数可直接复用。" in cleaned


def test_split_text_into_chunks_caps_structured_section_chunk_size():
    structured_markdown = (
        "# 标题\n\n"
        "## 长章节\n\n"
        + ("这是一个很长的段落，包含多个句子。".replace("，", "").replace("。", "") * 500)
    )

    chunks = split_text_into_chunks(structured_markdown, chunk_size=3000, overlap=50)

    assert len(chunks) >= 2
    assert chunks[0].startswith("--- Section: 长章节 ---")
    assert max(len(chunk) for chunk in chunks) < 1400
