# Technical Specification: Epic 3 — Ingestion Pipeline Mới cho Agent Search (Vertex AI Search)

**Target Backlog Tasks:** VAIS-030, VAIS-031, VAIS-032, VAIS-033, VAIS-034  
**Date:** 2026-09-01  
**Status:** DRAFT (Ready for Review)  

---

## 1. Mục tiêu và Bối cảnh

Hệ thống RAG doanh nghiệp chuyển đổi từ BigQuery Vector Search sang Google Cloud Vertex AI Search (Agent Search / Discovery Engine).
Epic 3 chịu trách nhiệm xây dựng Ingestion Pipeline mới đảm bảo:
1. **Chuẩn hoá định dạng tài liệu**: Chuyển đổi corpus markdown, HTML, PDF sang JSONL chuẩn Discovery Engine schema (`id`, `structData`, `content`).
2. **Đồng bộ Idempotent & Tự động dọn dẹp**: Tải JSONL lên GCS và thực thi `ImportDocuments` với `ReconciliationMode.FULL` — tự động xóa các chunk mồ côi hoặc tài liệu đã bị xoá khỏi nguồn.
3. **Loại bỏ phụ thuộc Vector Index thủ công**: Loại bỏ mã nguồn sinh embedding tự chế (`text-embedding-005` custom vectors) mà giao cho Agent Search quản trị embedding, semantic index, và BM25 hybrid ranking tự động.
4. **Dead Letter Queue (DLQ)**: Ghi nhận và cách ly các tài liệu lỗi/hỏng cấu trúc mà không làm gián đoạn pipeline.
5. **CLI Ingestion linh hoạt**: Cung cấp công cụ dòng lệnh `scripts/ingest_knowledge_base.py` hỗ trợ cả chế độ dry-run, chuyển đổi backend, và báo cáo tiến trình.

---

## 2. Ràng buộc Tuân thủ (CONSTRAINTS.md)

1. **Fail-Closed**: Bất kỳ lỗi parse nghiêm trọng hoặc lỗi import đều được ghi nhận vào DLQ và dừng lại an toàn; không âm thầm nuốt lỗi.
2. **Source-Driven Development**: Mọi API call tới `discoveryengine_v1` phải trích dẫn link doc chính thức của Google:
   - *ImportDocuments API*: `https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.services.document_service.DocumentServiceClient#google_cloud_discoveryengine_v1_services_document_service_DocumentServiceClient_import_documents`
   - *Document Format (JSONL schema)*: `https://cloud.google.com/generative-ai-app-builder/docs/prepare-data#jsonl`
   - *Reconciliation Mode*: `https://cloud.google.com/generative-ai-app-builder/docs/manage-data-stores#reconcile`
3. **Data Integrity**: Giữ nguyên `wrap_retrieved_document()` và `INDIRECT_PROMPT_INJECTION_DEFENSE_INSTRUCTION`.
4. **Một task = Một commit = Một test suite**.

---

## 3. Kiến trúc Chi tiết từng Task

### Task 3.1 (VAIS-030) — JSONL Builder (`scripts/ingest/jsonl_builder.py`)
- **Input**: Danh sách parsed documents / articles từ `parsers.py` (và `chunkers.py` nếu áp dụng chunking theo ADR-0003).
- **Output**: File JSONL theo schema chuẩn của Discovery Engine:
  ```json
  {
    "id": "ERP-KB-001",
    "jsonData": "{\"system\":\"ERP\",\"title\":\"SAP PO Guide\",\"category\":\"Finance\",\"content\":\"...\",\"keywords\":[\"sap\",\"po\"],\"owner\":\"erp@company.com\",\"source_uri\":\"docs/po.md\",\"effective_date\":\"2025-01-01\",\"expiry_date\":null,\"is_deleted\":false,\"parent_doc_id\":\"ERP-KB-001\",\"chunk_id\":\"ERP-KB-001-c1\",\"chunk_index\":0}",
    "structData": {
      "system": "ERP",
      "title": "SAP PO Guide",
      "category": "Finance",
      "content": "Full text...",
      "keywords": ["sap", "po"],
      "owner": "erp@company.com",
      "source_uri": "docs/po.md",
      "effective_date": "2025-01-01",
      "expiry_date": null,
      "is_deleted": false,
      "parent_doc_id": "ERP-KB-001",
      "chunk_id": "ERP-KB-001-c1",
      "chunk_index": 0,
      "section_hierarchy": {
        "h1": "SAP",
        "h2": "PO",
        "h3": "Guide"
      }
    }
  }
  ```
