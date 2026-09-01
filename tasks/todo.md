# Task List: Migration Vertex AI Search (Epic 0, Epic 1, Epic 2, Epic 3 & Epic 4)

## Epic 0: Spike & ADR
- [x] Task 0.1: VAIS-001 — Spike API Discovery Engine & Viết ADR 0001
  - Description: Xác thực API surface, SDK, vị trí `asia-southeast1`, cú pháp metadata filter, và viết `scripts/spike/vais_smoke.py` + `docs/adr/0001-knowledge-layer-agent-search.md`.
  - Acceptance: Có đầy đủ link doc Google, script spike chạy được cú pháp chuẩn, ADR 0001 hoàn thiện.
  - Verify: `.venv/bin/pytest tests/unit/`
  - Files: `scripts/spike/vais_smoke.py`, `docs/adr/0001-knowledge-layer-agent-search.md`

- [x] Task 0.2: VAIS-002 — ADR 0002: RBAC Enforcement Mechanism
  - Description: Viết ADR phân tích Option A (Metadata filter) vs Option B (Document-level ACL), threat models, ma trận phân loại khách hàng và tính bất biến của `acl_enabled`.
  - Acceptance: Phân tích đủ 2 phương án, có recommendation, có customer profile matrix.
  - Verify: File exists and passes review.
  - Files: `docs/adr/0002-rbac-enforcement.md`

- [x] Task 0.3: VAIS-003 — ADR 0003: Retrieval Granularity & Chunking Strategy
  - Description: Viết ADR phân tích trade-off giữa self-chunking (`chunkers.py`) và managed layout parser chunking của Agent Search.
  - Acceptance: Phân tích chi tiết ngữ cảnh enterprise document, bảng ma trận trade-off.
  - Verify: File exists and passes review.
  - Files: `docs/adr/0003-chunking-strategy.md`

## Epic 1: Sửa P0
- [x] Task 1.1: VAIS-010 — Bỏ MCP stdio, chuyển RAG thành In-Process FunctionTool
  - Description: Viết `it_helpdesk_agent/tools/enterprise_rag/rag_tools.py` in-process `FunctionTool`, refactor `agent.py`, viết integration test `tests/integration/test_rbac_end_to_end.py`.
  - Acceptance: `tests/integration/test_rbac_end_to_end.py` pass 100% với `K_SERVICE=1`, context SSO user được bảo toàn trong in-process execution.
  - Verify: `.venv/bin/pytest tests/integration/test_rbac_end_to_end.py`
  - Files: `it_helpdesk_agent/tools/enterprise_rag/rag_tools.py`, `it_helpdesk_agent/agent.py`, `tests/integration/test_rbac_end_to_end.py`

- [x] Task 1.2: VAIS-011 — Xoá mock detection `_mock_return_value` khỏi production code
  - Description: Quét và xoá sạch 14 vị trí `hasattr(..., "_mock_return_value")` trong `it_helpdesk_agent/`, thay thế bằng DI và clean typing.
  - Acceptance: `grep -rn "_mock_return_value" it_helpdesk_agent/` trả về 0. Toàn bộ unit tests pass.
  - Verify: `grep -rn "_mock_return_value" it_helpdesk_agent/` và `.venv/bin/pytest tests/unit/`
  - Files: `it_helpdesk_agent/tools/enterprise_rag_mcp/knowledge_store.py`

- [x] Task 1.3: VAIS-012 — Sửa báo cáo hiệu năng thành Capacity Model
  - Description: Đổi tiêu đề `SCALABILITY_PERFORMANCE_REPORT.md` thành "Capacity Model (mô hình tính toán)", ghi rõ giả định, bỏ từ "Empirical Benchmark", đánh dấu `CHƯA ĐO` cho số liệu thực nghiệm.
  - Acceptance: Báo cáo trung thực, rõ ràng giữa tính toán lý thuyết và đo đạc thực tế.
  - Verify: Review file diff.
  - Files: `SCALABILITY_PERFORMANCE_REPORT.md`

## Epic 2: Knowledge Layer Adapter Mới
- [x] Task 2.1: VAIS-020 — Chuẩn hoá contract `BaseKnowledgeStore` và `SearchResult`
  - Description: Thêm `chunk_id`, `parent_doc_id` vào `SearchResult`, chuẩn hóa `relevance_score` về $[0.0, 1.0]$ cho cả 3 backend (`in_memory`, `bigquery`, `vertex_ai_search`).
  - Acceptance: `tests/unit/test_schema_parity.py` pass 100% với $0.0 \le \text{score} \le 1.0$ và đồng nhất thuộc tính.
  - Verify: `.venv/bin/pytest tests/unit/test_schema_parity.py`
  - Files: `it_helpdesk_agent/tools/enterprise_rag_mcp/knowledge_store.py`, `tests/unit/test_schema_parity.py`

