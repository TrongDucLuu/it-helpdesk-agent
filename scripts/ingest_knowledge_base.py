#!/usr/bin/env python3
"""
Enterprise Knowledge Base Data Ingestion Pipeline.

Supports multiple backend destinations:
1. vertex_ai_search (default / alias: agent_search): Converts documents into Discovery Engine
   compatible JSONL, uploads to GCS, and executes idempotent ImportDocuments with ReconciliationMode.FULL.
2. bigquery: Performs semantic chunking, dense vector embeddings, and atomic staging/MERGE into BigQuery.
3. in_memory: Validates and parses documents in local memory for unit testing and offline verification.

Usage:
    # Dry-run for Vertex AI Search (generates sample JSONL and expected filter expression, no API calls):
    python scripts/ingest_knowledge_base.py --source-dir data/knowledge_base/ --dry-run

    # Production ingestion into Vertex AI Search / Agent Search:
    python scripts/ingest_knowledge_base.py \
        --backend vertex_ai_search \
        --source-dir data/knowledge_base/ \
        --project-id my-project \
        --location asia-southeast1 \
        --data-store-id it-kb-datastore \
        --gcs-bucket my-kb-corpus-bucket

    # Ingestion into BigQuery Vector Search:
    python scripts/ingest_knowledge_base.py \
        --backend bigquery \
        --source-dir data/knowledge_base/ \
        --project-id my-project \
        --dataset-id it_helpdesk_kb
"""

import os
import sys
import time
import json
import argparse
import logging
from pathlib import Path
from typing import Optional, Any

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.ingest import (
    DocumentParser,
    PARSER_VERSION,
    is_well_structured,
    chunk_by_sections,
    chunk_text,
    process_document,
    CHUNKER_VERSION,
    generate_batch_embeddings,
    generate_text_embedding,
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    get_dlq_schema,
    persist_dead_letter_queue,
    read_persisted_dead_letter_queue,
    ensure_vector_index,
    check_vector_index_coverage,
    ingest_articles_to_bigquery,
    reconcile_deleted_documents,
    purge_tombstoned_chunks,
    get_stale_chunks_for_reprocessing,
    run_test_query,
    build_document_records,
    build_corpus_jsonl,
    upload_jsonl_to_gcs,
    import_documents_from_gcs,
)
from it_helpdesk_agent.tools.enterprise_rag.filter_builder import build_system_filter
from it_helpdesk_agent.app_utils.system_config import get_configured_systems

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ingest_knowledge_base")


