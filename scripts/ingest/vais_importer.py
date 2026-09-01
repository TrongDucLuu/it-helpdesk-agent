"""
Vertex AI Search (Agent Search) Idempotent Document Importer.

Triggers asynchronous document batch import into Discovery Engine data stores
using ReconciliationMode.FULL to automatically clean up orphaned chunks and tombstones.

Google Cloud Official Documentation:
- ImportDocuments Method:
  https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.services.document_service.DocumentServiceClient#google_cloud_discoveryengine_v1_services_document_service_DocumentServiceClient_import_documents
- Data Store Reconciliation:
  https://cloud.google.com/generative-ai-app-builder/docs/manage-data-stores#reconcile
- GcsSource Schema:
  https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.types.GcsSource
"""

import os
import logging
from typing import Optional, Any

try:
    from google.cloud import discoveryengine_v1
except ImportError:
    discoveryengine_v1 = None  # type: ignore

logger = logging.getLogger("ingest.vais_importer")


def import_documents_from_gcs(
    project_id: str,
    location: str,
    data_store_id: str,
    gcs_uri: str,
    collection_id: str = "default_collection",
    branch_id: str = "0",
    reconciliation_mode: str = "FULL",
    document_client: Optional[Any] = None,
    wait_for_completion: bool = False,
) -> Any:
    """
    Executes Discovery Engine ImportDocuments operation with GCS input and ReconciliationMode.
    
    ReconciliationMode.FULL ensures orphaned or removed documents in previous imports
    are purged, achieving strict idempotent parity between the GCS source JSONL and the index.
    """
    client = document_client
    if client is None:
        if discoveryengine_v1 is None:
            raise ImportError("google-cloud-discoveryengine package is not installed.")
        client = discoveryengine_v1.DocumentServiceClient()

    parent = (
        f"projects/{project_id}/locations/{location}"
        f"/collections/{collection_id}/dataStores/{data_store_id}"
        f"/branches/{branch_id}"
    )

    recon_enum = None
    if discoveryengine_v1:
        if reconciliation_mode.upper() == "FULL":
            recon_enum = discoveryengine_v1.ImportDocumentsRequest.ReconciliationMode.FULL
        else:
            recon_enum = discoveryengine_v1.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL

        gcs_source = discoveryengine_v1.GcsSource(
            input_uris=[gcs_uri],
            data_schema="custom",
        )

        request = discoveryengine_v1.ImportDocumentsRequest(
            parent=parent,
            gcs_source=gcs_source,
            reconciliation_mode=recon_enum,
        )
        logger.info(
            "Submitting ImportDocumentsRequest to %s (GCS: %s, Mode: %s)...",
            parent, gcs_uri, reconciliation_mode
        )
        operation = client.import_documents(request=request)
    else:
        # Duck-typed client call for mock/testing
        operation = client.import_documents(
            parent=parent,
            gcs_uri=gcs_uri,
            reconciliation_mode=reconciliation_mode,
        )

    logger.info("Import operation started: %s", getattr(operation, "operation", operation))

    if wait_for_completion and hasattr(operation, "result"):
        logger.info("Waiting for Discovery Engine import operation to finish...")
        response = operation.result()
        logger.info("Import completed successfully: %s", response)
        return response

    return operation
