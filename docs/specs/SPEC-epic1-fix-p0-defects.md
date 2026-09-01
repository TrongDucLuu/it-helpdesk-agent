# Spec: Epic 1 — Sửa Các Lỗi P0 Kiến Trúc & Báo Cáo Hiệu Năng

## 1. Objective
Giải quyết dứt điểm 3 lỗi P0 độc lập với migration để bảo đảm tính toàn vẹn của hệ thống:
- **VAIS-010**: Chuyển RAG Tools (`search_enterprise_knowledge`, `get_system_manual`) từ FastMCP stdio subprocess sang ADK `FunctionTool` in-process tại `it_helpdesk_agent/tools/enterprise_rag/rag_tools.py`, khắc phục triệt để lỗi mất `contextvars.ContextVar` (`current_sso_user`) qua ranh giới tiến trình làm hỏng phân quyền RBAC trên Cloud Run.
- **VAIS-011**: Xoá hoàn toàn 14 vị trí kiểm tra `hasattr(x, "_mock_return_value")` trong mã production (`it_helpdesk_agent/`), thay thế bằng Dependency Injection và ép kiểu tường minh ở biên.
- **VAIS-012**: Sửa file `SCALABILITY_PERFORMANCE_REPORT.md`: Đổi tiêu đề thành "Capacity Model (mô hình tính toán)", ghi rõ toàn bộ giả định đầu vào (RPM/TPM quota Gemini, token/turn, cache hit rate giả định), tách biệt rõ ràng phần tính toán lý thuyết và để trống mục "Số liệu đo thật" chờ đo lường thực tế tại VAIS-062.

## 2. Tech Stack & Commands
- **ADK In-Process Tools**: ADK `FunctionTool` hoặc Python callable in-process nhận ngữ cảnh trực tiếp từ `current_sso_user`.
- **Test Framework**: `pytest`, `pytest-asyncio`.
- **Commands**:
  - Run Unit Tests: `.venv/bin/pytest tests/unit/ -v`
  - Run Integration Tests (RBAC Cloud Run simulation): `.venv/bin/pytest tests/integration/test_rbac_end_to_end.py -v`
  - Check Clean Code (0 mock branches): `grep -rn "_mock_return_value" it_helpdesk_agent/`

## 3. Project Structure
```
it_helpdesk_agent/
├── agent.py                                (Xoá rag_mcp subprocess, import in-process tools)
├── tools/
│   ├── enterprise_rag/
│   │   ├── __init__.py
│   │   └── rag_tools.py                    (In-process FunctionTools)
│   └── enterprise_rag_mcp/
│       └── main.py                         (Giữ entrypoint MCP tuỳ chọn kèm docstring cảnh báo)
tests/
├── integration/
│   └── test_rbac_end_to_end.py             (Test RBAC in-process với K_SERVICE=1)
└── unit/
    └── test_agent_architecture_v10.py
SCALABILITY_PERFORMANCE_REPORT.md           (Cập nhật thành Capacity Model)
```

## 4. Code Style & Boundary Rules
- **Pure In-Process Execution**: `rag_tools.py` đọc `current_sso_user` trực tiếp trong thread/async task hiện tại.
- **Dependency Injection**: Các store/client được truyền qua tham số hàm hoặc cấu hình khởi tạo, không kiểm tra type hay thuộc tính private `_mock_return_value`.
- **RBAC Server-side Enforcement**: Hàm tool chỉ nhận `query: str` và `system: Optional[str] = None`. Quyền truy cập hệ thống `allowed_systems` được tự động tính toán từ `current_sso_user` và giao với `system` của người dùng; LLM không có quyền tự cấp `allowed_systems`.

## 5. Testing & Acceptance Criteria
- [ ] **VAIS-010**:
  - Viết file test `tests/integration/test_rbac_end_to_end.py`.
  - Giả lập `K_SERVICE=1` và user role `erp_user` -> chỉ truy xuất được tài liệu `ERP`.
  - Giả lập user role `hr_manager` -> chỉ truy xuất được tài liệu `HRM`.
  - Giả lập user không có role -> trả về `[]`, không ngoại lệ, không leak dữ liệu.
  - Giả lập `current_sso_user = None` và `ALLOW_LOCAL_DEV_SSO=False` -> trả về `[]` hoặc báo lỗi không xác thực, tuyệt đối không trả document.
  - Test bắt buộc chạy cùng process với tool.
- [ ] **VAIS-011**:
  - Lệnh `grep -rn "_mock_return_value" it_helpdesk_agent/ | wc -l` trả về đúng `0`.
  - Toàn bộ 200 unit tests hiện tại vẫn pass 100%.
- [ ] **VAIS-012**:
  - `SCALABILITY_PERFORMANCE_REPORT.md` không còn chứa từ "Empirical" hay "Benchmark" gắn với các số liệu chưa được đo trên môi trường thực.
  - Có mục "Số liệu đo thật" ghi `CHƯA ĐO` chờ VAIS-062.