- [x] Task 2.2: VAIS-022 — Filter builder + fuzz test injection
  - Description: Viết `build_system_filter(allowed_systems: list[str]) -> str` whitelist chống injection, trả filter chặn tất cả khi `allowed_systems` rỗng.
  - Acceptance: `tests/unit/test_filter_builder_fuzz.py` với ≥20 injection payloads pass 100%.
  - Verify: `.venv/bin/pytest tests/unit/test_filter_builder_fuzz.py`
  - Files: `it_helpdesk_agent/tools/enterprise_rag/filter_builder.py`, `tests/unit/test_filter_builder_fuzz.py`

- [x] Task 2.3: VAIS-021 — `VertexAiSearchKnowledgeStore`
  - Description: Triển khai `BaseKnowledgeStore` với `SearchServiceClient`, doc links, mapping sang `SearchResult`, wrap tài liệu bằng `wrap_retrieved_document()`, fail-closed.
  - Acceptance: Unit test với fake client pass + integration test structure.
  - Verify: `.venv/bin/pytest tests/unit/test_vertex_search_store.py`
  - Files: `it_helpdesk_agent/tools/enterprise_rag/vertex_search_store.py`, `tests/unit/test_vertex_search_store.py`

- [x] Task 2.4: VAIS-023 — Factory 3 backend
  - Description: `get_knowledge_store(backend: Optional[str] = None)` hỗ trợ `{in_memory, bigquery, vertex_ai_search}`, backend lạ raise exception ngay lập tức.
  - Acceptance: `tests/unit/test_knowledge_store_factory.py` pass 100%.
  - Verify: `.venv/bin/pytest tests/unit/test_knowledge_store_factory.py`
  - Files: `it_helpdesk_agent/tools/enterprise_rag_mcp/knowledge_store.py`, `tests/unit/test_knowledge_store_factory.py`

- [x] Task 2.5: VAIS-024 — Governance date & tombstone trên backend mới
  - Description: Lọc tài liệu quá hạn / chưa hiệu lực và tombstone (`is_deleted`) trên Discovery Engine.
  - Acceptance: Unit tests verify expired & deleted docs bị loại bỏ hoàn toàn.
  - Verify: `.venv/bin/pytest tests/unit/test_vertex_search_store.py`
  - Files: `it_helpdesk_agent/tools/enterprise_rag/vertex_search_store.py`, `tests/unit/test_vertex_search_store.py`

## Epic 3: Ingestion Pipeline Mới
- [x] Task 3.1: VAIS-030 — JSONL Builder cho Discovery Engine
  - Description: Tạo `scripts/ingest/jsonl_builder.py` chuẩn hoá sang schema `structData`, lọc tombstone/expiry, và golden file test.
  - Acceptance: `tests/unit/test_jsonl_builder.py` pass 100%.
  - Verify: `.venv/bin/pytest tests/unit/test_jsonl_builder.py`
  - Files: `scripts/ingest/jsonl_builder.py`, `tests/unit/test_jsonl_builder.py`

- [x] Task 3.2: VAIS-031 — GCS Uploader & Idempotent Importer với ReconciliationMode.FULL
  - Description: Tạo `scripts/ingest/gcs_uploader.py` và `scripts/ingest/vais_importer.py` gọi `ImportDocuments` với `ReconciliationMode.FULL`.
  - Acceptance: `tests/unit/test_vais_importer.py` pass 100%.
  - Verify: `.venv/bin/pytest tests/unit/test_vais_importer.py`
  - Files: `scripts/ingest/gcs_uploader.py`, `scripts/ingest/vais_importer.py`, `tests/unit/test_vais_importer.py`

- [x] Task 3.3: VAIS-032 — Cách ly/dọn dẹp embedding và vector index
  - Description: Phân lập code embedding cũ, đảm bảo pipeline mới không phụ thuộc thủ công vào embedding generation.
  - Acceptance: Toàn bộ test suite pass 100% không suy giảm.
  - Verify: `.venv/bin/pytest tests/unit/`
  - Files: `scripts/ingest/__init__.py`, `scripts/ingest_knowledge_base.py`

