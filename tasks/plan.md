# Implementation Plan: Vertex AI Search Migration & Multi-Agent Quality Gate (Epics 0 - 6)

## Overview
Kế hoạch thực hiện toàn diện di chuyển sang Vertex AI Search / Agent Search và chuẩn bị Quality Gate tự động cho hệ thống IT Helpdesk Multi-Agent AI theo quy trình chuẩn:
`spec-driven-development` $\rightarrow$ `source-driven-development` $\rightarrow$ `constraint-driven-development` $\rightarrow$ `planning-and-task-breakdown` $\rightarrow$ `incremental-implementation` $\rightarrow$ `test-driven-development`.

---

## Architecture Decisions & Constraints
- Tuân thủ 100% các Ràng Buộc Tuyệt Đối trong `CONSTRAINTS.md`.
- **In-process FunctionTool** cho L2 RAG Agent thay vì MCP stdio subprocess để đảm bảo `contextvars` SSO user không bị đứt gãy.
- **Không xoá `InMemoryKnowledgeStore`** và giữ nguyên API contract của các tool RAG (`search_enterprise_knowledge`, `get_system_manual`).
- **Server-Side RBAC Enforcement**: `allowed_systems` được tính toán độc lập tại server từ `current_sso_user`, LLM tuyệt đối không có quyền tự cấp quyền.
- **ReconciliationMode.FULL**: Tự động dọn dẹp phân mảnh mồ côi và tombstones trên Discovery Engine.
- **RBAC-Aware Semantic Cache**: SHA-256 RBAC Hash scoping ngăn chặn rò rỉ tri thức qua cache khi vai trò thay đổi; TTL phân tầng L1=3600s, L2=300s, L3=0s.
- **Multi-Chunk Document Reassembly**: Sử dụng `parent_doc_id` và `chunk_index` ghép nối trọn vẹn tài liệu hướng dẫn quy trình dài.
- **Quality Gate (Epic 6)**: Đảm bảo RBAC Leakage = 0.0%, Prompt Injection Trap Refusal = 100%, và IR Recall@3 $\ge 85.0\%$.

---

## Task Breakdown & Dependency Graph

```
[Epic 0: Spike & ADRs] (COMPLETED)
  ├── Task 0.1: VAIS-001 [x]
  ├── Task 0.2: VAIS-002 [x]
  └── Task 0.3: VAIS-003 [x]

[Epic 1: Fix P0 Defects] (COMPLETED)
  ├── Task 1.1: VAIS-010 [x]
  ├── Task 1.2: VAIS-011 [x]
  └── Task 1.3: VAIS-012 [x]

[Epic 2: Knowledge Layer Adapter Mới] (COMPLETED)
  ├── Task 2.1: VAIS-020 [x]
  ├── Task 2.2: VAIS-022 [x]
  ├── Task 2.3: VAIS-021 [x]
  ├── Task 2.4: VAIS-023 [x]
  └── Task 2.5: VAIS-024 [x]

[Epic 3: Ingestion Pipeline Mới] (COMPLETED)
  ├── Task 3.1: VAIS-030 [x]
  ├── Task 3.2: VAIS-031 [x]
  ├── Task 3.3: VAIS-032 [x]
  ├── Task 3.4: VAIS-033 [x]
  └── Task 3.5: VAIS-034 [x]

[Epic 4: Terraform & Hạ Tầng] (COMPLETED)
  ├── Task 4.1: VAIS-040 [x]
  ├── Task 4.2: VAIS-041 [x]
  ├── Task 4.3: VAIS-042 [x]
  ├── Task 4.4: VAIS-043 [x]
  └── Task 4.5: VAIS-044 [x]

[Epic 5: Agent Layer] (COMPLETED)
  ├── Task 5.1: VAIS-050 [x] (Inject allowed_systems bằng code tại server)
  ├── Task 5.2: VAIS-051 [x] (Multi-chunk reassembly qua get_system_manual)
  ├── Task 5.3: VAIS-052 [x] (Configurable RAG_TOP_K kẹp [1, 100])
  ├── Task 5.4: VAIS-053 [x] (Latency Budget 4.0s timeout & fallback tiếng Việt)
  └── Task 5.5: VAIS-054 [x] (RBAC-aware semantic cache hashing & tier TTL)

[Epic 6: Eval & Quality Gate] (PLANNED / IN PROGRESS)
  ├── Task 6.1: VAIS-060 (Multi-backend Eval Harness)
  ├── Task 6.2: VAIS-061 (Golden Dataset 120+ queries & Decoupled IR metrics)
  ├── Task 6.3: VAIS-062 (Empirical A/B Benchmark Report)
  └── Task 6.4: VAIS-063 (CI Quality Gate Script)
```

---

## Tasks & Checkpoints

### Checkpoint 1: Foundation ADRs & Spike (Epic 0) — COMPLETED
- [x] Task 0.1 (VAIS-001): Viết ADR `docs/adr/0001-knowledge-layer-agent-search.md` và script `scripts/spike/vais_smoke.py`.
- [x] Task 0.2 (VAIS-002): Viết ADR `docs/adr/0002-rbac-enforcement.md` so sánh Option A & Option B.
- [x] Task 0.3 (VAIS-003): Viết ADR `docs/adr/0003-chunking-strategy.md` phân tích Chunking trade-offs.

