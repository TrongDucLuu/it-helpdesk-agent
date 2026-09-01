# ADR 0002: RBAC Enforcement Mechanism — Metadata Filter vs. Document-Level ACL

- **Status**: Accepted
- **Date**: 2026-09-01
- **Deciders**: Solution Architect Đức (Gimasys), Security Lead, Antigravity
- **Source Documents**:
  - Vertex AI Search Document-Level Access Control: https://cloud.google.com/generative-ai-app-builder/docs/document-level-access
  - Metadata Filtering Syntax: https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
  - Data Store Configuration & ACL Settings: https://cloud.google.com/generative-ai-app-builder/docs/create-data-store-es

---

## 1. Context & Problem Statement
Hệ thống IT Helpdesk phục vụ nhiều đối tượng người dùng với quyền hạn khác nhau đối với các hệ thống nội bộ (`HRM`, `ERP`, `CRM`, `IT_PORTAL`).
Yêu cầu an ninh tối thượng: **Người dùng không có quyền trên hệ thống nào thì tuyệt đối không được đọc hoặc thấy kết quả tìm kiếm từ hệ thống đó (RBAC Isolation & Fail-Closed).**

Trong Google Discovery Engine / Vertex AI Search (Agent Search), có 2 cơ chế phân quyền tài liệu:
1. **Option A (Application-Level Metadata Filter + Service Account)**: Data Store không bật ACL (`acl_enabled = false`). Ứng dụng trung gian (Agent Service) xác thực người dùng qua SSO token, trích xuất danh sách `allowed_systems` hợp lệ của người dùng đó, và tự động chèn mệnh đề `filter` vào `SearchRequest` (ví dụ: `system: ANY("HRM", "ERP")`) khi gọi Search API bằng Service Account của backend.
2. **Option B (Document-Level ACLs + End-User Credential / Identity Mapping)**: Data Store bật ACL (`acl_enabled = true` tại thời điểm tạo). Từng document được gán danh sách `read_access` (users, groups, IAM principles). Khi tìm kiếm, danh tính người dùng cuối (hoặc end-user OAuth token / Workforce Identity) được truyền trực tiếp để Discovery Engine tự lọc.

Ràng buộc chí mạng: **Cờ `acl_enabled` là BẤT BIẾN (IMMUTABLE)**. Không thể bật/tắt sau khi Data Store đã tạo.

---

## 2. Decision Matrix & Detailed Comparison

| Tiêu Chí | Option A: Metadata Filter | Option B: Document-Level ACL |
|---|---|---|
| **Cấu hình Data Store** | `acl_enabled = false` | `acl_enabled = true` (Bắt buộc lúc tạo) |
| **Cơ chế xác thực** | Backend Service Account gọi Search API | End-user OAuth / Principal Access Tokens |
| **Điểm thực thi RBAC** | Backend Application Server (`rag_tools.py`) | Managed Google Discovery Engine Kernel |
| **Độ phức tạp tích hợp** | Thấp. Đồng bộ trực tiếp với hệ thống SSO / IAM hiện tại (`current_sso_user`) | Rất cao. Phải đồng bộ Group/User Directory vào Google Cloud Identity / Workspace |
| **Độ trễ (Latency)** | Nhanh hơn (không qua bước phân giải nhóm người dùng động trên GCP) | Thêm độ trễ giải mã token và kiểm tra ACL phân tán |
| **Khả năng kiểm thử offline** | Rất cao (Mock / `InMemoryKnowledgeStore` giả lập chính xác logic filter) | Khó kiểm thử offline (đòi hỏi Identity Federation thật) |
| **Phạm vi phân quyền** | Phù hợp cấp độ Hệ thống / Nhóm tài liệu (`system`, `department`, `doc_type`) | Phù hợp cấp độ Từng file / Từng người dùng cụ thể (Per-document granular ACL) |

---

## 3. Threat Model Analysis

