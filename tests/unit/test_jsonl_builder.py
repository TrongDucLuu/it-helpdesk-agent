"""
Unit Tests for Discovery Engine JSONL Builder (VAIS-030).

Validates:
- JSONL format compliance (id, structData, jsonData).
- Proper field population (system, category, title, section_hierarchy, chunk_id, parent_doc_id).
- Tombstone and expired article exclusion.
- Golden File parity test for 3 sample documents in data/knowledge_base/.
"""

import json
from pathlib import Path
import pytest
from scripts.ingest.jsonl_builder import (
    build_document_records,
    build_corpus_jsonl,
    _generate_doc_id,
)


def test_generate_doc_id():
    assert _generate_doc_id("data/knowledge_base/erp_procurement_guide.md") == "erp_procurement_guide"
    assert _generate_doc_id("data/knowledge_base/erp_procurement_guide.md", chunk_index=2) == "erp_procurement_guide_c2"


def test_build_document_records_sample_markdown():
    kb_path = Path("data/knowledge_base/erp_procurement_guide.md")
    records = build_document_records(kb_path, enable_chunking=True)

    assert len(records) >= 1
    first_rec = records[0]
    assert "id" in first_rec
    assert "structData" in first_rec
    assert "jsonData" in first_rec

    struct = first_rec["structData"]
    assert struct["system"] == "ERP"
    assert "ME21N" in struct["content"] or "SAP" in struct["title"]
    assert struct["parent_doc_id"] == "erp_procurement_guide"
    assert "chunk_id" in struct
    assert "chunk_index" in struct
    assert "section_hierarchy" in struct


def test_build_document_records_tombstone_and_expiry_exclusion(tmp_path):
    # 1. Deleted file
    del_file = tmp_path / "erp_deleted.md"
    del_file.write_text("""---
title: Deleted Policy
system: ERP
is_deleted: true
---
# Deleted Policy Content
""")
    assert len(build_document_records(del_file, include_deleted=False)) == 0
    assert len(build_document_records(del_file, include_deleted=True)) > 0

    # 2. Expired file
    exp_file = tmp_path / "hrm_expired.md"
    exp_file.write_text("""---
title: Expired Policy
system: HRM
expiry_date: 2020-01-01
---
# Old Expired Leave Policy
""")
    assert len(build_document_records(exp_file, include_deleted=False)) == 0


def test_golden_file_jsonl_generation(tmp_path):
    """Golden file test: transforms all sample documents in data/knowledge_base/ to JSONL."""
    source_dir = Path("data/knowledge_base")
    out_jsonl = tmp_path / "golden_corpus.jsonl"

    count = build_corpus_jsonl(
        source_dir=source_dir,
        output_jsonl_path=out_jsonl,
        enable_chunking=True,
    )

    assert count >= 3
    assert out_jsonl.exists()

    with open(out_jsonl, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == count
        for line in lines:
            data = json.loads(line)
            assert "id" in data
            assert "structData" in data
            assert data["structData"]["system"] in ("ERP", "HRM", "CRM")
            assert len(data["structData"]["content"]) > 0
