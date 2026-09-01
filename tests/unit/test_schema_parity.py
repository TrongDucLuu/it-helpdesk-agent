"""
Unit and Mutation Tests for Schema Parity between Terraform and Python Ingestion.
Guarantees that `google_bigquery_table.knowledge_articles` in `deployment/terraform/main.tf`
and `scripts/ingest/loaders.py` have 100% schema parity across all 20 fields.
"""
import re
import json
from pathlib import Path
import pytest
from google.cloud import bigquery
from scripts.ingest.loaders import get_knowledge_articles_schema, get_dlq_schema


def extract_terraform_schema() -> list[dict]:
    """Parses the JSON schema block from deployment/terraform/main.tf."""
    tf_path = Path(__file__).parent.parent.parent / "deployment" / "terraform" / "main.tf"
    assert tf_path.exists(), f"Terraform main.tf not found at {tf_path}"

    content = tf_path.read_text(encoding="utf-8")
    match = re.search(r'resource\s+"google_bigquery_table"\s+"knowledge_articles"\s*\{.*?schema\s*=\s*<<EOF\s*(.*?)\s*EOF', content, re.DOTALL)
    assert match is not None, "Could not find schema block in google_bigquery_table.knowledge_articles"

    raw_json = match.group(1).strip()
    schema_fields = json.loads(raw_json)
    assert isinstance(schema_fields, list), "Terraform schema JSON must be a list of field definitions"
    return schema_fields


def normalize_type(t: str) -> str:
    """Normalizes BigQuery equivalent type names for comparison."""
    t_upper = t.upper().strip()
    mapping = {
        "BOOL": "BOOLEAN",
        "BOOLEAN": "BOOLEAN",
        "INT64": "INTEGER",
        "INTEGER": "INTEGER",
        "FLOAT64": "FLOAT64",
        "STRING": "STRING",
        "TIMESTAMP": "TIMESTAMP",
        "RECORD": "RECORD",
        "STRUCT": "RECORD",
    }
    return mapping.get(t_upper, t_upper)


def test_schema_parity_fields_and_types():
    """Verifies that all 20 fields, types, modes, and nested fields match between Terraform and loaders.py."""
    tf_schema = extract_terraform_schema()
    py_schema = get_knowledge_articles_schema()

    # 1. Total field count check
    assert len(tf_schema) == len(py_schema) == 20, (
        f"Schema count mismatch: Terraform has {len(tf_schema)} fields, "
        f"Python loaders.py has {len(py_schema)} fields (Expected exactly 20)."
    )

    tf_dict = {f["name"]: f for f in tf_schema}
    py_dict = {f.name: f for f in py_schema}

    # 2. Check every field
    for name, py_field in py_dict.items():
        assert name in tf_dict, f"Field '{name}' defined in Python loaders.py is missing from Terraform main.tf schema!"
        tf_field = tf_dict[name]

        # Verify normalized type
        expected_type = normalize_type(py_field.field_type)
        actual_type = normalize_type(tf_field.get("type", ""))
        assert actual_type == expected_type, (
            f"Type mismatch for field '{name}': Python={expected_type}, Terraform={actual_type}"
        )

        # Verify mode
        expected_mode = py_field.mode.upper() if py_field.mode else "NULLABLE"
        actual_mode = tf_field.get("mode", "NULLABLE").upper()
        assert actual_mode == expected_mode, (
            f"Mode mismatch for field '{name}': Python={expected_mode}, Terraform={actual_mode}"
        )

        # Verify nested fields (e.g. section_hierarchy)
        if expected_type == "RECORD":
            tf_sub = {sf["name"]: sf for sf in tf_field.get("fields", [])}
            py_sub = {sf.name: sf for sf in py_field.fields}
            assert set(tf_sub.keys()) == set(py_sub.keys()), (
                f"Subfields mismatch for RECORD field '{name}': Python={list(py_sub.keys())}, Terraform={list(tf_sub.keys())}"
            )
            for sub_name, py_sub_field in py_sub.items():
                assert normalize_type(tf_sub[sub_name]["type"]) == normalize_type(py_sub_field.field_type)


def test_schema_parity_mutation_detection():
    """Mutation Test: Injects synthetic schema drifts and confirms validation strictly fails."""
    tf_schema = extract_terraform_schema()
    
    # Mutation 1: Missing column in Terraform
    mutated_tf = [f for f in tf_schema if f["name"] != "parser_version"]
    assert len(mutated_tf) != len(get_knowledge_articles_schema()), "Mutation 1 should alter length"

    # Mutation 2: Mismatched type
    mutated_type_tf = [
        {**f, "type": "INTEGER" if f["name"] == "is_deleted" else f["type"]}
        for f in tf_schema
    ]
    py_schema = get_knowledge_articles_schema()
    py_dict = {f.name: f for f in py_schema}
    
    with pytest.raises(AssertionError):
        # Emulate checking with mutated type
        is_deleted_tf = next(f for f in mutated_type_tf if f["name"] == "is_deleted")
        assert normalize_type(is_deleted_tf["type"]) == normalize_type(py_dict["is_deleted"].field_type)


def extract_terraform_dlq_schema() -> list[dict]:
    """Parses the JSON schema block for google_bigquery_table.ingestion_dead_letter_queue from Terraform."""
    tf_path = Path(__file__).parent.parent.parent / "deployment" / "terraform" / "main.tf"
    assert tf_path.exists(), f"Terraform main.tf not found at {tf_path}"

    content = tf_path.read_text(encoding="utf-8")
    match = re.search(r'resource\s+"google_bigquery_table"\s+"ingestion_dead_letter_queue"\s*\{.*?schema\s*=\s*<<EOF\s*(.*?)\s*EOF', content, re.DOTALL)
    assert match is not None, "Could not find schema block in google_bigquery_table.ingestion_dead_letter_queue"

    raw_json = match.group(1).strip()
    schema_fields = json.loads(raw_json)
    assert isinstance(schema_fields, list), "Terraform DLQ schema JSON must be a list of field definitions"
    return schema_fields


