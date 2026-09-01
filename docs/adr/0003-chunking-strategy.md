# ADR 0003: Retrieval Granularity & Chunking Strategy

- **Status**: Accepted
- **Date**: 2026-09-01
- **Deciders**: Solution Architect Đức (Gimasys), Technical Lead, Antigravity
- **Source Documents**:
  - Vertex AI Search Document Processing & Chunking: https://cloud.google.com/generative-ai-app-builder/docs/snippets
  - Import Documents Structure: https://cloud.google.com/generative-ai-app-builder/docs/import-documents
  - Parsing & Extractive Content: https://cloud.google.com/generative-ai-app-builder/docs/content-search-spec

---

## 1. Context & Problem Statement
Trong kiến trúc RAG cho IT Helpdesk, câu hỏi của người dùng có 2 dạng nhu cầu truy xuất với độ chi tiết (granularity) hoàn toàn khác nhau:
1. **Truy vấn điểm (Point Query / Snippet Search)**: Người dùng hỏi một thông tin cụ thể (ví dụ: *"Hạn nộp báo cáo chi phí là ngày nào?"*, *"Ai duyệt đơn nghỉ phép > 3 ngày?"*). Tool: `search_enterprise_knowledge`.
2. **Truy vấn tài liệu hoàn chỉnh (Full Document Retrieval)**: Người dùng hoặc Agent cần đọc toàn bộ quy trình/hướng dẫn vận hành của một hệ thống (ví dụ: *"Cho tôi xem toàn bộ cẩm nang mua sắm ERP"*). Tool: `get_system_manual`.

Tại tầng ingestion & storage, ta đứng trước 2 hướng tiếp cận phân đoạn dữ liệu (Chunking Strategy):
- **Chiến lược 1 (Client-Side Chunking — `chunkers.py`)**: Hệ thống tự băm nhỏ tài liệu Markdown thành các chunks (ví dụ: 500 tokens, 100 overlap), mỗi chunk là một Document riêng biệt trong Data Store.
- **Chiến lược 2 (Managed Layout-Aware Chunking & Document-Level Storage)**: Lưu toàn bộ tài liệu gốc làm một Document trong Data Store, kích hoạt tính năng tự động phân tích cấu trúc (layout-aware parsing), trích xuất đoạn trích liên quan (`extractive_content_spec` / `snippet_spec`) do Google Discovery Engine quản lý.

---

## 2. Trade-off Analysis

| Tiêu Chí | Client-Side Chunking (`chunkers.py`) | Managed Layout-Aware Chunking (Agent Search) |
|---|---|---|
| **Cấu trúc bảng biểu & Tiêu đề** | Dễ bị cắt ngang bảng Markdown hoặc tách rời câu khỏi tiêu đề ngữ cảnh | Giữ nguyên ngữ cảnh phân cấp (Heading 1 -> Heading 2 -> Paragraph) |
| **Hỗ trợ `get_system_manual`** | Rất khó. Phải ghép nối hàng chục chunks bị xáo trộn thứ tự | Cực kỳ đơn giản: Truy xuất trực tiếp raw document content theo `doc_id` |
| **Độ chính xác Snippet (`search_enterprise_knowledge`)** | Phụ thuộc vào kích thước chunk cố định (fixed window) | Tối ưu bằng Extractive Segment & Snippet ML Models của Google |
| **Độ phức tạp Ingestion Pipeline** | Cao (phải quản lý code chunker, token counter, overlap, chunk id mapping) | Thấp (chỉ cần serialize Markdown/Text thành file JSONL nạp vào GCS) |
| **Tái sử dụng cho Offline Store** | Đòi hỏi `InMemoryKnowledgeStore` phải chạy cùng logic chunking | `InMemoryKnowledgeStore` lưu document và thực hiện keyword/regex matching trực tiếp |

---

## 3. Decision Outcome

1. **Adopt Managed Layout-Aware Chunking for Vertex AI Search**:
   - Ingestion Pipeline (`scripts/ingest_to_vertex_search.py` / `JsonlBuilder`) sẽ lưu trữ **mỗi file tài liệu là một Document duy nhất** trong Discovery Engine, chứa toàn bộ nội dung Markdown trong trường `content` hoặc `struct_data`.
   - Đối với `search_enterprise_knowledge`: Sử dụng `SearchRequest.ContentSearchSpec` với `snippet_spec.return_snippet = True` và `extractive_content_spec.max_extractive_segment_count = 3` để trích xuất các đoạn trích liên quan nhất cùng điểm liên quan (relevance score).
   - Đối với `get_system_manual`: Truy xuất trực tiếp nội dung đầy đủ của Document hoặc query với filter `system: "<SYSTEM>"` và lấy toàn bộ raw content.
2. **Preserve `InMemoryKnowledgeStore` Contract**:
   - `InMemoryKnowledgeStore` tiếp tục hỗ trợ cả tìm kiếm đoạn trích ngắn và lấy toàn bộ manual, đảm bảo 100% test offline và eval harness hoạt động ổn định mà không cần băm chunk thủ công.
3. **Deprecate Custom `chunkers.py` in Production Pipeline**:
   - Tinh gọn mã nguồn, loại bỏ sự phụ thuộc vào logic chunking cố định ở client side trong pipeline Agent Search.

---

## 4. Consequences
- Đơn giản hoá đáng kể pipeline nạp tài liệu (Ingestion Pipeline).
- Nâng cao tính chính xác của câu trả lời cho các câu hỏi liên quan đến bảng biểu phức tạp trong quy trình ERP/HRM.
- Đáp ứng hoàn hảo cả hai tool contract `search_enterprise_knowledge` và `get_system_manual`.
