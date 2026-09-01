"""
JSONL Builder for Google Cloud Vertex AI Search (Agent Search / Discovery Engine).

Converts enterprise knowledge documents (Markdown, HTML, PDF) into Discovery Engine
compatible JSONL records with rich structData schema and metadata isolation.

Google Cloud Official Documentation:
- Document JSONL Format Reference:
  https://cloud.google.com/generative-ai-app-builder/docs/prepare-data#jsonl
- Structured Data Stores:
  https://cloud.google.com/generative-ai-app-builder/docs/structured-data
- ImportDocuments API:
  https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.services.document_service.DocumentServiceClient#google_cloud_discoveryengine_v1_services_document_service_DocumentServiceClient_import_documents
"""

import os
import json
import re
import hashlib
import logging
from pathlib import Path
from typing import Optional, Any, Union
import datetime

from scripts.ingest.parsers import DocumentParser
from scripts.ingest.chunkers import chunk_by_sections, chunk_text, is_well_structured

logger = logging.getLogger("ingest.jsonl_builder")


def _generate_doc_id(source_path: str, chunk_index: Optional[int] = None) -> str:
    """Generates a clean, deterministic Discovery Engine document ID (^[a-zA-Z0-9-_]+$)."""
    stem = Path(source_path).stem
    # Replace non-alphanumeric/hyphen/underscore with underscore
    clean_stem = re.sub(r"[^a-zA-Z0-9-_]", "_", stem).strip("_")
    if not clean_stem:
        clean_stem = "doc_" + hashlib.sha256(source_path.encode()).hexdigest()[:12]
    
    if chunk_index is not None:
        return f"{clean_stem}_c{chunk_index}"
    return clean_stem


def _extract_system_from_path_or_meta(file_path: Path, meta_system: Optional[str] = None) -> str:
    """Infers system tag (ERP, HRM, CRM) from frontmatter or filename prefix."""
    if meta_system and meta_system.strip():
        return meta_system.strip().upper()
    stem = file_path.stem.upper()
    if stem.startswith("ERP") or "ERP" in stem:
        return "ERP"
    if stem.startswith("HRM") or "HRM" in stem:
        return "HRM"
    if stem.startswith("CRM") or "CRM" in stem:
        return "CRM"
    return "ERP"


