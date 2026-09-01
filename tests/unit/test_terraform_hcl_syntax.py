"""
Unit Tests for Terraform Configuration (Epic 4: VAIS-040, VAIS-041, VAIS-042, VAIS-043, VAIS-044).

Validates:
- VAIS-040: Vertex AI Search module, data store, search engine, and immutable acl_enabled comments.
- VAIS-041: No default region, valid region validation block.
- VAIS-042: Discovery Engine viewer IAM permission for Cloud Run SA.
- VAIS-043: BigQuery resources and IAM are conditional based on knowledge_backend == "bigquery".
- VAIS-044: Audit logging for Discovery Engine with DATA_READ and DATA_WRITE.
"""

from pathlib import Path
import pytest


@pytest.fixture
def tf_dir():
    return Path(__file__).resolve().parent.parent.parent / "deployment" / "terraform"


def test_vais_040_vertex_ai_search_tf_exists_and_configured(tf_dir):
    vais_tf = tf_dir / "vertex_ai_search.tf"
    assert vais_tf.exists(), "vertex_ai_search.tf must exist"

    content = vais_tf.read_text(encoding="utf-8")
    assert "google_discovery_engine_data_store" in content
    assert "google_discovery_engine_search_engine" in content
    assert "google_storage_bucket" in content
    assert "roles/discoveryengine.viewer" in content
    assert "IMMUTABLE" in content, "acl_enabled must have an IMMUTABLE warning comment"


def test_vais_041_region_has_no_default_and_has_validation(tf_dir):
    vars_tf = tf_dir / "variables.tf"
    assert vars_tf.exists()

    content = vars_tf.read_text(encoding="utf-8")
    
    # Extract the variable "region" block
    region_block_start = content.find('variable "region"')
    assert region_block_start != -1, "variable region must be defined"
    
    region_block_end = content.find('variable "', region_block_start + 10)
    region_block = content[region_block_start:region_block_end] if region_block_end != -1 else content[region_block_start:]

    assert "default" not in region_block, "variable region must NOT have a default value to prevent accidental data residency violations"
    assert "validation" in region_block, "variable region must have a validation block"
    assert "asia-southeast1" in region_block, "variable region validation must include asia-southeast1"


def test_vais_042_iam_least_privilege_discovery_engine(tf_dir):
    vais_tf = tf_dir / "vertex_ai_search.tf"
    content = vais_tf.read_text(encoding="utf-8")
    
    assert "roles/discoveryengine.viewer" in content
    assert "roles/storage.objectAdmin" in content


def test_vais_043_bigquery_resources_conditional(tf_dir):
    main_tf = tf_dir / "main.tf"
    content = main_tf.read_text(encoding="utf-8")

    assert 'count                      = var.knowledge_backend == "bigquery" ? 1 : 0' in content or \
           'count   = var.knowledge_backend == "bigquery" ? 1 : 0' in content or \
           'count               = var.knowledge_backend == "bigquery" ? 1 : 0' in content, \
           "BigQuery resources must have conditional count"


def test_vais_044_audit_logging_configured(tf_dir):
  main_tf = tf_dir / "main.tf"
  content = main_tf.read_text(encoding="utf-8")

  assert "google_project_iam_audit_config" in content
  assert "discoveryengine.googleapis.com" in content
  assert "DATA_READ" in content
  assert "DATA_WRITE" in content
