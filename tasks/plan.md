# Implementation Plan: Vertex AI Search Migration & Knowledge Layer (Epic 0, 1, 2, 3)

## Overview
Kế hoạch thực hiện Epic 0 (Spike & ADRs), Epic 1 (Sửa lỗi P0), Epic 2 (Knowledge Layer Adapter Mới), và Epic 3 (Ingestion Pipeline Mới) theo quy trình `spec-driven-development`, `source-driven-development`, `constraint-driven-development`, `planning-and-task-breakdown`, `incremental-implementation`, và `test-driven-development`.

---

## Architecture Decisions & Constraints
- Tuân thủ 100% 9 Ràng Buộc Tuyệt Đối trong `CONSTRAINTS.md`.
- In-process FunctionTool cho RAG thay vì MCP stdio subprocess để đảm bảo `contextvars` SSO user không bị đứt gãy.
- Không xoá `InMemoryKnowledgeStore` và giữ nguyên API contract của các tool RAG.
- Mọi tài liệu kỹ thuật về Vertex AI Search / Discovery Engine (Agent Search) phải có link Google Cloud official documentation.
- Chuẩn hóa `relevance_score` về $[0.0, 1.0]$ trên mọi backend knowledge store.
- ImportDocuments với `reconciliation_mode=FULL` để tự động dọn dẹp orphan documents & tombstones.

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

[Epic 3: Ingestion Pipeline Mới]
  ├── Task 3.1: VAIS-030 (JSONL builder + golden file tests)
  ├── Task 3.2: VAIS-031 (GCS upload + ImportDocuments idempotent)
  ├── Task 3.3: VAIS-032 (Dọn dẹp code embedding & vector index cũ)
  ├── Task 3.4: VAIS-033 (Dead Letter Queue handling)
  └── Task 3.5: VAIS-034 (CLI Ingestion tool scripts/ingest_knowledge_base.py)
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

### Checkpoint 4: Ingestion Pipeline Mới (Epic 3)
- [ ] Task 3.1 (VAIS-030): Xây dựng `scripts/ingest/jsonl_builder.py` và golden file tests trong `tests/unit/test_jsonl_builder.py`.
- [ ] Task 3.2 (VAIS-031): Xây dựng `scripts/ingest/gcs_uploader.py`, `scripts/ingest/vais_importer.py` và tests `tests/unit/test_vais_importer.py`.
- [ ] Task 3.3 (VAIS-032): Dọn dẹp code embedding cũ và vector index coverage, giữ test suite 100% xanh.
- [ ] Task 3.4 (VAIS-033): Cấu trúc DLQ ghi nhận tài liệu lỗi khi parse.
- [ ] Task 3.5 (VAIS-034): Viết CLI `scripts/ingest_knowledge_base.py` hỗ trợ `--backend`, `--dry-run`, `--data-store-id`.

### Final Verification Checkpoint
- [ ] Toàn bộ unit tests pass: `pytest tests/unit/`
- [ ] Toàn bộ integration tests pass: `pytest tests/integration/`
- [ ] Zero mock references: `grep -rn "_mock_return_value" it_helpdesk_agent/` = 0
- [ ] Schema parity check 100% pass across all 3 stores
