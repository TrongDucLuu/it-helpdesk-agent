# IT Helpdesk Multi-Agent AI System (Enterprise Production-Ready)

Hệ thống **IT Helpdesk Multi-Agent AI** thông minh, phân cấp 3 mức độ (3-Tier Support Architecture), tích hợp cơ chế bảo mật doanh nghiệp chuẩn **Zero-Trust Enterprise SSO (Google OIDC + Granular RBAC)**, tối ưu hóa chi phí và độ trễ với **Google Cloud Agent Search / Vertex AI Search** & **RBAC-Aware Semantic Cache Layer**, ứng dụng các công nghệ tiên tiến nhất của hệ sinh thái **Google AI (Google ADK, Gemini 2.5/3, Vertex AI Memory Bank, Google Cloud Firestore)** và sẵn sàng triển khai trên **Google Cloud Run**.

---

## 🌟 1. Phân Cấp Hỗ Trợ Kỹ Thuật (3-Tier Multi-Agent Architecture)

```
                                  ┌─────────────────────────────┐
                                  │   Người dùng / Nhân viên    │
                                  └──────────────┬──────────────┘
                                                 │ (Bearer Google OIDC Token)
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │ SSOAuthenticationMiddleware │
                                  │  (OIDC JWKS + Domain Filter)│
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  RBAC-Aware Semantic Cache  │ ──[ HIT (Sim >= 0.92, Hash Match) ]──► [ Trả lời tức thì ]
                                  │  (User & Tier Scoped Cache) │                                        (Tiết kiệm 100% Token)
                                  └──────────────┬──────────────┘
                                                 │ [ MISS ]
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  root_triage_orchestrator   │ ◄──► [ Vertex AI Memory Bank ]
                                  │      (Gemini 3 Flash)       │
                                  └──────────────┬──────────────┘
                 ┌───────────────────────────────┼──────────────────────────────┐
                 ▼                               ▼                              ▼
  ┌─────────────────────────────┐ ┌─────────────────────────────┐ ┌─────────────────────────────┐
  │    l1_selfservice_agent     │ │   l2_enterprise_rag_agent   │ │  l3_deep_diagnostics_agent  │
  │      (Gemini 3 Flash)       │ │      (Gemini 3 Flash)       │ │   (Gemini 2.5/3 Pro)        │
  └──────────────┬──────────────┘ └──────────────┬──────────────┘ └──────────────┬──────────────┘
          ┌──────┴──────┐                 ┌──────┴──────┐                 ┌──────┴──────┐
          ▼             ▼                 ▼             ▼                 ▼             ▼
    [Ticketing]   [Memory Tool]     [Enterprise   [Email Draft]     [Log Analyzer  [Compliance
     (Firestore)                     RAG Tools]    (In-Process)       RCA Tool]     SLA Tool]
                                  (Vertex AI Search/                 (RBAC Gate)   (RBAC Gate)
                                   BigQuery/InMemory)
```

### 🟢 Mức 1 — Giao Tiếp & Hỗ Trợ Cơ Bản (`l1_selfservice_agent`)
- **FAQ & Chính sách IT:** Giải đáp chính sách bảo mật, chuẩn độ phức tạp mật khẩu, hướng dẫn kết nối VPN, Wi-Fi doanh nghiệp, cài đặt máy in.
- **Quy trình Tự phục vụ (Self-Service):** Hướng dẫn chi tiết từng bước khi người dùng cần reset mật khẩu Active Directory, Google Workspace, Okta, hoặc tự mở khóa tài khoản.
- **Tiếp nhận & Phân loại sự cố:** Lắng nghe mô tả lỗi, tự động tạo ticket với category và mức độ ưu tiên chính xác (`Low`, `Medium`, `High`, `Critical`).