- **Tombstone Exclusion**: Tài liệu có `is_deleted = True` hoặc `expiry_date < CURRENT_DATE` sẽ bị loại bỏ ngay từ bước sinh JSONL (trừ khi có cờ `--include-deleted`).
- **Test**: Golden file validation với 3 tài liệu mẫu trong `data/knowledge_base/`.

### Task 3.2 (VAIS-031) — GCS Uploader & Idempotent Import (`scripts/ingest/vais_importer.py` & `gcs_uploader.py`)
- **GCS Uploader**: Tải JSONL đã sinh lên bucket corpus (`gs://<CORPUS_BUCKET>/ingest/<TIMESTAMP>/documents.jsonl`).
- **VAIS Importer**:
  - Khởi tạo `discoveryengine_v1.DocumentServiceClient`.
  - Gọi `import_documents(request=discoveryengine_v1.ImportDocumentsRequest(parent=..., gcs_source=..., reconciliation_mode=discoveryengine_v1.ImportDocumentsRequest.ReconciliationMode.FULL))`.
  - Chờ Long Running Operation (LRO) hoặc trả Operation ID với poll status.
- **Test**: Unit test với mock DocumentServiceClient và mock GCS client, kiểm thử cả nhánh thành công và lỗi (500, permission denied).

### Task 3.3 (VAIS-032) — Dọn dẹp Code Embedding & Vector Index BQ
- **Hành động**:
  - Xoá `scripts/ingest/embedders.py` và `it_helpdesk_agent/app_utils/embedding_utils.py` (nếu không còn component nào tham chiếu).
  - Cập nhật các import và code tests để không còn phụ thuộc vào `vertexai.language_models.TextEmbeddingModel` và `EMBEDDING_DIMENSIONS`.
  - Đảm bảo toàn bộ test suite vẫn chạy thành công 100%.

### Task 3.4 (VAIS-033) — Dead Letter Queue (DLQ)
- **Thiết kế**:
  - Khi parser hoặc JSONL builder gặp tài liệu hỏng / không đọc được / thiếu trường bắt buộc: ghi record vào DLQ log file hoặc BigQuery DLQ table (nếu cấu hình BQ).
  - Record cấu trúc: `{"file_path": str, "stage": str, "error_message": str, "timestamp": str}`.
- **Test**: Unit test ném file rác / corrupted PDF vào pipeline và xác nhận record được ghi đúng cấu trúc vào DLQ.

### Task 3.5 (VAIS-034) — Unified CLI Ingestion Script (`scripts/ingest_knowledge_base.py`)
- **CLI Arguments**:
  - `--backend {vertex_ai_search, bigquery, in_memory}` (default: `vertex_ai_search`).
  - `--source-dir` (default: `data/knowledge_base/`).
  - `--gcs-bucket` (GCS bucket for upload).
  - `--data-store-id` (Target Discovery Engine datastore).
  - `--dry-run` (Chỉ parse và sinh JSONL mẫu, không upload hay gọi API).
  - `--output-jsonl` (Đường dẫn lưu file JSONL output).
- **Exit Codes**: `0` on success, `1` on error.

---

## 4. Verification Plan & Test Strategy

| Test File | Phạm vi kiểm thử |
|---|---|
| `tests/unit/test_jsonl_builder.py` | Kiểm thử sinh JSONL, định dạng schema, tombstone filter, golden file parity. |
| `tests/unit/test_vais_importer.py` | Kiểm thử GCS upload và gọi `ImportDocuments` với `reconciliation_mode=FULL`. |
| `tests/unit/test_dlq.py` | Kiểm thử bắt lỗi parse và ghi nhận DLQ. |
| `tests/unit/test_ingest_cli.py` | Kiểm thử CLI với `--dry-run`, backend flags, invalid params. |

---