def main():
    start_time = time.time()
    parser = argparse.ArgumentParser(description="Ingest customer documentation into Enterprise Knowledge Base")
    parser.add_argument(
        "--backend",
        type=str,
        default="vertex_ai_search",
        choices=["vertex_ai_search", "agent_search", "bigquery", "in_memory"],
        help="Target knowledge store backend (default: vertex_ai_search)",
    )
    parser.add_argument("--source-dir", type=str, help="Directory containing documents (.md, .txt, .docx, .pdf, .jsonl)")
    parser.add_argument("--file", type=str, help="Single document file to ingest")
    parser.add_argument("--system", type=str, help="Default enterprise system (e.g. ERP, HRM, CRM)")
    parser.add_argument("--project-id", type=str, default=os.getenv("GOOGLE_CLOUD_PROJECT", ""), help="Google Cloud Project ID")
    parser.add_argument("--location", type=str, default=os.getenv("VERTEX_SEARCH_LOCATION", "asia-southeast1"), help="Discovery Engine location (e.g. asia-southeast1, global)")
    parser.add_argument("--data-store-id", type=str, default=os.getenv("VERTEX_SEARCH_DATA_STORE_ID", "it-helpdesk-kb"), help="Discovery Engine Data Store ID")
    parser.add_argument("--gcs-bucket", type=str, default=os.getenv("KB_CORPUS_GCS_BUCKET", ""), help="GCS Bucket for staging corpus JSONL")
    parser.add_argument("--reconciliation-mode", type=str, default="FULL", choices=["FULL", "INCREMENTAL"], help="Reconciliation mode for Discovery Engine import")
    parser.add_argument("--dataset-id", type=str, default=os.getenv("BIGQUERY_KB_DATASET", "it_helpdesk_kb"), help="BigQuery Dataset ID (for BigQuery backend)")
    parser.add_argument("--table-name", type=str, default="knowledge_articles", help="BigQuery Table Name")
    parser.add_argument("--dry-run", action="store_true", help="Parse and generate sample JSONL locally without writing to cloud")
    parser.add_argument("--output-jsonl", type=str, default="data/corpus/documents.jsonl", help="Output path for generated JSONL")
    parser.add_argument("--acl", action="store_true", help="Include ACL / access control metadata in generated records")
    parser.add_argument("--reconcile", action="store_true", help="Tombstone documents missing from source directory (BigQuery)")
    parser.add_argument("--purge-tombstones-older-than", type=int, help="Hard delete tombstones older than N days (BigQuery)")
    parser.add_argument("--reprocess-where", type=str, help="Check and list stale chunks requiring reprocessing (BigQuery)")
    parser.add_argument("--test-query", type=str, help="Run a verification query after ingestion")
    parser.add_argument("--dlq-path", type=str, default=os.getenv("DLQ_STORAGE_PATH", "data/dlq/ingestion_dlq.jsonl"), help="Path to save / load dead-letter queue records")
    parser.add_argument("--show-dlq", action="store_true", help="Display all persisted dead-letter queue records and exit")

    args = parser.parse_args()

    # Show DLQ inspect option
    if args.show_dlq:
        records = read_persisted_dead_letter_queue(
            dlq_file_path=args.dlq_path,
            project_id=args.project_id or None,
            dataset_id=args.dataset_id or None
        )
        print(f"=== Persisted Dead-Letter Queue Records ({len(records)}) ===")
        for idx, rec in enumerate(records, 1):
            print(f"[{idx}] {rec.get('occurred_at')} | Stage: {rec.get('stage')} | File: {rec.get('file_path')} | Error: {rec.get('error_message')}")
        return

    # BigQuery specific maintenance options
    if args.purge_tombstones_older_than is not None:
        if not args.project_id:
            logger.error("Project ID is required for tombstone purge.")
            sys.exit(1)
        from google.cloud import bigquery
        bq_client = bigquery.Client(project=args.project_id)
        purge_tombstoned_chunks(bq_client, args.project_id, args.dataset_id, args.table_name, older_than_days=args.purge_tombstones_older_than)
        return

    if args.reprocess_where:
        if not args.project_id:
            logger.error("Project ID is required to query stale chunks.")
            sys.exit(1)
        from google.cloud import bigquery
        bq_client = bigquery.Client(project=args.project_id)
        stale = get_stale_chunks_for_reprocessing(
            bq_client, args.project_id, args.dataset_id, args.table_name,
            current_chunker_version=CHUNKER_VERSION, current_parser_version=PARSER_VERSION
        )
        logger.info("Found %d stale chunks matching reprocessing criteria.", len(stale))
        return

    # Determine files to process
    files_to_process: list[Path] = []
    if args.file:
        p = Path(args.file)
        if not p.exists():
            logger.error("File not found: %s", p)
            sys.exit(1)
        files_to_process.append(p)
    elif args.source_dir:
        p = Path(args.source_dir)
        if not p.exists():
            logger.error("Directory not found: %s", p)
            sys.exit(1)
        for ext in ("*.md", "*.txt", "*.docx", "*.pdf", "*.jsonl"):
            files_to_process.extend(p.glob(ext))
    else:
        # Default to data/knowledge_base if present
        default_data_dir = BASE_DIR / "data" / "knowledge_base"
        if default_data_dir.exists():
            for ext in ("*.md", "*.txt", "*.docx", "*.pdf", "*.jsonl"):
                files_to_process.extend(default_data_dir.glob(ext))
        else:
            logger.error("Please specify --source-dir or --file")
            sys.exit(1)

    if not files_to_process:
        logger.warning("No supported document files found to process.")
        sys.exit(0)

    target_backend = args.backend.lower()
    if target_backend in ("vertex_ai_search", "agent_search"):
        logger.info(
            "Target Backend: Vertex AI Search (Agent Search). Processing %d file(s)...",
            len(files_to_process)
        )
        
        out_path = Path(args.output_jsonl)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        total_records = 0
        sample_record = None
        dead_letter_queue: list[dict[str, Any]] = []

        with open(out_path, "w", encoding="utf-8") as out_f:
            for fp in files_to_process:
                try:
                    recs = build_document_records(fp, enable_chunking=True)
                    if not recs:
                        continue
                    if sample_record is None and recs:
                        sample_record = recs[0]
                    for r in recs:
                        out_f.write(json.dumps(r, ensure_ascii=False) + "\n")
                        total_records += 1
                except Exception as e:
                    logger.error("DLQ: Failed processing %s: %s", fp.name, e)
                    dead_letter_queue.append({
                        "file": str(fp),
                        "error": str(e),
                        "stage": "jsonl_build"
                    })

        if dead_letter_queue:
            logger.warning("Dead Letter Queue: %d document(s) failed.", len(dead_letter_queue))
            persist_dead_letter_queue(
                dead_letter_queue,
                project_id=args.project_id if not args.dry_run else None,
                dataset_id=args.dataset_id if not args.dry_run else None,
                dlq_file_path=args.dlq_path,
            )

        # Build sample filter for preview
        sample_filter = build_system_filter(get_configured_systems())

        if args.dry_run:
            print("\n=================== DRY-RUN VERIFICATION ===================")
            print(f"Backend: Vertex AI Search (Agent Search)")
            print(f"Total documents/chunks generated: {total_records}")
            print(f"Output JSONL file: {out_path}")
            print(f"Sample JSONL Record:\n{json.dumps(sample_record, indent=2, ensure_ascii=False)}")
            print(f"Estimated Security Filter:\n{sample_filter}")
            print("============================================================\n")
            logger.info("[Dry-Run Mode] Finished successfully. No cloud APIs invoked.")
            sys.exit(0)

        # Production Execution
        if not args.gcs_bucket:
            logger.error("--gcs-bucket is required for Vertex AI Search ingestion.")
            sys.exit(1)
        if not args.project_id:
            logger.error("--project-id is required for Vertex AI Search ingestion.")
            sys.exit(1)

        blob_name = f"ingest/{int(time.time())}/corpus.jsonl"
        gcs_uri = upload_jsonl_to_gcs(
            local_file_path=out_path,
            bucket_name=args.gcs_bucket,
            destination_blob_name=blob_name,
        )

        import_documents_from_gcs(
            project_id=args.project_id,
            location=args.location,
            data_store_id=args.data_store_id,
            gcs_uri=gcs_uri,
            reconciliation_mode=args.reconciliation_mode,
        )

        logger.info("Vertex AI Search Ingestion initiated successfully via GCS: %s", gcs_uri)
        return

    elif target_backend == "bigquery":
        logger.info("Target Backend: BigQuery. Found %d file(s) to process.", len(files_to_process))
        all_articles: list[dict[str, Any]] = []
        dead_letter_queue = []

        for fp in files_to_process:
            logger.info("Parsing %s...", fp.name)
            try:
                if fp.suffix.lower() in (".md", ".txt"):
                    docs = DocumentParser.parse_markdown_or_text(fp)
                elif fp.suffix.lower() == ".docx":
                    docs = DocumentParser.parse_docx(fp)
                elif fp.suffix.lower() == ".pdf":
                    docs = DocumentParser.parse_pdf(fp)
                elif fp.suffix.lower() == ".jsonl":
                    docs = DocumentParser.parse_jsonl(fp)
                else:
                    continue

                for d in docs:
                    try:
                        processed = process_document(d, default_system=args.system)
                        all_articles.extend(processed)
                    except Exception as e:
                        logger.error("DLQ: Failed processing doc '%s' from %s: %s", d.get("title"), fp.name, e)
                        dead_letter_queue.append({"file": str(fp), "doc": d, "error": str(e), "stage": "chunking"})
            except Exception as e:
                logger.error("DLQ: Failed parsing file %s: %s", fp.name, e)
                dead_letter_queue.append({"file": str(fp), "error": str(e), "stage": "parsing"})

        if dead_letter_queue:
            persist_dead_letter_queue(
                dead_letter_queue,
                project_id=args.project_id if not args.dry_run else None,
                dataset_id=args.dataset_id if not args.dry_run else None,
                dlq_file_path=args.dlq_path
            )

        if args.dry_run:
            logger.info("[Dry-Run Mode] Generating sample embeddings locally (No BigQuery writes)...")
            texts = [a["content"] for a in all_articles]
            embeddings = generate_batch_embeddings(texts, model_name=DEFAULT_EMBEDDING_MODEL, use_vertex=False)
            for a, emb in zip(all_articles, embeddings):
                a["embedding"] = emb
            logger.info("[Dry-Run Mode] All %d articles validated and embedded successfully.", len(all_articles))
        else:
            if not args.project_id:
                logger.error("Project ID is required for BigQuery ingestion.")
                sys.exit(1)
            
            ingest_articles_to_bigquery(
                all_articles,
                project_id=args.project_id,
                dataset_id=args.dataset_id,
                table_name=args.table_name
            )

            if args.reconcile or (args.source_dir and not args.file):
                active_uris = list({str(fp) for fp in files_to_process})
                for a in all_articles:
                    if a.get("source_uri"):
                        active_uris.append(a["source_uri"])
                active_uris = list(set(active_uris))
                
                from google.cloud import bigquery
                bq_client = bigquery.Client(project=args.project_id)
                reconcile_deleted_documents(
                    bq_client=bq_client,
                    project_id=args.project_id,
                    dataset_id=args.dataset_id,
                    table_name=args.table_name,
                    active_source_uris=active_uris
                )

        if args.test_query:
            run_test_query(
                args.test_query,
                project_id=args.project_id,
                dataset_id=args.dataset_id,
                table_name=args.table_name,
                dry_run=args.dry_run,
                sample_articles=all_articles
            )

    elif target_backend == "in_memory":
        logger.info("Target Backend: in_memory. Validating documents in memory...")
        count = 0
        for fp in files_to_process:
            recs = build_document_records(fp, enable_chunking=True)
            count += len(recs)
        logger.info("In-memory validation complete: %d chunks parsed.", count)


if __name__ == "__main__":
    main()
