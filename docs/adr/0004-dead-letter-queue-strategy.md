# ADR 0004: Dead Letter Queue (DLQ) Strategy for Agent Search Ingestion

## Status
ACCEPTED

## Context
Trong hệ thống ingestion pipeline cho Vertex AI Search (Agent Search / Discovery Engine), tài liệu từ khách hàng (PDF, Word, Markdown, HTML) có thể gặp các lỗi:
1. File hỏng (corrupted PDF, bad encoding).
2. Thiếu cấu trúc bắt buộc hoặc metadata không hợp lệ (hệ thống không nằm trong danh sách whitelist).
3. Lỗi upload GCS hoặc lỗi format JSONL.

Trước đây khi dùng BigQuery, DLQ được ghi vào bảng BigQuery `ingestion_dead_letter_queue`.
Khi chuyển sang Agent Search, chúng ta cần quyết định cơ chế lưu trữ DLQ độc lập, bền vững và quan sát được.

## Decision
Chúng tôi quyết định áp dụng **Dual DLQ Strategy (Local/GCS JSONL + BigQuery/Cloud Logging)**:
1. **Mặc định (Local & GCS JSONL DLQ)**:
   - Các tài liệu lỗi ở mọi giai đoạn (Parsing, Chunking, Schema Validation, GCS Upload) được ghi thành từng dòng JSON vào file DLQ:
     - Local: `data/dlq/ingestion_dlq.jsonl`
     - GCS (trong môi trường Cloud): `gs://<CORPUS_BUCKET>/dlq/<JOB_ID>.jsonl`
   - Cấu trúc mỗi bản ghi DLQ:
     ```json
     {
       "id": "dlq_uuid",
       "stage": "parsing | chunking | schema_validation | upload",
       "file_path": "path/to/corrupted.pdf",
       "error_message": "Detailed exception trace",
       "doc_title": "Optional title if parsed",
       "occurred_at": "ISO-8601 timestamp"
     }
     ```
2. **Tuỳ chọn Enterprise Observability (BigQuery DLQ Table)**:
   - Nếu `project_id` và `dataset_id` được cấu hình, pipeline tiếp tục stream các bản ghi DLQ vào bảng BigQuery `ingestion_dead_letter_queue` để phục vụ Dashboard giám sát chất lượng dữ liệu.
3. **Fail-Closed & Isolation**:
   - Lỗi của một tài liệu đơn lẻ được cô lập vào DLQ và không làm sập toàn bộ đợt ingestion của các tài liệu hợp lệ khác. Tuy nhiên, tổng kết job sẽ log rõ số lượng bản ghi DLQ phát sinh.

## Consequences
- Tách biệt hoàn toàn việc lưu trữ DLQ khỏi cơ chế tìm kiếm tri thức.
- Dễ dàng kiểm tra và replay các tài liệu lỗi bằng lệnh CLI: `python scripts/ingest_knowledge_base.py --show-dlq`.