### 3.1. Option A: Metadata Filter
- **Mối đe dọa 1: Prompt Injection từ người dùng / LLM tự nâng quyền**:
  - *Rủi ro*: LLM cố tình điền `system: ANY("ALL")` hoặc người dùng gửi prompt giả mạo quyền.
  - *Biện pháp giảm thiểu*: **Inject bằng code phía server**. Hàm `search_enterprise_knowledge` chỉ nhận `query` và gợi ý `system`. Backend server lấy danh sách quyền thực từ `current_sso_user` (ContextVar), tính toán `final_systems = user_allowed_systems & requested_systems`, và tự sinh chuỗi `filter`. LLM không có tham số nào để can thiệp vào `allowed_systems`.
- **Mối đe dọa 2: Lỗi Service Account Leakage**:
  - *Rủi ro*: Service Account có quyền đọc toàn bộ Data Store. Nếu backend server bị compromise, kẻ tấn công có thể query toàn bộ.
  - *Biện pháp giảm thiểu*: Gán role IAM tối thiểu `roles/discoveryengine.viewer` cho Service Account của Cloud Run; bảo vệ backend bằng WAF và mTLS.

### 3.2. Option B: Document-Level ACL
- **Mối đe dọa 1: Đồng bộ ACL bị lệch pha (Stale ACL Sync)**:
  - *Rủi ro*: Nhân viên chuyển phòng ban nhưng ACL trên Discovery Engine chưa cập nhật kịp thời -> rò rỉ dữ liệu nhạy cảm.
- **Mối đe dọa 2: Quá tải quota Directory Sync API**:
  - *Rủi ro*: Đồng bộ danh bạ hàng ngàn người dùng liên tục gây nghẽn API.

---

## 4. Customer Classification Matrix (Khi Nào Dùng Gì?)

```
+-------------------------------------------------------------+
| Nhu Cầu Phân Quyền                                          |
|                                                             |
| [Cấp Hệ Thống / Module] --------> CHỌN OPTION A             |
| (HRM, ERP, CRM, Internal Guides)   (Metadata Filter)        |
|                                    - Đơn giản, linh hoạt    |
|                                    - Zero identity sync lag |
|                                    - Tối ưu cho AI Agent    |
|                                                             |
| [Cấp Từng File / Phòng Ban Nhỏ] -> CHỌN OPTION B            |
| (Google Drive, SharePoint sync,    (Document-Level ACL)     |
|  File cá nhân, Bảng lương riêng)   - acl_enabled = true     |
|                                    - Yêu cầu Cloud Identity |
+-------------------------------------------------------------+
```

1. **Khách hàng Tier 1 (Doanh nghiệp vừa và nhỏ, Standard Enterprise)**:
   - Toàn bộ tài liệu quy trình nội bộ thuộc về các phân hệ (`HRM`, `ERP`, `CRM`, `IT`).
   - Phân quyền theo vai trò người dùng (Role-Based Access Control).
   - **Khuyến nghị**: **Option A**.
2. **Khách hàng Tier 2 (Tập đoàn lớn, Multi-tenant phức tạp)**:
   - Dữ liệu kết nối trực tiếp từ Google Drive / Microsoft 365 với hàng triệu file có ACL riêng biệt từng file.
   - **Khuyến nghị**: **Option B** (tạo Data Store riêng với `acl_enabled = true`).

---

## 5. Decision Outcome

1. **Giai đoạn Hiện tại (Migration)**: Lựa chọn **Option A (Metadata Filter + Backend Code Injection)** làm chiến lược mặc định:
   - Tạo Data Store với `acl_enabled = false`.
   - Thực thi RBAC 100% tại backend `rag_tools.py` dựa trên `current_sso_user`.
   - Áp dụng nguyên tắc **Fail-Closed**: nếu không có SSO context hoặc user không có role, trả về 0 kết quả ngay lập tức trước khi gọi Search API.
2. **Kiến trúc Mở rộng (Multi-Tenant / Future Proof)**:
   - Module Terraform cung cấp biến `acl_enabled = false` (default) nhưng cho phép cấu hình `true` khi khách hàng yêu cầu Document-Level ACL riêng biệt.