### Checkpoint 2: P0 Architecture & Report Fixes (Epic 1) — COMPLETED
- [x] Task 1.1 (VAIS-010): Tạo `it_helpdesk_agent/tools/enterprise_rag/rag_tools.py`, cập nhật `agent.py`, viết `tests/integration/test_rbac_end_to_end.py`.
- [x] Task 1.2 (VAIS-011): Xoá tất cả kiểm tra `_mock_return_value` trong `it_helpdesk_agent/`.
- [x] Task 1.3 (VAIS-012): Cập nhật `SCALABILITY_PERFORMANCE_REPORT.md` thành Capacity Model lý thuyết + đánh dấu `CHƯA ĐO`.

### Checkpoint 3: Knowledge Layer Adapter Mới (Epic 2) — COMPLETED
- [x] Task 2.1 (VAIS-020): Cập nhật `SearchResult` (`chunk_id`, `parent_doc_id`, chuẩn hóa `relevance_score` $[0.0, 1.0]$), viết `tests/unit/test_schema_parity.py`.
- [x] Task 2.2 (VAIS-022): Viết `it_helpdesk_agent/tools/enterprise_rag/filter_builder.py` và `tests/unit/test_filter_builder_fuzz.py`.
- [x] Task 2.3 (VAIS-021): Viết `it_helpdesk_agent/tools/enterprise_rag/vertex_search_store.py` và `tests/unit/test_vertex_search_store.py`.
- [x] Task 2.4 (VAIS-023): Cập nhật `get_knowledge_store` factory trong `knowledge_store.py` và `tests/unit/test_knowledge_store_factory.py`.
- [x] Task 2.5 (VAIS-024): Governance date & tombstone filter tests và logic cho `VertexAiSearchKnowledgeStore`.

### Checkpoint 4: Ingestion Pipeline Mới (Epic 3) — COMPLETED
- [x] Task 3.1 (VAIS-030): Xây dựng `scripts/ingest/jsonl_builder.py` và golden file tests trong `tests/unit/test_jsonl_builder.py`.
- [x] Task 3.2 (VAIS-031): Xây dựng `scripts/ingest/gcs_uploader.py`, `scripts/ingest/vais_importer.py` và tests `tests/unit/test_vais_importer.py`.
- [x] Task 3.3 (VAIS-032): Dọn dẹp code embedding cũ và vector index coverage, giữ test suite 100% xanh.
- [x] Task 3.4 (VAIS-033): Cấu trúc DLQ ghi nhận tài liệu lỗi khi parse (`docs/adr/0004-dead-letter-queue-strategy.md`).
- [x] Task 3.5 (VAIS-034): Viết CLI `scripts/ingest_knowledge_base.py` hỗ trợ `--backend`, `--dry-run`, `--data-store-id`.

### Checkpoint 5: Terraform & Hạ Tầng (Epic 4) — COMPLETED
- [x] Task 4.1 (VAIS-040): Module `vertex_ai_search.tf` tạo Bucket, Data Store, Search Engine, IAM.
- [x] Task 4.2 (VAIS-041): Bỏ default region, thêm validation & cập nhật Bước 0 trong Runbook.
- [x] Task 4.3 (VAIS-042): IAM Least Privilege `roles/discoveryengine.viewer`.
- [x] Task 4.4 (VAIS-043): BigQuery resources thành conditional.
- [x] Task 4.5 (VAIS-044): Cloud Audit Logging cho Discovery Engine.

### Checkpoint 6: Agent Layer (Epic 5) — COMPLETED
- [x] Task 5.1 (VAIS-050): Server-side RBAC Injection cho `search_enterprise_knowledge`.
- [x] Task 5.2 (VAIS-051): Multi-chunk Document Reassembly trong `get_system_manual`.
- [x] Task 5.3 (VAIS-052): Configurable `RAG_TOP_K` kẹp $[1, 100]$.
- [x] Task 5.4 (VAIS-053): Latency Budget 4.0s timeout & graceful Vietnamese fallback.
- [x] Task 5.5 (VAIS-054): RBAC-aware semantic cache key hashing & Tier-specific TTLs.

### Checkpoint 7: Eval & Quality Gate (Epic 6) — PLANNED
- [ ] Task 6.1 (VAIS-060): Nâng cấp Eval Harness hỗ trợ đa backend (`--store {in_memory, bigquery, vertex_ai_search}`).
- [ ] Task 6.2 (VAIS-061): Mở rộng Golden Dataset lên $\ge 120$ queries và decoupled IR metrics (Precision@k, Recall@k, MRR, RBAC Leakage Rate).
- [ ] Task 6.3 (VAIS-062): Báo cáo A/B Benchmark thực nghiệm BigQuery vs Vertex AI Search.
- [ ] Task 6.4 (VAIS-063): CI Quality Gate script `scripts/ci/check_eval_quality_gate.py`.

### Final Verification Status
- Toàn bộ unit & integration tests pass: **274/274 tests passed** (100%).
- Zero mock references: `grep -rn "_mock_return_value" it_helpdesk_agent/` = 0.
- Schema parity check 100% pass across all 3 stores.