### 🔵 Mức 2 — Tra Cứu Tài Liệu (RAG) & Hệ Thống Doanh Nghiệp (`l2_enterprise_rag_agent`)
- **Enterprise In-Process FunctionTools:** Tích hợp trực tiếp các công cụ tra cứu tri thức nội bộ hệ thống **ERP** (SAP/Oracle PO & kế toán), **HRM** (Workday chấm công & onboarding), **CRM** (Salesforce lead sync & quota), loại bỏ hoàn toàn độ trễ giao tiếp ngoại trình IPC của MCP.
- **Backend Vertex AI Search (Agent Search):** Tìm kiếm lai ngữ nghĩa (Hybrid Semantic + Lexical Search), tự động nhúng vector (Managed Embeddings), xếp hạng lại kết quả (Semantic Reranking), và lọc phân quyền siêu nhanh bằng metadata pre-filtering.
- **Tái Hợp Nhất Đa Phân Mảnh (Multi-Chunk Reassembly):** Công cụ `get_system_manual` sử dụng `parent_doc_id` và `chunk_index` để ghép nối hoàn chỉnh các chương/mục của tài liệu quy trình dài, bảo đảm không bị mất bước kỹ thuật.
- **Kiến trúc Adapter Linh hoạt (`get_knowledge_store`):** Hỗ trợ chuyển đổi liền mạch giữa `vertex_ai_search` (Production Primary), `in_memory` (Local Dev & Unit Test offline), và `bigquery` (Conditional Legacy cho khách hàng có sẵn DWH).
- **Phòng Thủ Gián Điệp Prompt (Indirect Prompt Injection Defense):** Bọc tài liệu tri thức bằng `wrap_retrieved_document()`, escape XML attributes, kiểm soát số lượng thẻ và chỉ thị phân định nghiêm ngặt.
- **Soạn thảo Email & Cập nhật Ticket:** Soạn bản thảo email phản hồi chuẩn mực, lịch sự và tự động đồng bộ tiến độ ticket.

### 🟣 Mức 3 — Phân Tích & Suy Luận Chuyên Sâu (`l3_deep_diagnostics_agent`)
- **Mô hình năng lực cao:** Mặc định sử dụng **`gemini-2.5-pro` (GA - 99.9% Vertex AI SLA)** trên môi trường Production hoặc `gemini-3-pro-preview` trên Development/Staging chuyên trách suy luận logic và phân tích cấu trúc phức tạp.
- **Root Cause Analysis (RCA):** Phân tích log files, stack traces, phát hiện các mã lỗi trọng yếu (`OUT_OF_MEMORY`, `DB_CONNECTION_EXHAUSTED`, `NETWORK_TIMEOUT`, `AUTH_SECURITY_FAILURE`, `DISK_IO_FAILURE`, `DATA_CORRUPTION_NULL`) và lập báo cáo nguyên nhân gốc rễ cùng giải pháp khắc phục có kèm **Confidence Level** và **Disclaimer**.
- **Pháp lý IT & Rà soát SLA Hợp đồng:** Trích xuất cam kết Uptime, thời gian phản hồi MTTR 2 chiều (prefix/suffix), điều khoản bồi thường (Service Credits), quyền kiểm toán an toàn thông tin và thông báo sự cố bảo mật (DPA/NDA/GDPR) có đính kèm **Legal Disclaimer**.

---

## ⚡ 2. Tối Ưu Hóa Hiệu Năng & Chi Phí (RBAC-Aware Semantic Cache & Managed Search)

### A. Redis Vector Semantic Cache Có Nhận Thức Phân Quyền (`semantic_cache.py`)
- **Vấn đề giải quyết:** Các câu hỏi IT Helpdesk lặp lại thường xuyên (ví dụ: *"hướng dẫn đổi pass wifi"*, *"quy trình mở kỳ kế toán"*). Nếu mỗi câu hỏi đều gọi LLM sẽ tốn chi phí token và mất 1.5–3s phản hồi.
- **Bảo Vệ Đa Tầng RBAC Hash (`compute_rbac_hash`):**
  - Khắc phục lỗ hổng rò rỉ quyền khi vai trò người dùng thay đổi: Khóa cache private được gắn kèm `hashlib.sha256(sorted(allowed_systems))`. Nếu user bị thu hồi quyền truy cập ERP, toàn bộ cache entry cũ chứa tài liệu ERP lập tức bị vô hiệu hóa (Cache Invalidation by Scope).
  - **TTL Phân Tầng:** Tầng L1 (FAQ công khai) có TTL 3600s; Tầng L2 (RAG nghiệp vụ có phân quyền) có TTL 300s ngắn hơn để tôn trọng cập nhật tài liệu và thu hồi quyền; Tầng L3 (Chẩn đoán sự cố) tự động bypass cache (TTL = 0s).
