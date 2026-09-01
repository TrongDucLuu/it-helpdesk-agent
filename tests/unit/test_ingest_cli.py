"""
Unit Tests for Ingestion CLI (VAIS-034).

Verifies:
- CLI execution with --dry-run exits with code 0 and prints sample JSONL.
- Proper backend routing (vertex_ai_search, bigquery, in_memory).
- DLQ record inspection via --show-dlq.
"""

import sys
import subprocess
from pathlib import Path
import pytest


def test_cli_dry_run_vertex_ai_search(tmp_path):
    output_jsonl = tmp_path / "out.jsonl"
    cmd = [
        sys.executable,
        "scripts/ingest_knowledge_base.py",
        "--backend", "vertex_ai_search",
        "--source-dir", "data/knowledge_base",
        "--output-jsonl", str(output_jsonl),
        "--dry-run",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0
    assert "DRY-RUN VERIFICATION" in result.stdout
    assert "Vertex AI Search (Agent Search)" in result.stdout
    assert "Estimated Security Filter:" in result.stdout
    assert output_jsonl.exists()


def test_cli_dry_run_bigquery():
    cmd = [
        sys.executable,
        "scripts/ingest_knowledge_base.py",
        "--backend", "bigquery",
        "--source-dir", "data/knowledge_base",
        "--dry-run",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0
    assert "Target Backend: BigQuery" in result.stderr or "Target Backend: BigQuery" in result.stdout
    assert "All" in result.stderr or "All" in result.stdout


def test_cli_in_memory():
    cmd = [
        sys.executable,
        "scripts/ingest_knowledge_base.py",
        "--backend", "in_memory",
        "--source-dir", "data/knowledge_base",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0
    assert "In-memory validation complete" in result.stderr or "In-memory validation complete" in result.stdout


def test_cli_show_dlq(tmp_path):
    dlq_file = tmp_path / "dlq.jsonl"
    dlq_file.write_text('{"id": "1", "occurred_at": "2026-09-01T12:00:00Z", "stage": "parsing", "file_path": "bad.pdf", "error_message": "Corrupted header"}\n')

    cmd = [
        sys.executable,
        "scripts/ingest_knowledge_base.py",
        "--show-dlq",
        "--dlq-path", str(dlq_file),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0
    assert "Corrupted header" in result.stdout
    assert "bad.pdf" in result.stdout
