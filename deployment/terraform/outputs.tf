output "cloud_run_url" {
  description = "The URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.default.uri
}

output "service_account_email" {
  description = "The Service Account used by the IT Helpdesk Agent"
  value       = google_service_account.agent_sa.email
}

output "artifact_registry_repository" {
  description = "Artifact Registry Docker repository"
  value       = google_artifact_registry_repository.repo.id
}

output "vertex_search_data_store_id" {
  description = "Discovery Engine / Vertex AI Search Data Store ID"
  value       = google_discovery_engine_data_store.kb_store.data_store_id
}

output "vertex_search_engine_id" {
  description = "Discovery Engine Search Engine (App) ID"
  value       = google_discovery_engine_search_engine.kb_search_engine.engine_id
}

output "kb_corpus_bucket_name" {
  description = "GCS Bucket for Knowledge Base JSONL Corpus Stage"
  value       = google_storage_bucket.kb_corpus_bucket.name
}

output "bigquery_kb_dataset" {
  description = "BigQuery dataset for Enterprise Knowledge Base (null if not using bigquery backend)"
  value       = try(google_bigquery_dataset.kb_dataset[0].dataset_id, null)
}

output "firestore_database_name" {
  description = "Firestore database for ticketing store"
  value       = google_firestore_database.database.name
}

output "load_balancer_ip" {
  description = "Public IP of Global HTTPS Load Balancer (if enabled)"
  value       = var.enable_load_balancer ? google_compute_global_address.lb_ip[0].address : null
}

output "redis_host" {
  description = "Private IP Host of Memorystore for Redis instance"
  value       = var.redis_enabled ? google_redis_instance.cache_redis[0].host : null
}

output "redis_port" {
  description = "Port number of Memorystore for Redis instance"
  value       = var.redis_enabled ? google_redis_instance.cache_redis[0].port : null
}