- **Bộ lọc An toàn Public FAQ (`_is_safe_public_faq`):** Tự động chia sẻ cache công khai (`is_public=True`) cho các câu hỏi hướng dẫn chung (Wi-Fi, VPN, máy in) thuộc tầng L1 không gọi tool và không chứa PII.
- **Soft Fail-Closed & Circuit Breaker:** Tự động bypass cache và log `WARNING` khi Redis gặp sự cố mạng, bảo đảm luồng hội thoại không bị gián đoạn.

### B. Managed Search Engine: Vertex AI Search vs BigQuery Vector
- **Vertex AI Search (Agent Search):**
  - Fully Managed Search Engine hỗ trợ Hybrid Search (Dense Vector + BM25 Lexical + TF-IDF) và Google Semantic Ranker.
  - Tự động lập chỉ mục (Managed Indexing), lọc phân quyền qua Metadata Filter Expressions (`system: ANY("ERP", "HRM")`).
  - Không cần duy trì pipeline sinh embedding thủ công, không tốn tài nguyên bảo trì vector index định kỳ.
- **BigQuery Vector Search (Conditional Legacy):**
  - Giữ lại dưới dạng tùy chọn (`KNOWLEDGE_BACKEND=bigquery`) cho các khách hàng đã lưu trữ toàn bộ Data Warehouse trên BigQuery.

---

## 🔒 3. Kiến Trúc Bảo Mật Doanh Nghiệp (Enterprise Security & SSO)

Hệ thống được thiết kế theo tiêu chuẩn an toàn thông tin cấp doanh nghiệp, khắc phục hoàn toàn các lỗ hổng bảo mật phổ biến:

| Cơ chế bảo mật | Chi tiết kỹ thuật | Trạng thái bảo vệ |
| :--- | :--- | :--- |
| **Xác thực Google OIDC Chuẩn** | Sử dụng `google.oauth2.id_token.verify_oauth2_token` kiểm tra chữ ký số qua JWKS public certs của Google (`accounts.google.com`). | ✅ **Strict OIDC** |
| **JWT Single Verification Memoization** | Kết quả verify token được cache vào `request.state.verified_sso_user`, loại bỏ hoàn toàn việc giải mã chữ ký trùng lặp giữa các Middleware. | ✅ **Zero Overhead** |
| **Fail-Closed Domain Filtering** | Bắt buộc cấu hình `ALLOWED_DOMAINS` trên Production. Ngăn chặn triệt để tài khoản cá nhân `@gmail.com` truy cập hệ thống. | ✅ **Fail-Closed** |
| **Server-Side RBAC Enforcement** | Quyền `allowed_systems` được tính toán độc lập tại server từ `current_sso_user` và giao với gợi ý của LLM. LLM **tuyệt đối không thể tự cấp quyền**. | ✅ **Zero-Trust RBAC** |
| **Indirect Prompt Injection Defense** | Bọc dữ liệu bằng `wrap_retrieved_document`, escape XML delimiters, gắn cảnh báo `INDIRECT_PROMPT_INJECTION_DEFENSE_INSTRUCTION`. | ✅ **Defense-in-Depth** |
| **Pre-Query Security Trimming** | `build_system_filter()` tiền lọc an toàn trên Vertex AI Search; nếu user không có quyền, trả về sentinel `system = "__ZERO_ACCESS_SENTINEL__"`. | ✅ **Fail-Closed Filter** |
| **Governance Date & Tombstone Filter** | Tự động loại trừ tài liệu quá hạn (`expiry_date`), chưa có hiệu lực (`effective_date`), hoặc đã bị đánh dấu xoá (`is_deleted=True`). | ✅ **Content Governance** |
| **Latency Budget & Graceful Fallback** | Giới hạn thời gian truy vấn RAG tối đa 4.0s (`RAG_SEARCH_TIMEOUT_SECONDS`), tự động trả phản hồi tiếng Việt lịch sự khi timeout. | ✅ **Latency Guard** |

### Ma Trận Phân Quyền (RBAC Matrix)

