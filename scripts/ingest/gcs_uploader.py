"""
Google Cloud Storage Uploader for Ingestion Pipeline.

Handles secure upload of JSONL corpus data to designated GCS corpus buckets.

Google Cloud Official Documentation:
- GCS Python Client Reference:
  https://cloud.google.com/python/docs/reference/storage/latest
"""

import os
import logging
from pathlib import Path
from typing import Optional, Any

try:
    from google.cloud import storage
except ImportError:
    storage = None  # type: ignore

logger = logging.getLogger("ingest.gcs_uploader")


def upload_jsonl_to_gcs(
    local_file_path: Path,
    bucket_name: str,
    destination_blob_name: str,
    storage_client: Optional[Any] = None,
) -> str:
    """
    Uploads a local JSONL file to Google Cloud Storage.
    Returns the gs:// URI of the uploaded blob.
    """
    if not local_file_path.exists():
        raise FileNotFoundError(f"Local file does not exist: {local_file_path}")

    client = storage_client
    if client is None:
        if storage is None:
            raise ImportError("google-cloud-storage package is not installed.")
        client = storage.Client()

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    logger.info("Uploading %s to gs://%s/%s...", local_file_path, bucket_name, destination_blob_name)
    blob.upload_from_filename(str(local_file_path), content_type="application/json")
    
    gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
    logger.info("Upload complete: %s", gcs_uri)
    return gcs_uri
