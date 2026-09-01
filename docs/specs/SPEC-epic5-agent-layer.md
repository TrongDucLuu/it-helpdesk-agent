# Technical Specification: Epic 5 — Agent Layer Optimization

**Target Backlog Tasks:** VAIS-050, VAIS-051, VAIS-052, VAIS-053, VAIS-054  
**Date:** 2026-09-01  
**Status:** DRAFT (Ready for Review)  

---

## 1. Mục tiêu và Bối cảnh

Epic 5 tập trung vào việc hoàn thiện tầng tương tác của Agent (L2 Enterprise Systems & RAG Specialist) và Root Orchestrator:
1. **VAIS-050 (L2 Agent Tool Suite)**: Bảo đảm L2 agent sử dụng trực tiếp các in-process `FunctionTool` (`search_enterprise_knowledge`, `get_system_manual`, `draft_email_response`, ticketing tools) với context SSO được duy trì xuyên suốt.
2. **VAIS-051 (`get_system_manual` Reassembly)**: Khắc phục lỗi trả về đoạn trích (chunk) đơn lẻ khi gọi `get_system_manual`. Tập hợp và ghép nối đầy đủ toàn bộ các chunk của một tài liệu theo đúng thứ tự `chunk_index` dựa trên `parent_doc_id`.
3. **VAIS-052 (`top_k` Cấu hình Linh hoạt)**: Hỗ trợ biến môi trường `RAG_TOP_K` (default 8, fallback bảo vệ giới hạn $[1, 100]$).
4. **VAIS-053 (RBAC-Aware Semantic Cache)**: Bổ sung hash của `allowed_systems` vào cache key để ngăn chặn triệt để việc lộ lọt dữ liệu qua cache khi vai trò của user bị thu hồi. Thiết lập TTL riêng biệt cho L2 ngắn hơn L1.
5. **VAIS-054 (Latency Budget & Graceful Timeout)**: Đặt `RAG_SEARCH_TIMEOUT_SECONDS` (mặc định 4.0s) với cơ chế timeout fail-closed và thông điệp tiếng Việt lịch sự, ghi log `ERROR` chuẩn cấu trúc.

---

## 2. Ràng buộc Tuân thủ (CONSTRAINTS.md)

- **Không đổi tên tool**: Giữ nguyên tên `search_enterprise_knowledge` và `get_system_manual`.
- **RBAC Server-Side**: Danh sách `allowed_systems` luôn được tính toán từ `current_sso_user` ở server.
- **Fail-Closed**: Timeout hoặc lỗi backend trả về thông báo an toàn, không ném exception unhandled lên UI người dùng.
- **Prompt Injection Defense**: Giữ nguyên toàn bộ chỉ thị phòng vệ `INDIRECT_PROMPT_INJECTION_DEFENSE_INSTRUCTION` và hàm bọc `wrap_retrieved_document()`.

---

## 3. Danh sách File Tạo và Chỉnh sửa

| File | Hành động | Mục đích |
|---|---|---|
| `it_helpdesk_agent/tools/enterprise_rag/rag_tools.py` | **Chỉnh sửa** | Hỗ trợ `RAG_TOP_K`, `RAG_SEARCH_TIMEOUT_SECONDS` timeout handling, graceful fallback. |
| `it_helpdesk_agent/tools/enterprise_rag/vertex_search_store.py` | **Chỉnh sửa** | `get_article_by_id` gom tất cả chunk theo `parent_doc_id` và `chunk_index`. |
| `it_helpdesk_agent/tools/enterprise_rag_mcp/knowledge_store.py` | **Chỉnh sửa** | `InMemoryKnowledgeStore.get_article_by_id` gom các chunk theo `parent_doc_id`. |
| `it_helpdesk_agent/app_utils/semantic_cache.py` | **Chỉnh sửa** | Thêm hash `allowed_systems` vào cache key; phân cấp TTL theo tier L1 vs L2. |
| `tests/unit/test_agent_architecture_v10.py` | **Chỉnh sửa / Tạo mới** | Unit tests cho kiến trúc Agent, tool reassembly, cache RBAC, timeout. |

---