| Vai trò (Role) | L1 Self-Service | L2 Enterprise RAG | L3 Log RCA Tool | L3 Contract SLA Tool |
| :--- | :---: | :---: | :---: | :---: |
| **`employee`** | ✅ Cho phép | ✅ Cho phép (Chỉ tài liệu public/HRM cơ bản) | ❌ Bị từ chối (`forbidden`) | ❌ Bị từ chối (`forbidden`) |
| **`erp_user` / `accountant`** | ✅ Cho phép | ✅ Cho phép (Tài liệu ERP) | ❌ Bị từ chối | ❌ Bị từ chối |
| **`hr_specialist` / `hr_manager`** | ✅ Cho phép | ✅ Cho phép (Tài liệu HRM) | ❌ Bị từ chối | ❌ Bị từ chối |
| **`sales_rep` / `crm_manager`** | ✅ Cho phép | ✅ Cho phép (Tài liệu CRM) | ❌ Bị từ chối | ❌ Bị từ chối |
| **`it_admin` / `sys_admin`** | ✅ Cho phép | ✅ Cho phép (Toàn bộ ERP/HRM/CRM) | ✅ Cho phép | ✅ Cho phép |
| **`compliance_officer` / `legal_counsel`** | ✅ Cho phép | ✅ Cho phép | ❌ Bị từ chối | ✅ Cho phép |
| **`devops_engineer` / `lead_engineer`** | ✅ Cho phép | ✅ Cho phép | ✅ Cho phép | ❌ Bị từ chối |

---

## 💾 4. Cơ Chế Lưu Trữ Dữ Liệu & Ingestion Pipeline

1. **Hệ thống Quản lý Ticket (`ticketing_tool.py`):**
   - Tích hợp **Google Cloud Firestore** (`collection: helpdesk_tickets`) hỗ trợ mở rộng không giới hạn khi triển khai trên multi-instance Cloud Run.
2. **Trí nhớ dài hạn (`agent.py`):**
   - Tích hợp **Vertex AI Memory Bank** (`VertexAiMemoryBankService`) tự động lưu vết ngữ cảnh người dùng, lịch sử thiết bị và sự cố lặp lại.
3. **Pipeline Nạp Tri Thức Tự Động (`scripts/ingest_knowledge_base.py`):**
   - Hỗ trợ đa định dạng: `.md`, `.txt`, `.docx`, `.pdf` (PyPDF hoặc Google Document AI Layout Parser), `.jsonl`.
   - Chuyển đổi và chuẩn hoá dữ liệu sang cấu trúc `structData` JSONL cho Discovery Engine.
   - Tải lên Cloud Storage (`gcs_uploader.py`) và thực hiện Import bất đồng bộ với chế độ `ReconciliationMode.FULL` (`vais_importer.py`), tự động xoá bỏ các tài liệu cũ không còn trong corpus.
   - Cơ chế **Dead Letter Queue (DLQ)** ghi nhận tài liệu lỗi khi parse.

---

## ⚙️ 5. Cấu Hình Biến Môi Trường (Environment Variables)

Sao chép file cấu hình mẫu:
```bash
cp .env.example .env
```

| Tên biến | Bắt buộc (Prod) | Mặc định | Ý nghĩa |
| :--- | :---: | :---: | :--- |
| `ENVIRONMENT` | Có | `development` | Môi trường: `development`, `staging`, `production`. |
| `GOOGLE_CLOUD_PROJECT` | Có | — | ID của dự án Google Cloud. |
| `GOOGLE_CLOUD_REGION` | Có | `asia-southeast1` | Vùng triển khai GCP (ví dụ: `asia-southeast1`, `us-central1`). |
| `SSO_CLIENT_ID` | Có | — | OAuth 2.0 Client ID được cấp từ GCP Console. |
| `ALLOWED_DOMAINS` | **Bắt buộc** | — | Danh sách domain email công ty được phép đăng nhập (ví dụ: `company.com,corp.com`). |
| `KNOWLEDGE_BACKEND` | Không | `vertex_ai_search` | Backend cho RAG (`vertex_ai_search`, `in_memory`, `bigquery`). |
| `VERTEX_SEARCH_DATA_STORE_ID` | Có (nếu VAIS) | `it-helpdesk-kb-datastore` | ID của Data Store trên Vertex AI Search / Agent Search. |
| `VERTEX_SEARCH_LOCATION` | Không | `global` | Location của Data Store (`global`, `asia-southeast1`, v.v.). |
| `GCS_CORPUS_BUCKET` | Có (nếu nạp) | — | Tên GCS Bucket chứa file JSONL corpus nạp tri thức. |
| `RAG_TOP_K` | Không | `8` | Số lượng tài liệu lấy về từ backend RAG (kẹp trong khoảng [1, 100]). |
| `RAG_SEARCH_TIMEOUT_SECONDS` | Không | `4.0` | Hạn mức thời gian tìm kiếm RAG trước khi kích hoạt fallback tiếng Việt. |
| `SEMANTIC_CACHE_BACKEND` | Không | `memory` | Backend cho Semantic Cache (`memory` hoặc `redis`). |
| `REDIS_HOST` / `REDIS_PORT` | Không | `localhost:6379` | Địa chỉ kết nối Redis / Google Cloud Memorystore. |
| `L3_RATE_LIMIT_PER_MINUTE` | Không | `10` | Hạn mức gọi chẩn đoán sâu L3 cho mỗi user/phút (cảnh báo tại 80%). |

