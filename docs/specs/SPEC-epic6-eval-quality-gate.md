# Technical Specification: Epic 6 — Evaluation & Quality Gate (VAIS-060 → VAIS-063)

**Author:** Solution Architect Đức (Gimasys) & Antigravity  
**Date:** 2026-09-01  
**Status:** DRAFT / PENDING_REVIEW  
**Relevant Skills:** `spec-driven-development`, `source-driven-development`, `constraint-driven-development`, `planning-and-task-breakdown`

---

## 1. Overview & Business Objectives

Epic 6 is the critical validation layer for presales and production gating. It replaces static mock-assumed benchmarks with empirical retrieval accuracy metrics (Precision@k, Recall@k, MRR, Hit Rate, RBAC Leakage Rate, Latency p50/p95) evaluated systematically across multiple knowledge backends (`InMemoryKnowledgeStore`, `VertexAiSearchKnowledgeStore`, and conditional `BigQueryVectorKnowledgeStore`).

### Quality Gate Hard Requirements
1. **RBAC Leakage Rate**: Must be strictly `0.0%` (Zero-Tolerance).
2. **Indirect Prompt Injection Defense Rate**: Must be strictly `100.0%`.
3. **Retrieval Recall@3**: Must be $\ge 85.0\%$ (or within 5% degradation against committed baseline).
4. **Intent & Routing Accuracy**: Must be $\ge 85.0\%$.
5. **Trap Question Refusal Rate**: Must be $\ge 90.0\%$.

---

## 2. Architectural Design & Task Breakdown

```mermaid
graph TD
    A[Golden Dataset: >=120 cases] --> B[Eval Runner: eval_harness.py]
    B --> C{Store Backend Factory}
    C -->|--store in_memory| D[InMemoryKnowledgeStore]
    C -->|--store vertex_ai_search| E[VertexAiSearchKnowledgeStore]
    C -->|--store bigquery| F[BigQueryVectorKnowledgeStore]
    
    B --> G[Metric Evaluator]
    G --> H[Precision@k, Recall@k, MRR, Hit Rate]
    G --> I[RBAC Leakage & Security Isolation]
    G --> J[p50 / p95 Latency Measurement]
    
    G --> K[CI Quality Gate: check_eval_quality_gate.py]
    G --> L[Benchmark Report: ab_bigquery_vs_agent_search.md]
```

### Tasks:
1. **VAIS-060: Multi-Backend Eval Harness**
   - Refactor `run_eval_suite(store: Optional[BaseKnowledgeStore] = None, backend_name: Optional[str] = None)` to accept store instances and backend selector.
   - CLI flags `--store {in_memory, bigquery, vertex_ai_search}` or `--backend`.
   - Explicit backend name and environment metadata in output header.
   - Documented in source code with official links.

2. **VAIS-061: Expanded Golden Evaluation Dataset & Standardized Metrics**
   - Decouple Precision@k, Recall@k, and MRR.
   - Expand `data/eval/golden_dataset_vais.json` to $\ge 120$ comprehensive test cases:
     - $\ge 30$ Natural Vietnamese queries with zero technical codes (no ME21N, OB52, SU01, etc.).
     - $\ge 15$ RBAC negative security queries (unauthorized user attempting to access ERP/HRM/CRM docs).
     - $\ge 10$ Content Governance queries (expired or deleted documents).
     - $\ge 10$ Indirect Prompt Injection queries.
     - $\ge 55$ Standard domain queries across ERP, HRM, CRM, L1 FAQ, and L3 RCA.

3. **VAIS-062: Empirical A/B Benchmark Report**
   - Run benchmark across available backends.
   - Generate `docs/eval/ab_bigquery_vs_agent_search_2026-09-01.md` containing real measurements for `in_memory` and `vertex_ai_search` (with explicit offline notes when GCP credentials are not present).

4. **VAIS-063: CI Quality Gate Integration**
   - Implement `scripts/ci/check_eval_quality_gate.py`.
   - Read metrics from eval suite, compare against `data/eval/baseline_metrics.json`.
   - Exit with code 0 if all quality gates pass, exit code 1 if any gate is breached.

---

## 3. Official Documentation & Source-Driven Citations
- **Vertex AI Search REST & Python API**: https://cloud.google.com/generative-ai-app-builder/docs/preview-search-results
- **Information Retrieval Metrics (TREC Standards)**: Precision@k, Recall@k, Mean Reciprocal Rank (MRR).

---

## 4. Verification & Testing Strategy
- Unit test suite: `tests/unit/test_epic6_eval_quality_gate.py` covering:
  - Multi-backend switching in eval harness.
  - Correct mathematical calculation of Precision@k, Recall@k, MRR.
  - RBAC negative case validation (assert 0 leaked results).
  - Content governance exclusion (assert 0 expired/deleted documents retrieved).
  - CI quality gate pass/fail thresholds.
