# ==============================================================================
# Vertex AI Search (Agent Search / Discovery Engine) Infrastructure Module
#
# Google Cloud Official Documentation:
# - Discovery Engine Data Store Terraform Resource:
#   https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/discovery_engine_data_store
# - Discovery Engine Search Engine / App:
#   https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/discovery_engine_search_engine
# - Discovery Engine Access Control (IAM):
#   https://cloud.google.com/generative-ai-app-builder/docs/access-control
# ==============================================================================

# 1. GCS Bucket for Knowledge Base Corpus (JSONL Stage)
resource "google_storage_bucket" "kb_corpus_bucket" {
  name                        = "${var.project_id}-${var.service_name}-kb-corpus"
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  dynamic "encryption" {
    for_each = var.enable_cmek && var.cmek_kms_key_name != "" ? [1] : []
    content {
      default_kms_key_name = var.cmek_kms_key_name
    }
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 90
    }
  }

  depends_on = [google_project_service.services]
}

# 2. Discovery Engine Data Store
# NOTE: acl_enabled IS IMMUTABLE.
# KHÔNG THỂ THAY ĐỔI SAU KHI TẠO. ĐỔI Ý NGHĨA LÀ PHẢI XOÁ DATA STORE VÀ RE-INDEX TOÀN BỘ CORPUS.
resource "google_discovery_engine_data_store" "kb_store" {
  project                     = var.project_id
  location                    = var.region
  data_store_id               = var.vertex_search_data_store_id
  display_name                = "Enterprise IT Helpdesk Knowledge Base"
  industry_vertical           = "GENERIC"
  content_config              = "CONTENT_REQUIRED"
  solution_types              = ["SOLUTION_TYPE_SEARCH"]
  create_advanced_site_search = false

  dynamic "acl_enabled" {
    for_each = var.acl_enabled ? [true] : []
    content {}
  }

  dynamic "kms_key_name" {
    for_each = var.enable_cmek && var.cmek_kms_key_name != "" ? [var.cmek_kms_key_name] : []
    content {}
  }

  depends_on = [google_project_service.services]
}

# 3. Discovery Engine Search Engine (App)
resource "google_discovery_engine_search_engine" "kb_search_engine" {
  project        = var.project_id
  collection_id  = "default_collection"
  location       = var.region
  engine_id      = var.vertex_search_engine_id
  display_name   = "IT Helpdesk Search Engine"
  data_store_ids = [google_discovery_engine_data_store.kb_store.data_store_id]

  search_engine_config {
    search_tier = "SEARCH_TIER_ENTERPRISE"
    search_add_ons = ["SEARCH_ADD_ON_LLM"]
  }

  depends_on = [google_discovery_engine_data_store.kb_store]
}

# 4. IAM Least Privilege Permissions for Cloud Run Service Account
# Discovery Engine Viewer role for runtime search & retrieval
resource "google_project_iam_member" "discovery_engine_viewer" {
  count   = var.knowledge_backend == "vertex_ai_search" ? 1 : 0
  project = var.project_id
  role    = "roles/discoveryengine.viewer"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# Storage Admin strictly on the corpus bucket for ingestion pipelines
resource "google_storage_bucket_iam_member" "kb_corpus_storage_admin" {
  bucket = google_storage_bucket.kb_corpus_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.agent_sa.email}"
}