---

## 🚀 6. Hướng Dẫn Cài Đặt & Chạy Cục Bộ (Local Development)

### Bước 1: Cài đặt Dependencies với `uv`
```bash
uv sync
```

### Bước 2: Chạy Toàn Bộ Kiểm Thử Tự Động (Unit & Integration Tests)
```bash
uv run pytest tests/ -v
```
*(Hiện tại toàn bộ **274/274 test cases** thuộc Epics 0 đến 5 đều vượt qua 100%)*

### Bước 3: Nạp Tri Thức Thử Nghiệm (Ingestion Dry-Run & Live)
```bash
# Chạy dry-run kiểm tra định dạng JSONL và bộ lọc hệ thống
python scripts/ingest_knowledge_base.py \
    --backend vertex_ai_search \
    --source-dir data/knowledge_base/ \
    --dry-run

# Chạy nạp thật lên Cloud Storage và Vertex AI Search
python scripts/ingest_knowledge_base.py \
    --backend vertex_ai_search \
    --project-id="YOUR_PROJECT_ID" \
    --gcs-bucket="YOUR_CORPUS_BUCKET" \
    --data-store-id="it-helpdesk-kb-datastore" \
    --source-dir data/knowledge_base/
```

### Bước 4: Chạy Đánh Giá Chất Lượng & Benchmark (Eval Harness)
```bash
# Chạy đánh giá trên InMemory store (nhanh, offline)
python scripts/eval_harness.py --store in_memory

# Chạy đánh giá trên Vertex AI Search thật
python scripts/eval_harness.py --store vertex_ai_search
```

### Bước 5: Khởi Chạy Web Server (FastAPI + ADK Web UI)
```bash
uv run python main.py --mode serve --port 8080
```
- Giao diện Web: `http://localhost:8080`
- OpenAPI Swagger Docs: `http://localhost:8080/docs` (Tự động vô hiệu hóa trên Production để bảo mật)
- Healthcheck Endpoint: `http://localhost:8080/healthz`
- Semantic Cache Stats: `http://localhost:8080/api/cache/stats`
- Telemetry Analytics: `http://localhost:8080/api/telemetry/summary`

---

## ☁️ 7. Triển Khai Lên Google Cloud (Terraform & Cloud Run)

### Khởi Tạo Hạ Tầng Tự Động (Terraform)
Thư mục `deployment/terraform` bao gồm:
- Module `vertex_ai_search.tf`: Bật `discoveryengine.googleapis.com`, tạo GCS Corpus Bucket có versioning & UBLA, Data Store với `acl_enabled = false` (bất biến), Search Engine, và cấp quyền tối thiểu `roles/discoveryengine.viewer`.
- Validation biến `region` bắt buộc (không default), kiểm soát Data Residency tuân thủ Nghị định 13/2023/NĐ-CP.
- Cloud Audit Logging cho dữ liệu tìm kiếm tri thức.

```bash
cd deployment/terraform
terraform init
terraform plan \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="region=asia-southeast1" \
  -var="sso_client_id=YOUR_OAUTH_CLIENT_ID.apps.googleusercontent.com" \
  -var="allowed_domains=company.com"

terraform apply -auto-approve \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="region=asia-southeast1" \
  -var="sso_client_id=YOUR_OAUTH_CLIENT_ID.apps.googleusercontent.com" \
  -var="allowed_domains=company.com"
cd ../..
```

---

## 📂 8. Cấu Trúc Mã Nguồn (Project Structure)