def build_document_records(
    file_path: Path,
    enable_chunking: bool = True,
    max_chunk_size: int = 1200,
    overlap: int = 150,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    """
    Parses a single knowledge document and constructs JSONL records conforming to Discovery Engine schema.
    
    Filters out tombstone (is_deleted=True) and expired articles unless include_deleted is True.
    """
    if not file_path.exists() or not file_path.is_file():
        logger.warning("File %s does not exist.", file_path)
        return []

    ext = file_path.suffix.lower()
    sections: list[dict[str, Any]] = []

    if ext in (".md", ".txt"):
        sections = DocumentParser.parse_markdown_or_text(file_path)
    elif ext in (".html", ".htm"):
        sections = DocumentParser.parse_html(file_path)
    elif ext == ".pdf":
        sections = DocumentParser.parse_pdf(file_path)
    else:
        logger.warning("Unsupported file format: %s for %s", ext, file_path)
        return []

    if not sections:
        return []

    # Infer global document metadata from frontmatter or first section
    doc_title = file_path.stem.replace("_", " ").title()
    doc_system = _extract_system_from_path_or_meta(file_path)
    doc_category = "General"
    owner: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    is_deleted = False
    keywords: list[str] = [doc_system.lower(), file_path.stem.lower()]

    # Extract frontmatter if available in first section or raw file
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_head = f.read(2048)
            if raw_head.startswith("---"):
                fm_match = re.match(r"^---\s*\n(.*?)\n---", raw_head, re.DOTALL)
                if fm_match:
                    for line in fm_match.group(1).splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            k = k.strip().lower()
                            v = v.strip().strip("'\"")
                            if k == "title" and v:
                                doc_title = v
                            elif k == "system" and v:
                                doc_system = v.upper()
                            elif k == "category" and v:
                                doc_category = v
                            elif k == "owner" and v:
                                owner = v
                            elif k == "effective_date" and v:
                                effective_date = v
                            elif k == "expiry_date" and v:
                                expiry_date = v
                            elif k == "is_deleted":
                                is_deleted = v.lower() in ("true", "1", "yes")
    except Exception as e:
        logger.debug("Failed to read frontmatter from %s: %s", file_path, e)

    # Check expiration and tombstone
    today = datetime.date.today()
    if is_deleted and not include_deleted:
        logger.info("Skipping deleted article %s during JSONL build.", file_path.name)
        return []

    if expiry_date and not include_deleted:
        try:
            exp_d = datetime.date.fromisoformat(expiry_date[:10])
            if exp_d <= today:
                logger.info("Skipping expired article %s (expired on %s)", file_path.name, exp_d)
                return []
        except Exception:
            pass

    parent_doc_id = _generate_doc_id(str(file_path))
    records: list[dict[str, Any]] = []

    if enable_chunking:
        chunk_items = chunk_by_sections(
            sections=sections,
            max_chunk_size=max_chunk_size,
            overlap=overlap,
            return_metadata=True,
        )
        if not chunk_items:
            # Fallback to full text if chunk_by_sections produced nothing
            full_content = "\n\n".join(s.get("content", "") for s in sections).strip()
            chunk_items = [{"text": full_content, "hierarchy": {"h1": doc_title, "h2": None, "h3": None}}]

        for idx, item in enumerate(chunk_items):
            chunk_text_content = item.get("text", "").strip()
            if not chunk_text_content:
                continue
            chunk_id = _generate_doc_id(str(file_path), chunk_index=idx)
            hierarchy = item.get("hierarchy") or {}

            struct_data = {
                "id": chunk_id,
                "system": doc_system,
                "title": doc_title,
                "category": doc_category,
                "content": chunk_text_content,
                "keywords": keywords,
                "owner": owner or f"{doc_system.lower()}-admin@company.com",
                "source_uri": str(file_path),
                "effective_date": effective_date or "2025-01-01",
                "expiry_date": expiry_date,
                "is_deleted": is_deleted,
                "parent_doc_id": parent_doc_id,
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "section_hierarchy": {
                    "h1": hierarchy.get("h1") or doc_title,
                    "h2": hierarchy.get("h2"),
                    "h3": hierarchy.get("h3"),
                },
            }

            records.append({
                "id": chunk_id,
                "structData": struct_data,
                "jsonData": json.dumps(struct_data, ensure_ascii=False),
            })
    else:
        # Single document record without chunking
        full_content = "\n\n".join(s.get("content", "") for s in sections).strip()
        struct_data = {
            "id": parent_doc_id,
            "system": doc_system,
            "title": doc_title,
            "category": doc_category,
            "content": full_content,
            "keywords": keywords,
            "owner": owner or f"{doc_system.lower()}-admin@company.com",
            "source_uri": str(file_path),
            "effective_date": effective_date or "2025-01-01",
            "expiry_date": expiry_date,
            "is_deleted": is_deleted,
            "parent_doc_id": parent_doc_id,
            "chunk_id": parent_doc_id,
            "chunk_index": 0,
            "section_hierarchy": {
                "h1": doc_title,
                "h2": None,
                "h3": None,
            },
        }
        records.append({
            "id": parent_doc_id,
            "structData": struct_data,
            "jsonData": json.dumps(struct_data, ensure_ascii=False),
        })

    return records


def build_corpus_jsonl(
    source_dir: Union[str, Path],
    output_jsonl_path: Union[str, Path],
    enable_chunking: bool = True,
    max_chunk_size: int = 1200,
    overlap: int = 150,
) -> int:
    """
    Scans source_dir for knowledge documents, transforms them into Discovery Engine JSONL schema,
    and writes to output_jsonl_path.
    
    Returns total document/chunk count written.
    """
    source_path = Path(source_dir)
    out_path = Path(output_jsonl_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not source_path.exists() or not source_path.is_dir():
        raise ValueError(f"Thư mục nguồn không tồn tại: {source_dir}")

    total_count = 0
    with open(out_path, "w", encoding="utf-8") as out_f:
        # Collect supported files
        files = sorted(list(source_path.glob("*.md")) + list(source_path.glob("*.txt")) + list(source_path.glob("*.html")) + list(source_path.glob("*.pdf")))
        for f in files:
            try:
                records = build_document_records(
                    file_path=f,
                    enable_chunking=enable_chunking,
                    max_chunk_size=max_chunk_size,
                    overlap=overlap,
                )
                for rec in records:
                    out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    total_count += 1
            except Exception as e:
                logger.error("Lỗi khi xử lý file %s: %s", f, e)

    logger.info("Hoàn thành sinh JSONL tại %s (tổng cộng %d documents/chunks)", out_path, total_count)
    return total_count
