variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "The Google Cloud region to deploy to (e.g. asia-southeast1, us-central1, europe-west1, global). Required to ensure data residency compliance."
  type        = string
  validation {
    condition     = contains(["asia-southeast1", "asia-east1", "asia-northeast1", "us-central1", "us-east1", "us-west1", "europe-west1", "europe-west4", "global"], var.region)
    error_message = "The region must be a valid Google Cloud region supported by Discovery Engine / Vertex AI Search (e.g. asia-southeast1, us-central1, europe-west1, global)."
  }
}

variable "service_name" {
  description = "The name of the Cloud Run service"
  type        = string
  default     = "it-helpdesk-agent"
}

variable "environment" {
  description = "Deployment environment (production, staging, development)"
  type        = string
  default     = "production"
}

variable "secrets" {
  description = "A map of secret names and their values (e.g., HELPDESK_ADMIN_API_KEY, SSO_CLIENT_SECRET, SSO_JWT_SECRET)"
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "ai_assets_bucket" {
  description = "The GCS bucket for storing IT Helpdesk assets and artifacts"
  type        = string
  default     = ""
}

variable "sso_client_id" {
  description = "The SSO / OIDC Client ID for enterprise authentication (Google Workspace OAuth Client ID)"
  type        = string
  default     = "it-helpdesk-agent-client-id"
}

variable "sso_issuer" {
  description = "The SSO / OIDC Issuer URL (e.g., https://accounts.google.com)"
  type        = string
  default     = "https://accounts.google.com"
}

variable "allowed_domains" {
  description = "Comma-separated list of enterprise domains permitted to access (e.g. 'company.com,subsidiary.com')"
  type        = string
  default     = ""
}

variable "knowledge_backend" {
  description = "Knowledge base backend ('vertex_ai_search', 'bigquery', 'in_memory')"
  type        = string
  default     = "vertex_ai_search"
  validation {
    condition     = contains(["vertex_ai_search", "bigquery", "in_memory"], var.knowledge_backend)
    error_message = "knowledge_backend must be one of: 'vertex_ai_search', 'bigquery', 'in_memory'."
  }
}

# ==============================================================================
# Vertex AI Search (Agent Search / Discovery Engine) Variables
# ==============================================================================

variable "vertex_search_data_store_id" {
  description = "Data store ID for Discovery Engine / Vertex AI Search (e.g. it-helpdesk-kb)"
  type        = string
  default     = "it-helpdesk-kb"
}

variable "vertex_search_engine_id" {
  description = "Search Engine / App ID for Discovery Engine (e.g. it-helpdesk-engine)"
  type        = string
  default     = "it-helpdesk-engine"
}

variable "acl_enabled" {
  description = "IMMUTABLE — KHÔNG THỂ THAY ĐỔI SAU KHI TẠO. ĐỔI Ý NGHĨA LÀ PHẢI XOÁ DATA STORE VÀ RE-INDEX TOÀN BỘ CORPUS. Bật Document-level ACLs (Option B) hoặc dùng Metadata Filtering (Option A)."
  type        = bool
  default     = false
}

variable "enable_cmek" {
  description = "Enable Customer-Managed Encryption Keys (CMEK) for enterprise banking/defense tier"
  type        = bool
  default     = false
}

variable "cmek_kms_key_name" {
  description = "Cloud KMS Key Resource Name for CMEK encryption (required if enable_cmek is true)"
  type        = string
  default     = ""
}

variable "enable_vpc_sc" {
  description = "Enable VPC Service Controls perimeter compatibility"
  type        = bool
  default     = false
}

# ==============================================================================
# BigQuery & Legacy Backend Variables (Conditional via knowledge_backend)
# ==============================================================================

variable "bigquery_kb_dataset" {
  description = "BigQuery dataset ID for storing knowledge articles and vector embeddings (used only when knowledge_backend is 'bigquery')"
  type        = string
  default     = "it_helpdesk_kb"
}

variable "max_instance_count" {
  description = "Maximum number of Cloud Run container instances. Enterprise Sizing Formula: ceil(Peak_CCU / max_instance_request_concurrency) * 1.5"
  type        = number
  default     = 10
}

variable "min_instance_count" {
  description = "Minimum number of Cloud Run container instances (recommend >= 1 in production to eliminate cold starts)"
  type        = number
  default     = 1
}

variable "max_instance_request_concurrency" {
  description = "Maximum concurrent requests per container instance (recommended 4-8 for LLM reasoning workloads)"
  type        = number
  default     = 8
}

variable "redis_enabled" {
  description = "Provision Google Cloud Memorystore for Redis for cluster-wide rate limiting and semantic caching"
  type        = bool
  default     = true
}

variable "redis_memory_size_gb" {
  description = "Memory capacity in GiB for Memorystore Redis instance (1 GiB supports ~50,000 active users + cache entries)"
  type        = number
  default     = 1
}

variable "l3_rate_limit_per_minute" {
  description = "Rate limit threshold for expensive L3 Gemini Pro reasoning calls per user per minute"
  type        = number
  default     = 10
}

variable "allow_unauthenticated" {
  description = "Whether to allow unauthenticated public HTTP access at Cloud Run layer (SSO auth is enforced at application middleware)"
  type        = bool
  default     = true
}

variable "use_firestore_tickets" {
  description = "Enable Google Cloud Firestore for persistent helpdesk ticket storage"
  type        = bool
  default     = true
}

variable "rate_limit_enabled" {
  description = "Enable sliding window rate limiting"
  type        = bool
  default     = true
}

variable "rate_limit_per_minute" {
  description = "Rate limit threshold per client per minute"
  type        = number
  default     = 60
}

variable "agent_engine_resource_name" {
  description = "Pre-provisioned Vertex AI Agent Engine resource name (optional, overrides auto-creation at runtime)"
  type        = string
  default     = ""
}

variable "firestore_database_name" {
  description = "Name of the Firestore database instance ('(default)' or custom named database)"
  type        = string
  default     = "(default)"
}

variable "enable_load_balancer" {
  description = "Provision a Google Cloud Global HTTPS Load Balancer with Cloud Armor WAF and SSL (Recommended for Enterprise Production)"
  type        = bool
  default     = false
}

variable "domain_name" {
  description = "Custom domain name for Google-managed SSL Certificate (e.g., helpdesk.corp.example.com)"
  type        = string
  default     = ""
}

variable "use_vertex_embedding" {
  description = "Enable Vertex AI text-embedding-005 for generating dense vector embeddings"
  type        = bool
  default     = true
}

variable "systems_config_path" {
  description = "Path to the systems and RBAC configuration YAML file"
  type        = string
  default     = "/code/config/systems.yaml"
}

variable "enable_cloud_armor" {
  description = "Enable Google Cloud Armor WAF and HTTPS Load Balancer in front of Cloud Run for DDoS and OWASP protection"
  type        = bool
  default     = false
}

variable "fast_model_name" {
  description = "Gemini model name for standard triage, L1 and L2 agents. GA default: 'gemini-2.5-flash' (guaranteed 99.9% Vertex AI SLA). For experimental preview, override with 'gemini-3-flash-preview'."
  type        = string
  default     = "gemini-2.5-flash"
}

variable "reasoning_model_name" {
  description = "Gemini model name for L3 reasoning diagnostics & compliance. GA default: 'gemini-2.5-pro' (guaranteed 99.9% Vertex AI SLA). For experimental preview, override with 'gemini-3-pro-preview'."
  type        = string
  default     = "gemini-2.5-pro"
}

variable "telemetry_anonymize_users" {
  description = "Hash user IDs (SHA-256) in telemetry logs for GDPR/HIPAA/Banking compliance (Fail-closed default: true)"
  type        = bool
  default     = true
}

variable "telemetry_include_query" {
  description = "Include query snippets in telemetry logs (Fail-closed default: false for sensitive data protection)"
  type        = bool
  default     = false
}