```
it-helpdesk-agent/
├── .env.example                     # File mẫu biến môi trường
├── Dockerfile                       # Container definition chuẩn production
├── Makefile                         # Lệnh tiện ích cho build, test, deploy
├── README.md                        # Tài liệu hướng dẫn toàn diện
├── CONSTRAINTS.md                   # Ràng buộc kiến trúc & Invariants tuyệt đối
├── pyproject.toml                   # Định nghĩa dependencies và project metadata
├── main.py                          # Entrypoint khởi chạy CLI hoặc FastAPI server
├── config/                          # Cấu hình hệ thống, RBAC & chunking đa tầng
│   └── systems.yaml                 # Định nghĩa ERP/HRM/CRM, role mappings & domain keywords
├── docs/                            # Tài liệu kiến trúc, ADRs và Specs
│   ├── adr/                         # Architecture Decision Records (0001 -> 0004)
│   └── specs/                       # Đặc tả kỹ thuật các Epics (0 -> 6)
├── scripts/
│   ├── eval_harness.py              # Eval benchmark đa backend (Precision@k, Recall@k, MRR)
│   ├── ingest_knowledge_base.py     # Unified CLI Ingest nạp tri thức lên VAIS/BQ
│   ├── ingest/                      # Package module hóa xử lý dữ liệu nạp
│   │   ├── parsers.py               # DocumentParser (MD, TXT, DOCX, DocAI PDF, JSONL)
│   │   ├── chunkers.py              # Tiered & semantic chunking strategies
│   │   ├── jsonl_builder.py         # JSONL builder chuẩn hóa structData cho Discovery Engine
│   │   ├── gcs_uploader.py          # Upload corpus lên GCS
│   │   ├── vais_importer.py         # Import Documents bất đồng bộ (FULL reconciliation)
│   │   └── loaders.py               # BigQuery Table schema & DLQ error handler
│   └── load_test/                   # Bộ kiểm thử tải và mô phỏng CCU (Locust)
├── deployment/
│   └── terraform/                   # Infrastructure-as-Code cho GCP
│       ├── main.tf                  # Cloud Run, IAM, Secrets & Check blocks
│       ├── vertex_ai_search.tf      # Discovery Engine Data Store, Engine & GCS Bucket
│       └── variables.tf             # Biến cấu hình Terraform (Region validation bắt buộc)
├── it_helpdesk_agent/
│   ├── agent.py                     # Multi-Agent 3 cấp bậc (L1, L2, L3) + In-Process Tools
│   ├── fast_api_app.py              # Ứng dụng FastAPI, Middleware và Cache endpoints
│   ├── app_utils/
│   │   ├── env.py                   # Quản lý nạp biến môi trường & Secret Manager
│   │   ├── rate_limiter.py          # Token-hash & IP Sliding Window Limiter + Soft Warning
│   │   ├── semantic_cache.py        # RBAC-Aware Redis & InMemory Vector Semantic Cache
│   │   ├── sso_auth.py              # Xác thực OIDC JWKS, Role Resolution, RBAC ContextVar
│   │   ├── system_config.py         # Dynamic loader cho systems.yaml & Domain Keywords
│   │   └── telemetry.py             # OpenTelemetry tracking, Fail-Closed Privacy & PII redaction
│   └── tools/
│       ├── compliance_tool.py       # Công cụ phân tích SLA & hợp đồng IT (RBAC + Disclaimer)
│       ├── log_analyzer.py          # Công cụ phân tích log RCA (RBAC + Confidence Level)
│       ├── ticketing_tool.py        # Quản lý Ticket (Firestore limit + bounded LRU cache)
│       ├── enterprise_rag/          # Bộ công cụ RAG In-Process
│       │   ├── rag_tools.py         # search_enterprise_knowledge, get_system_manual, draft_email
│       │   ├── filter_builder.py    # build_system_filter chống injection với whitelist
│       │   └── vertex_search_store.py # VertexAiSearchKnowledgeStore adapter
│       └── enterprise_rag_mcp/      # RAG Data Models & Core Stores
│           ├── knowledge_store.py   # BaseKnowledgeStore, InMemory & BigQuery Stores
│           └── rag_models.py        # Schemas dữ liệu RAG (KnowledgeArticle, SearchResult)
└── tests/
    ├── integration/                 # Kiểm thử tích hợp RBAC end-to-end
    │   └── test_rbac_end_to_end.py
    └── unit/                        # Bộ kiểm thử đơn vị tự động (274 test cases)
        ├── test_epic5_agent_layer.py
        ├── test_filter_builder_fuzz.py
        ├── test_ingest_cli.py
        ├── test_jsonl_builder.py
        ├── test_knowledge_store_factory.py
        ├── test_schema_parity.py
        ├── test_terraform_hcl_syntax.py
        ├── test_vais_importer.py
        ├── test_vertex_search_store.py
        └── ...
```
