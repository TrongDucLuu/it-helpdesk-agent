# Capability Map: Migration BigQuery Vector Search → Vertex AI Search (Agent Search)

Initiative: `it-helpdesk-agent` Knowledge Layer Modernization
Architecture Baseline: 2026-09-01 (Review Findings & Migration Backlog)

## Module Decomposition

| Module ID | Responsibility | Depends On | Epic Source |
|---|---|---|---|
| `epic0-spike-adr` | Xác thực API Discovery Engine/Agent Search, vị trí `asia-southeast1`, ADR RBAC enforcement và ADR Chunking | — | Epic 0 (VAIS-001, 002, 003) |
| `epic1-p0-fixes` | Chuyển RAG sang In-Process FunctionTool, xoá `_mock_return_value`, sửa báo cáo hiệu năng thành Capacity Model | — | Epic 1 (VAIS-010, 011, 012) |
| `epic2-knowledge-adapter` | `BaseKnowledgeStore` contract, `VertexAiSearchKnowledgeStore`, `filter_builder`, 3-backend factory, Governance dates | `epic0-spike-adr`, `epic1-p0-fixes` | Epic 2 (VAIS-020..024) |
| `epic3-ingestion-pipeline` | JSONL builder, GCS uploader, `ImportDocuments` (reconciliation FULL), dọn embedder/index code, DLQ | `epic2-knowledge-adapter` | Epic 3 (VAIS-030..034) |
| `epic4-terraform-infra` | Terraform module Vertex AI Search, validation region, IAM least privilege, conditional BQ | `epic0-spike-adr`, `epic2-knowledge-adapter` | Epic 4 (VAIS-040..044) |
| `epic5-agent-layer` | L2 Agent wiring FunctionTool, `get_system_manual` full doc resolution, config top_k, RBAC-aware semantic cache | `epic1-p0-fixes`, `epic2-knowledge-adapter` | Epic 5 (VAIS-050..054) |
| `epic6-eval-quality-gates` | Multi-backend eval harness, metric precision/recall/MRR separation, 120+ eval dataset, A/B measurement, CI gate | `epic2-knowledge-adapter`, `epic5-agent-layer` | Epic 6 (VAIS-060..063) |

## Build & Execution Order

```
[Phase 1: Foundation & P0 Fixes]
├── Module epic0-spike-adr  (VAIS-001, VAIS-002, VAIS-003)
└── Module epic1-p0-fixes   (VAIS-010, VAIS-011, VAIS-012)  [Song song với Epic 0]
             │
             ▼
[Phase 2: Core Knowledge Adapter & Ingestion]
├── Module epic2-knowledge-adapter (VAIS-020..024)
├── Module epic3-ingestion-pipeline (VAIS-030..034)
└── Module epic4-terraform-infra    (VAIS-040..044)
             │
             ▼
[Phase 3: Agent Integration & Quality Gates]
├── Module epic5-agent-layer       (VAIS-050..054)
└── Module epic6-eval-quality-gates (VAIS-060..063)
```

## Hard Gates

1. **Gate 1**: Không bắt đầu Epic 2 nếu Epic 0 chưa hoàn tất ADRs và xác thực API.
2. **Gate 2**: Không merge Epic 5 nếu VAIS-010 chưa có Integration Test RBAC in-process pass (`tests/integration/test_rbac_end_to_end.py`).
3. **Gate 3**: Không đánh dấu DONE bất kỳ task nào nếu vi phạm 9 Ràng Buộc Tuyệt Đối trong `CONSTRAINTS.md`.
