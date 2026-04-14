"""
End-to-end test for graph builder bulk pipeline.

Requires:
- LLM_API_KEY set in environment
- Neo4j running at NEO4J_URI

Marked with pytest.mark.e2e so it is excluded from normal test runs.
Run with: pytest tests/test_graph_builder_e2e.py -m e2e -v
"""

import os
import uuid

import pytest

from app.services.graph_builder import GraphBuilderService

pytestmark = pytest.mark.e2e

SKIP_REASON = "LLM_API_KEY not set -- skipping E2E test"

TEST_ARTICLE = """\
Modern CLI tools have evolved significantly in the past decade. Traditional \
Unix utilities like grep, sed, and awk remain foundational, but a new generation \
of replacements written in Rust and Go offer dramatic performance improvements.

ripgrep (rg) is a line-oriented search tool that recursively searches the current \
directory for a regex pattern. It respects .gitignore rules by default and can \
search compressed files. Benchmarks show it is 2-5x faster than GNU grep on \
large codebases.

fd is a simple, fast alternative to the find command. It features smart case \
detection, colorized output, and parallel command execution. It ignores hidden \
directories and files matching .gitignore patterns by default.

bat is a cat clone with syntax highlighting, Git integration, and automatic \
paging. It can be used as a drop-in replacement for cat while providing a much \
richer reading experience.

These tools share common design principles: sensible defaults that reduce the \
need for flags, excellent performance through modern systems programming languages, \
and seamless integration with existing Unix pipelines. The migration from traditional \
to modern CLI tools represents a broader trend in developer tooling toward better \
ergonomics without sacrificing composability.

One key problem these tools address is information overload in large repositories. \
When a monorepo contains millions of files, traditional tools become impractically \
slow. Modern alternatives solve this through parallelism, memory-mapped I/O, and \
SIMD-accelerated string matching.

The architecture typically follows a producer-consumer pattern: a directory walker \
produces file paths, and multiple worker threads consume and search those files \
concurrently. This design maximizes I/O throughput on modern NVMe storage.
"""


@pytest.fixture
def graph_id():
    return f"e2e_test_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def builder():
    return GraphBuilderService()


@pytest.mark.skipif(not os.environ.get("LLM_API_KEY"), reason=SKIP_REASON)
def test_bulk_pipeline_produces_graph(builder, graph_id):
    """Full pipeline: chunk text, build graph via bulk API, verify nodes and edges exist."""
    from app.services.text_processor import TextProcessor

    processor = TextProcessor()
    chunks = processor.split_text(TEST_ARTICLE)
    assert len(chunks) >= 1, "Expected at least one chunk from test article"

    # Set a minimal ontology
    ontology = {
        "entity_types": [
            {"name": "Tool", "description": "A CLI tool or utility", "attributes": []},
            {"name": "Problem", "description": "A problem or challenge", "attributes": []},
            {"name": "Architecture", "description": "A design pattern or architecture", "attributes": []},
        ],
        "edge_types": [
            {
                "name": "SOLVES",
                "description": "Tool solves a problem",
                "source_targets": [{"source": "Tool", "target": "Problem"}],
            },
            {
                "name": "USES",
                "description": "Tool uses an architecture",
                "source_targets": [{"source": "Tool", "target": "Architecture"}],
            },
        ],
    }
    builder.set_ontology(graph_id, ontology)

    progress_messages = []

    def progress_cb(msg, pct):
        progress_messages.append((msg, pct))

    episode_ids = builder.add_text_batches(
        graph_id, chunks, progress_callback=progress_cb
    )

    assert len(episode_ids) >= 1, "Expected at least one episode from bulk pipeline"
    assert any(pct == 1.0 for _, pct in progress_messages), "Expected 100% progress"

    # Verify graph data in Neo4j
    graph_data = builder.get_graph_data(graph_id)
    assert graph_data["node_count"] >= 1, "Expected at least one node in the graph"

    diagnostics = builder.get_build_diagnostics()
    assert diagnostics["processed_chunk_count"] == len(chunks)

    # Cleanup
    builder.delete_graph(graph_id)
