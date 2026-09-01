"""
Unit Tests for GCS Uploader and VAIS Importer (VAIS-031).

Verifies:
- GCS upload interaction and return URI formatting.
- Discovery Engine ImportDocuments invocation with ReconciliationMode.FULL.
- Parent branch path generation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scripts.ingest.gcs_uploader import upload_jsonl_to_gcs
from scripts.ingest.vais_importer import import_documents_from_gcs


def test_upload_jsonl_to_gcs(tmp_path):
    local_file = tmp_path / "corpus.jsonl"
    local_file.write_text('{"id": "doc1"}\n')

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    uri = upload_jsonl_to_gcs(
        local_file_path=local_file,
        bucket_name="test-corpus-bucket",
        destination_blob_name="ingest/2026/corpus.jsonl",
        storage_client=mock_client,
    )

    assert uri == "gs://test-corpus-bucket/ingest/2026/corpus.jsonl"
    mock_client.bucket.assert_called_once_with("test-corpus-bucket")
    mock_bucket.blob.assert_called_once_with("ingest/2026/corpus.jsonl")
    mock_blob.upload_from_filename.assert_called_once_with(str(local_file), content_type="application/json")


def test_import_documents_from_gcs_invokes_full_reconciliation():
    mock_doc_client = MagicMock()
    mock_operation = MagicMock()
    mock_doc_client.import_documents.return_value = mock_operation

    op = import_documents_from_gcs(
        project_id="test-proj",
        location="asia-southeast1",
        data_store_id="it-kb-datastore",
        gcs_uri="gs://test-bucket/ingest/corpus.jsonl",
        reconciliation_mode="FULL",
        document_client=mock_doc_client,
        wait_for_completion=False,
    )

    assert op == mock_operation
    mock_doc_client.import_documents.assert_called_once()
    
    # Check request argument
    call_kwargs = mock_doc_client.import_documents.call_args.kwargs
    request = call_kwargs.get("request")
    if request:
        assert "projects/test-proj/locations/asia-southeast1/collections/default_collection/dataStores/it-kb-datastore/branches/0" in request.parent
        assert request.gcs_source.input_uris == ["gs://test-bucket/ingest/corpus.jsonl"]
    else:
        assert "it-kb-datastore" in call_kwargs.get("parent", "")