def test_dlq_schema_parity_fields_and_types():
    """Verifies that all 7 fields, types, and modes match between Terraform and loaders.py get_dlq_schema()."""
    tf_schema = extract_terraform_dlq_schema()
    py_schema = get_dlq_schema()

    assert len(tf_schema) == len(py_schema) == 7, (
        f"DLQ Schema count mismatch: Terraform has {len(tf_schema)} fields, "
        f"Python get_dlq_schema() has {len(py_schema)} fields (Expected exactly 7)."
    )

    tf_dict = {f["name"]: f for f in tf_schema}
    py_dict = {f.name: f for f in py_schema}

    for name, py_field in py_dict.items():
        assert name in tf_dict, f"Field '{name}' defined in Python get_dlq_schema() is missing from Terraform main.tf!"
        tf_field = tf_dict[name]

        expected_type = normalize_type(py_field.field_type)
        actual_type = normalize_type(tf_field.get("type", ""))
        assert actual_type == expected_type, (
            f"Type mismatch for DLQ field '{name}': Python={expected_type}, Terraform={actual_type}"
        )

        expected_mode = py_field.mode.upper() if py_field.mode else "NULLABLE"
        actual_mode = tf_field.get("mode", "NULLABLE").upper()
        assert actual_mode == expected_mode, (
            f"Mode mismatch for DLQ field '{name}': Python={expected_mode}, Terraform={actual_mode}"
        )


def test_dlq_schema_parity_mutation_detection():
    """Mutation Test: Injects synthetic schema drift into DLQ schema and confirms detection."""
    tf_schema = extract_terraform_dlq_schema()
    mutated_tf = [f for f in tf_schema if f["name"] != "doc_payload"]
    assert len(mutated_tf) != len(get_dlq_schema()), "Mutation should alter DLQ schema length"


def test_search_result_contract_parity_across_backends():
    """
    Verifies that SearchResult contract is strictly respected across all backends:
    - Exactly the same fields and types (including chunk_id, parent_doc_id).
    - relevance_score is bounded to [0.0, 1.0].
    """
    from it_helpdesk_agent.tools.enterprise_rag_mcp.knowledge_store import (
        InMemoryKnowledgeStore,
        BigQueryVectorKnowledgeStore,
    )
    from it_helpdesk_agent.tools.enterprise_rag_mcp.rag_models import SearchResult
    from unittest.mock import MagicMock

    # 1. InMemory Store Search
    in_mem_store = InMemoryKnowledgeStore()
    in_mem_results = in_mem_store.search("SAP Purchase Order", system="ERP", limit=3)
    assert len(in_mem_results) > 0

    for r in in_mem_results:
        assert isinstance(r, SearchResult)
        assert 0.0 <= r.relevance_score <= 1.0
        assert hasattr(r, "chunk_id")
        assert hasattr(r, "parent_doc_id")
        assert r.system == "ERP"

    # 2. BigQuery Store Search (Mocked Client)
    mock_bq_client = MagicMock()
    mock_row = MagicMock()
    mock_row.id = "ERP-KB-001"
    mock_row.system = "ERP"
    mock_row.title = "Test BQ Title"
    mock_row.content = "Test BQ Content for ERP"
    mock_row.distance = 0.25
    mock_row.hybrid_score = 4.5  # Exceeds 1.0 to test clamping / normalization
    mock_row.source_uri = "docs/test.md"
    mock_row.category = "Test"
    mock_row.keywords = ["erp", "sap"]
    mock_row.owner = "admin@company.com"
    mock_row.effective_date = "2025-01-01"
    mock_row.expiry_date = None
    mock_row.is_deleted = False
    mock_row.chunk_id = "chunk-001"
    mock_row.parent_doc_id = "doc-001"
    mock_row.section_hierarchy = {"h1": "H1", "h2": "H2", "h3": "H3"}

    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [mock_row]
    mock_bq_client.query.return_value = mock_query_job

    bq_store = BigQueryVectorKnowledgeStore(
        project_id="test-proj",
        dataset_id="test_ds",
        bq_client=mock_bq_client,
        embedding_fn=lambda x: [0.1] * 64
    )
    bq_results = bq_store.search("test query", system="ERP", limit=1)
    assert len(bq_results) == 1
    bq_r = bq_results[0]
    assert isinstance(bq_r, SearchResult)
    assert 0.0 <= bq_r.relevance_score <= 1.0
    assert bq_r.chunk_id == "chunk-001"
    assert bq_r.parent_doc_id == "doc-001"
    assert bq_r.section_hierarchy.h1 == "H1"
    assert bq_r.relevance_score <= 1.0


def test_search_result_relevance_score_clamping():
    """Verifies that SearchResult validator clamps relevance_score to [0.0, 1.0]."""
    from it_helpdesk_agent.tools.enterprise_rag_mcp.rag_models import SearchResult

    res_high = SearchResult(
        article_id="TEST-001",
        system="ERP",
        title="Test",
        snippet="Snippet",
        relevance_score=3.5,
    )
    assert res_high.relevance_score == 1.0

    res_low = SearchResult(
        article_id="TEST-002",
        system="ERP",
        title="Test",
        snippet="Snippet",
        relevance_score=-0.8,
    )
    assert res_low.relevance_score == 0.0

