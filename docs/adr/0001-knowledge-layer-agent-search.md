# ADR 0001: Knowledge Layer Migration — Vertex AI Search (Agent Search)

- **Status**: Accepted
- **Date**: 2026-09-01
- **Deciders**: Solution Architect Đức (Gimasys), Technical Lead, Antigravity
- **Source Documents**:
  - Vertex AI Search Locations: https://cloud.google.com/generative-ai-app-builder/docs/locations
  - Data Store Creation & Content Config: https://cloud.google.com/generative-ai-app-builder/docs/create-data-store-es
  - Metadata Filtering Syntax: https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
  - Snippets & Content Search Spec: https://cloud.google.com/generative-ai-app-builder/docs/snippets
  - Import Documents & Reconciliation Modes: https://cloud.google.com/generative-ai-app-builder/docs/import-documents
  - Document-Level Access Control (ACL): https://cloud.google.com/generative-ai-app-builder/docs/document-level-access

---

## 1. Context & Problem Statement
Hệ thống IT Helpdesk Multi-Agent hiện đang sử dụng BigQuery Vector Search làm knowledge layer cho `l2_enterprise_rag_agent`. Mặc dù BigQuery Vector Search đáp ứng được nhu cầu ban đầu, hệ thống gặp các giới hạn lớn khi mở rộng:
1. Độ trễ truy vấn (p95 latency) cao do BigQuery là data warehouse phân tán, không tối ưu cho point query realtime < 300ms.
2. Thiếu cơ chế hybrid search tích hợp sẵn (dense vector + sparse BM25 keyword + semantic ranking).
3. Đội ngũ kỹ thuật phải tự duy trì embedding pipeline, chunking, indexing và rate limiting phức tạp.
4. Google Cloud đã ra mắt Agent Search (trước đây là Vertex AI Search / Discovery Engine), cung cấp managed indexing, layout-aware parsing, auto-chunking, extractive snippets và hybrid search với SLA enterprise.

Hệ thống cần chuyển đổi sang Vertex AI Search (Agent Search) đồng thời giải quyết các câu hỏi kiến trúc nền tảng.

---

## 2. API Surface & SDK Validation

### 2.1. Thư Viện & Phiên Bản API
- **Python Package**: `google-cloud-discoveryengine>=0.13.0`
- **Module**: `google.cloud.discoveryengine_v1` (GA API Surface).
  - `SearchServiceClient`: Thực hiện truy vấn ngữ nghĩa, lọc metadata và trích xuất snippets.
  - `DocumentServiceClient`: Quản lý tài liệu và thực hiện bulk import từ GCS JSONL (`reconciliation_mode=FULL` hoặc `INCREMENTAL`).
  - `DataStoreServiceClient`: Quản lý vòng đời Data Store (`create_data_store`, `get_data_store`).
- **Endpoint Regional**: `https://{location}-discoveryengine.googleapis.com` (qua `google.api_core.client_options.ClientOptions(api_endpoint=...)`).

### 2.2. Hỗ Trợ Vùng (Location Support)
- Vùng `asia-southeast1` (Singapore) được hỗ trợ chính thức bởi Discovery Engine API.
- Cấu hình client:
  ```python
  from google.api_core.client_options import ClientOptions
  from google.cloud import discoveryengine_v1 as discoveryengine

  client_options = ClientOptions(api_endpoint="asia-southeast1-discoveryengine.googleapis.com")
  client = discoveryengine.SearchServiceClient(client_options=client_options)
  ```

### 2.3. Cú Pháp Metadata Filter
- Bộ lọc `filter` được truyền trực tiếp trong `discoveryengine.SearchRequest`.
- Cú pháp chuẩn theo tài liệu Google Cloud:
  - So khớp tập hợp (ANY): `system: ANY("ERP", "HRM")`
  - So khớp chính xác: `system: "ERP"`
  - Logic kết hợp: `system: ANY("ERP") AND doc_type: "guide"`
- **Lưu ý**: Tên trường và giá trị là case-sensitive. Trường lọc phải được định nghĩa trong schema của Data Store hoặc cấu hình `struct_data`.

### 2.4. Tính Bất Biến Của `acl_enabled`
- Cờ `acl_enabled` là **IMMUTABLE** (bất biến) được thiết lập tại thời điểm gọi `DataStoreServiceClient.create_data_store`.
- Một khi Data Store đã được tạo, không thể thay đổi `acl_enabled` giữa `true` và `false`. Việc chuyển đổi giữa Option A (Metadata filter) và Option B (Document ACL) đòi hỏi phải tạo Data Store mới và re-index toàn bộ dữ liệu.

### 2.5. Giới Hạn Của ADK `VertexAiSearchTool` Built-in
ADK (Agent Development Kit) cung cấp sẵn `VertexAiSearchTool`, tuy nhiên công cụ này không phù hợp cho kiến trúc phân quyền enterprise:
1. Không cho phép server-side code tự động inject `allowed_systems` từ `current_sso_user` một cách an toàn mà không qua LLM parameter.
2. Không hỗ trợ đóng gói XML an toàn (`wrap_retrieved_document`) để chống Indirect Prompt Injection.
3. Không hỗ trợ abstraction đa backend (không thể chuyển đổi mượt mà sang `InMemoryKnowledgeStore` khi chạy unit test offline hoặc eval harness).

**Quyết định**: Xây dựng Custom In-Process `FunctionTool` bọc quanh `VertexAiSearchKnowledgeStore` kế thừa `BaseKnowledgeStore`.

---

## 3. Decision Outcome

1. **Adopt `google-cloud-discoveryengine_v1`**: Sử dụng `SearchServiceClient` và `DocumentServiceClient` làm backend adapter chính.
2. **Triển khai kiến trúc Adapter**: Tạo `VertexAiSearchKnowledgeStore` kế thừa `BaseKnowledgeStore` chung với `InMemoryKnowledgeStore` và `BigQueryKnowledgeStore`.
3. **Regional Endpoint**: Sử dụng `asia-southeast1` làm vùng mặc định cho staging và production.
4. **Tool Pattern**: Sử dụng ADK `FunctionTool` in-process trong `it_helpdesk_agent/tools/enterprise_rag/rag_tools.py`.

---

## 4. Consequences

### Positive
- Tận dụng managed hybrid search, layout parsing và extractive snippets từ Google.
- Giảm thiểu độ trễ truy vấn knowledge base từ hàng giây (BigQuery) xuống < 300ms (Agent Search).
- Giữ vững 100% test coverage offline nhờ `InMemoryKnowledgeStore`.

### Negative / Trade-offs
- Cần duy trì JSONL serialization pipeline cho GCS import.
- Chi phí hạ tầng cho Data Store và search queries trên Vertex AI Search.
