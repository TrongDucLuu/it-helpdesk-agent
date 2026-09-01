"""
Enterprise Knowledge Base Ingestion Package.
Provides document parsers, chunking strategies, Discovery Engine JSONL builders, GCS uploaders, and VAIS importers.
"""

from scripts.ingest.parsers import DocumentParser, PARSER_VERSION
from scripts.ingest.chunkers import (
    is_well_structured,
    chunk_by_sections,
    chunk_text,
    process_document,
    CHUNKER_VERSION,
)
from scripts.ingest.embedders import (
    generate_batch_embeddings,
    generate_text_embedding,
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
)
from scripts.ingest.loaders import (
    get_knowledge_articles_schema,
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
)
from scripts.ingest.jsonl_builder import (
    build_document_records,
    build_corpus_jsonl,
)
from scripts.ingest.gcs_uploader import (
    upload_jsonl_to_gcs,
)
from scripts.ingest.vais_importer import (
    import_documents_from_gcs,
)

__all__ = [
    "DocumentParser",
    "PARSER_VERSION",
    "is_well_structured",
    "chunk_by_sections",
    "chunk_text",
    "process_document",
    "CHUNKER_VERSION",
    "generate_batch_embeddings",
    "generate_text_embedding",
    "DEFAULT_EMBEDDING_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "get_knowledge_articles_schema",
    "get_dlq_schema",
    "persist_dead_letter_queue",
    "read_persisted_dead_letter_queue",
    "ensure_vector_index",
    "check_vector_index_coverage",
    "ingest_articles_to_bigquery",
    "reconcile_deleted_documents",
    "purge_tombstoned_chunks",
    "get_stale_chunks_for_reprocessing",
    "run_test_query",
    "build_document_records",
    "build_corpus_jsonl",
    "upload_jsonl_to_gcs",
    "import_documents_from_gcs",
]