- [x] Task 3.4: VAIS-033 — Dead Letter Queue Strategy & Implementation
  - Description: Viết ADR 0004 về chiến lược DLQ (Local JSONL + GCS + BQ/Cloud Logging) và triển khai ghi nhận tài liệu lỗi khi parse.
  - Acceptance: `docs/adr/0004-dead-letter-queue-strategy.md` hoàn thiện, CLI hỗ trợ `--show-dlq`.
  - Verify: `.venv/bin/pytest tests/unit/test_ingest_cli.py`
  - Files: `docs/adr/0004-dead-letter-queue-strategy.md`, `scripts/ingest/loaders.py`

- [x] Task 3.5: VAIS-034 — Unified CLI Ingest Script
  - Description: Cập nhật `scripts/ingest_knowledge_base.py` nhận `--backend {vertex_ai_search, bigquery, in_memory}`, `--dry-run`, `--data-store-id`, `--acl`.
  - Acceptance: `tests/unit/test_ingest_cli.py` pass 100% (dry-run in sample JSONL và estimated filter, exit code 0).
  - Verify: `.venv/bin/pytest tests/unit/test_ingest_cli.py`
  - Files: `scripts/ingest_knowledge_base.py`, `tests/unit/test_ingest_cli.py`

## Epic 4: Terraform & Hạ Tầng
- [x] Task 4.1: VAIS-040 — Module Vertex AI Search (`vertex_ai_search.tf`)
  - Description: Tạo `deployment/terraform/vertex_ai_search.tf` với GCS Corpus bucket, Data store, Search Engine, IAM `roles/discoveryengine.viewer`, ghi chú `acl_enabled` IMMUTABLE.
  - Acceptance: Cấu hình đúng chuẩn Terraform Google Discovery Engine.
  - Verify: `.venv/bin/pytest tests/unit/test_terraform_hcl_syntax.py`
  - Files: `deployment/terraform/vertex_ai_search.tf`

- [x] Task 4.2: VAIS-041 — Bỏ default region, thêm validation & cập nhật Runbook
  - Description: Xoá default `us-central1` trong `variables.tf`, thêm validation block giới hạn các region hợp lệ, thêm Bước 0 "Data Residency & Compliance" vào `Runbook_Onboarding_Khach_Hang.md`.
  - Acceptance: `test_vais_041_region_has_no_default_and_has_validation` pass 100%.
  - Verify: `.venv/bin/pytest tests/unit/test_terraform_hcl_syntax.py`
  - Files: `deployment/terraform/variables.tf`, `Runbook_Onboarding_Khach_Hang.md`

- [x] Task 4.3: VAIS-042 — IAM Least Privilege
  - Description: Cấp quyền tối thiểu `roles/discoveryengine.viewer` cho Cloud Run SA, chỉ cấp BQ IAM khi `knowledge_backend == "bigquery"`.
  - Acceptance: `test_vais_042_iam_least_privilege_discovery_engine` pass 100%.
  - Verify: `.venv/bin/pytest tests/unit/test_terraform_hcl_syntax.py`
  - Files: `deployment/terraform/vertex_ai_search.tf`, `deployment/terraform/main.tf`

- [x] Task 4.4: VAIS-043 — BigQuery Resources thành Conditional
  - Description: Chuyển BigQuery Dataset, Knowledge Table, DLQ Table sang `count = var.knowledge_backend == "bigquery" ? 1 : 0`, đổi default backend thành `"vertex_ai_search"`.
  - Acceptance: `test_vais_043_bigquery_resources_conditional` pass 100%.
  - Verify: `.venv/bin/pytest tests/unit/test_terraform_hcl_syntax.py`
  - Files: `deployment/terraform/main.tf`, `deployment/terraform/variables.tf`, `deployment/terraform/outputs.tf`

- [x] Task 4.5: VAIS-044 — Audit Logging cho Discovery Engine
  - Description: Bật `google_project_iam_audit_config` cho `discoveryengine.googleapis.com` với DATA_READ và DATA_WRITE.
  - Acceptance: `test_vais_044_audit_logging_configured` pass 100%.
  - Verify: `.venv/bin/pytest tests/unit/test_terraform_hcl_syntax.py`
  - Files: `deployment/terraform/main.tf`

## Checkpoint & Quality Gate
- [x] Tất cả tests pass (257/257 Unit & Integration tests)
- [x] Code review checklist cleared
