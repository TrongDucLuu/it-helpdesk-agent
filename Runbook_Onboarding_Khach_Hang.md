# Runbook: Onboarding Khách Hàng & Vận Hành Ingestion Pipeline

> **Dành cho:** Solutions Architects, DevOps Engineers, và System Administrators  
> **Hệ thống:** IT Helpdesk Multi-Agent AI System (`it-helpdesk-agent`)  
> **Phiên bản tài liệu:** 3.0 (Vertex AI Search & Zero-Trust In-Process Architecture)

---

## 1. Tổng Quan Kiến Trúc Onboarding

Hệ thống `it-helpdesk-agent` được thiết kế theo kiến trúc **Config-Driven**. Khi triển khai cho một khách hàng doanh nghiệp mới (hoặc mở rộng thêm hệ thống nghiệp vụ như MES, HIS, Core Banking, WMS...), toàn bộ cấu hình hệ thống, vai trò RBAC, chiến lược chunking và xử lý tài liệu được khai báo tập trung tại [`config/systems.yaml`](file:///Users/luuduc/.gemini/antigravity/scratch/it-helpdesk-agent/config/systems.yaml) mà **không cần sửa hay biên dịch lại bất kỳ dòng mã nguồn nào**.

```
                           +------------------------------------+
                           |        config/systems.yaml         |
                           +------------------------------------+
                                      |              |
                +---------------------+              +---------------------+
                |                                                          |
                v                                                          v
   [Đường Đọc: Runtime Agent]                               [Đường Ghi: Ingestion Pipeline]
   - Security-Trimming (IDOR/RBAC)                          - Structured Document Parser
   - Pre-Query Filter Builder                               - Tiered Chunking Strategy
   - In-Process RAG Tools                                   - structData JSONL + FULL Reconciliation
```

---

## 2. Quy Trình Onboarding Khách Hàng Mới (Step-by-Step)

### Bước 0: Khảo Sát & Xác Định Vùng Lưu Trữ Dữ Liệu (Data Residency & Compliance) [BẮT BUỘC]

Trước khi khởi tạo hạ tầng Terraform hoặc đưa dữ liệu tri thức doanh nghiệp vào hệ thống, Solutions Architect và DevOps Engineer **bắt buộc** phải khảo sát và chốt các tiêu chí Data Residency & Governance:

1. **Tuân thủ Pháp lý & Quy định Dữ liệu (Compliance & Localization)**:
   - Doanh nghiệp Việt Nam chịu sự điều chỉnh của **Nghị định 13/2023/NĐ-CP** (Bảo vệ Dữ liệu Cá nhân), Thông tư 09/2020/TT-NHNN (Ngân hàng Nhà nước), và các quy định an toàn thông tin Y tế / Quốc phòng.
   - **Lựa chọn Region trong Terraform (`var.region`)**:
     - Doanh nghiệp Việt Nam / Đông Nam Á: Chọn `asia-southeast1` (Singapore - độ trễ thấp nhất ~30-40ms, lưu trữ dữ liệu tại APAC).
     - Doanh nghiệp Bắc Mỹ: Chọn `us-central1` hoặc `us-east1`.
     - Doanh nghiệp Châu Âu (GDPR): Chọn `europe-west1` (Bỉ) hoặc `europe-west4` (Hà Lan).
   - **Ràng buộc Terraform**: Biến `region` **không có giá trị mặc định**. Quá trình provisioning sẽ fail-closed nếu không chỉ định rõ vùng triển khai.

2. **Quyết định Chiến lược Phân quyền Knowledge Base (`acl_enabled`)**:
   - **CẢNH BÁO IMMUTABLE**: Thuộc tính `acl_enabled` trên Discovery Engine Data Store **không thể thay đổi sau khi tạo**. Nếu muốn đổi giữa Option A (Metadata Filter) và Option B (Document-Level ACLs), bắt buộc phải huỷ toàn bộ Data Store và nạp lại toàn bộ Corpus.
   - Hầu hết khách hàng Enterprise sử dụng **Option A (`acl_enabled = false`)** kết hợp với hệ thống lọc bảo mật động tại server (`build_system_filter`).

---

### Bước 1: Khai báo Danh mục Hệ thống & Phân quyền RBAC

Chỉnh sửa tệp `config/systems.yaml` để định nghĩa các hệ thống mục tiêu của khách hàng:

```yaml
# Các vai trò quản trị viên có quyền truy cập toàn bộ các hệ thống
shared_admin_roles:
  - "it_admin"
  - "support_agent"
  - "sysadmin"

# Ánh xạ vai trò thực tế cho người dùng SSO (Google OIDC / Enterprise Email)
# Thứ tự ưu tiên: 1. YAML mapping -> 2. Firestore 'user_roles' -> 3. Token claim -> 4. Base 'employee'
user_role_mappings:
  "admin@company.com": ["it_admin", "sysadmin"]
  "lead_accountant@company.com": ["accountant", "erp_user"]
  "procurement_lead@company.com": ["procurement_lead", "erp_user"]
  "hr_director@company.com": ["hr_manager", "hr_specialist"]

# Từ khóa đặc thù nhận diện hệ thống phục vụ phân tích Telemetry và Routing (Word Boundary \b)
domain_keywords:
  ERP:
    - "sap"
    - "oracle"
    - "po"
    - "purchase order"
    - "me21n"
    - "me29n"
    - "hóa đơn"
    - "mua sắm"
    - "kế toán"
  HRM:
    - "workday"
    - "nghỉ phép"
    - "bảo hiểm"
    - "chấm công"
    - "lương"
    - "onboarding"
    - "hợp đồng lao động"
  CRM:
    - "salesforce"
    - "lead"
    - "khách hàng"
    - "quota"
    - "deal"
    - "pipeline"

# Danh mục hệ thống nghiệp vụ của khách hàng
systems:
  ERP:
    display_name: "Enterprise Resource Planning (SAP S/4HANA)"
    vendor_examples: "SAP / Oracle NetSuite"
    description: "Hệ thống quản lý tài chính, kế toán, chuỗi cung ứng và mua sắm vật tư"
    common_issues:
      - "Lỗi khóa tài khoản người dùng do nhập sai mật khẩu 3 lần"
      - "Lỗi hạch toán hóa đơn và kỳ kế toán bị đóng (FI-GL)"
      - "Lỗi duyệt đơn mua hàng PO qua giao dịch ME29N"
    roles:
      - "erp_user"
      - "accountant"
      - "procurement_lead"

  HRM:
    display_name: "Human Resource Management (Workday)"
    vendor_examples: "Workday / BambooHR"
    description: "Hệ thống quản trị nhân sự, chấm công, nghỉ phép và bảo hiểm y tế"
    common_issues:
      - "Lỗi đồng bộ dữ liệu chấm công vân tay vào kỳ lương"
      - "Quy trình phê duyệt nghỉ thai sản / nghỉ phép năm"
    roles:
      - "employee"
      - "hr_specialist"
      - "hr_manager"

  MES:
    display_name: "Manufacturing Execution System"
    vendor_examples: "Siemens Opcenter / Rockwell FactoryTalk"
    description: "Hệ thống điều hành và giám sát dây chuyền sản xuất nhà máy"
    common_issues:
      - "Lỗi mất kết nối OPC-UA tới thiết bị PLC trạm dập"
      - "Lỗi đồng bộ lệnh sản xuất (Work Order) từ ERP xuống chuyền"
    roles:
      - "factory_operator"
      - "plant_engineer"
      - "production_supervisor"
```

> [!IMPORTANT]
> **Quy tắc Phân quyền & Định danh:**
> 1. **Cấp Role thật:** Google ID Token mặc định không chứa claim `roles`. Quản trị viên khai báo danh sách email nhân sự đặc quyền trong `user_role_mappings` hoặc kích hoạt đồng bộ qua Firestore collection `user_roles` (`USE_FIRESTORE_ROLES=true`). Mọi người dùng không nằm trong danh sách đặc quyền đều tự động nhận role cơ bản `employee`.
> 2. **Quy tắc đặt tên hệ thống:** Tên hệ thống (key) chỉ bao gồm chữ cái in hoa và số (`[A-Z0-9]+`), độ dài tối đa 20 ký tự. Từ khóa `ALL` là từ khóa dành riêng cho Security Trimming, nghiêm cấm đặt tên hệ thống là `ALL`.

---

### Bước 2: Cấu hình Chiến Lược Chunking & Document Processing

Tại cùng tệp `config/systems.yaml`, cấu hình pipeline chunking phù hợp với đặc thù dữ liệu tài liệu của khách hàng:

```yaml
# Cấu hình chiến lược phân mảnh tri thức (Chunking Pipeline)
chunking:
  default_strategy: "auto"        # "auto" | "fixed" | "semantic"
  max_chunk_size: 1200            # Độ dài chunk tối đa (ký tự)
  overlap: 150                    # Độ dài gối đầu giữa các chunk
  well_structured_max_section_ratio: 0.65  # Ngưỡng tỷ lệ tối đa của 1 section (65%)
  well_structured_min_avg_section_length: 100 # Độ dài trung bình tối thiểu của section

  # Cho phép ghi đè cấu hình theo từng hệ thống nghiệp vụ đặc thù
  systems:
    HRM:
      strategy: "semantic"        # HRM sử dụng cờ semantic chunking
    MES:
      max_chunk_size: 800         # Sổ tay bảo trì MES chia nhỏ 800 ký tự
      overlap: 100

# Cấu hình bộ trích xuất định dạng tài liệu (Document Processing)
document_processing:
  pdf_parser: "pypdf_flat"        # "pypdf_flat" | "document_ai"
  document_ai_processor_id: ""    # Bắt buộc nếu dùng document_ai (projects/.../processors/...)
  document_ai_timeout_seconds: 60
  document_ai_max_retries: 2
```

#### Hướng dẫn chọn PDF Parser:
1. **`pypdf_flat` (Mặc định - Chi phí $0):**
   - Phù hợp với tài liệu PDF dạng văn bản một cột phẳng, tài liệu nội bộ xuất từ Word.
2. **`document_ai` (Google Cloud Document AI Layout Parser - $10 / 1.000 trang):**
   - Khuyên dùng cho khách hàng có tài liệu kỹ thuật phức tạp: định dạng nhiều cột (multi-column), bảng biểu phức tạp, heading phân cấp sâu.
   - Bắt buộc khai báo `document_ai_processor_id`. Hệ thống sẽ **Fail-Closed** nếu cấu hình thiếu ID hoặc API lỗi vượt quá số lần retry.

---

### Bước 3: Cấu hình Retrieval & Knowledge Backend
Trong `config/systems.yaml`, cấu hình tham số tìm kiếm và mở rộng tính năng:
```yaml
retrieval:
  top_k: 8                          # Số lượng tài liệu lấy về tối đa (kẹp trong [1, 100])
  timeout_seconds: 4.0              # Hạn mức thời gian RAG (fallback tiếng Việt khi timeout)
  hybrid_search_enabled: true       # Bật Hybrid Search (Dense + Lexical + Semantic Reranker)
```

---

### Bước 4: Chuẩn Bị & Nạp Dữ Liệu (Modular Ingestion Pipeline)

Toàn bộ pipeline nạp dữ liệu được cấu trúc dạng package mở rộng [`scripts/ingest/`](file:///Users/luuduc/.gemini/antigravity/scratch/it-helpdesk-agent/scripts/ingest/):
- **`parsers.py`**: Xử lý đa định dạng (`.md`, `.txt`, `.docx`, `.pdf` qua PyPDF hoặc Document AI Layout, `.jsonl`).
- **`chunkers.py`**: Phân chia đoạn tri thức đa chiến lược (Fixed, Semantic, Tiered Section-Aware).
- **`jsonl_builder.py`**: Chuẩn hóa corpus thành file JSON Lines `structData` cho Discovery Engine.
- **`gcs_uploader.py`**: Upload file JSONL lên Cloud Storage Corpus Bucket.
- **`vais_importer.py`**: Gọi API Discovery Engine nạp tài liệu với `ReconciliationMode.FULL`.
- **`loaders.py`**: Quản lý Staging BigQuery & Dead Letter Queue (DLQ).
- **`scripts/ingest_knowledge_base.py`**: Giao diện dòng lệnh CLI Driver hợp nhất (`--backend {vertex_ai_search, bigquery, in_memory}`).

Tập hợp tài liệu tri thức của khách hàng theo định dạng hỗ trợ và chạy lệnh nạp:

```bash
# 1. Chạy Dry-Run kiểm tra định dạng và cấu trúc JSONL (Không tốn chi phí GCP)
python scripts/ingest_knowledge_base.py \
    --backend vertex_ai_search \
    --source-dir="data/knowledge_base/" \
    --default-system="ERP" \
    --dry-run

# 2. Nạp chính thức vào Vertex AI Search (Agent Search Data Store)
python scripts/ingest_knowledge_base.py \
    --backend vertex_ai_search \
    --project-id="your-gcp-project-id" \
    --gcs-bucket="your-corpus-bucket-name" \
    --data-store-id="it-helpdesk-kb-datastore" \
    --source-dir="/path/to/customer/docs" \
    --default-system="ERP"

# 3. (Tùy chọn Legacy) Nạp vào BigQuery nếu khách hàng dùng Data Warehouse
python scripts/ingest_knowledge_base.py \
    --backend bigquery \
    --project-id="your-gcp-project-id" \
    --dataset-id="it_helpdesk_kb" \
    --table-name="knowledge_articles" \
    --source-dir="/path/to/customer/docs" \
    --default-system="ERP"
```

Quá trình nạp tự động:
1. Trích xuất văn bản và phân cấp cây tài liệu (`section_hierarchy` gồm `h1, h2, h3`).
2. Gán metadata phân quyền, ngày hiệu lực (`effective_date`), ngày hết hạn (`expiry_date`), và `parent_doc_id` / `chunk_index`.
3. Chuẩn hóa sang `structData` JSONL và nạp bất đồng bộ lên Discovery Engine.
4. Discovery Engine tự động thực hiện nhúng vector và tạo chỉ mục Hybrid Search & Semantic Ranker.

---

## 3. Cập Nhật Chiến Lược Chunking & Đồng Bộ Corpus

Khi một khách hàng đang hoạt động yêu cầu đổi chiến lược chunking (ví dụ: từ `fixed` sang `auto` hoặc điều chỉnh `max_chunk_size` từ 1200 xuống 800):

### Cơ Chế Dọn Dẹp Chunk Mồ Côi Tự Động:
1. **Trên Vertex AI Search (`ReconciliationMode.FULL`):**
   - API Import của Discovery Engine chạy ở chế độ `FULL`. Toàn bộ các chunk cũ không còn xuất hiện trong file JSONL tải lên GCS sẽ **tự động bị xóa bỏ hoàn toàn khỏi Data Store**, ngăn chặn triệt để hiện tượng phân mảnh mồ côi làm nhiễu kết quả RAG.
2. **Trên BigQuery (Legacy):**
   - `ingest_knowledge_base.py` tự động kích hoạt truy vấn DML DELETE đối với tất cả các bản ghi có `source_uri` nằm trong danh sách tài liệu vừa nạp nhưng `id` không nằm trong staging table.

```bash
# Lệnh cập nhật lại toàn bộ tri thức cho khách hàng trên Vertex AI Search:
python scripts/ingest_knowledge_base.py \
    --backend vertex_ai_search \
    --project-id="$PROJECT_ID" \
    --gcs-bucket="$GCS_CORPUS_BUCKET" \
    --data-store-id="it-helpdesk-kb-datastore" \
    --source-dir="./knowledge_base_files"
```

---

## 4. Định Cỡ Hạ Tầng & Yêu Cầu Quota Trước Khi Triển Khai (Capacity Planning)

Trước khi chạy Terraform cho môi trường Production của khách hàng, Solutions Architect phải hoàn tất việc tính toán và yêu cầu Quota GCP:

### 4.1. Bảng Định Cỡ Hạ Tầng Chuẩn (Sizing Matrix)

| Quy Mô Khách Hàng | Tổng Nhân Sự | Peak CCU | Cloud Run Min / Max | Memorystore Redis | Vertex AI Flash Quota | Vertex AI Pro Quota |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier S (Vừa & Nhỏ)** | < 2.000 | 10 – 40 CCU | 1 / 8 instances | 1 GiB (Basic) | 300 RPM | 30 RPM |
| **Tier M (Doanh nghiệp)** | 2.000 – 10.000 | 40 – 200 CCU | 2 / 40 instances | 1 – 2 GiB (STANDARD_HA) | 1.500 RPM | 150 RPM |
| **Tier L (Tập đoàn)** | 10.000 – 50.000 | 200 – 1.000 CCU | 4 / 150 instances | 4 – 8 GiB (STANDARD_HA) | 6.000 RPM | 600 RPM |

```bash
# Cấu hình Terraform tương ứng trong terraform.tfvars
environment                      = "production"
redis_enabled                    = true
redis_memory_size_gb             = 2
min_instance_count               = 2
max_instance_count               = 40
max_instance_request_concurrency = 8
l3_rate_limit_per_minute         = 10
telemetry_anonymize_users        = true
telemetry_include_query          = false
```

### 4.2. Chạy Kiểm Thử Tải (Pre-GoLive Load Test Benchmark)

Trước khi bàn giao hệ thống cho khách hàng, kỹ sư triển khai bắt buộc phải chạy bộ script benchmark để đo lường độ trễ thực tế:

```bash
# 1. Chạy bài kiểm thử tải bậc thang 10 -> 25 -> 50 -> 100 -> 200 CCU
python scripts/load_test/run_load_test.py \
    --url="https://helpdesk.customer.corp.com" \
    --stages="10,25,50,100" \
    --stage-duration=30 \
    --output="benchmark_report.json"

# 2. Hoặc chạy kiểm thử tải giao diện web qua Locust
locust -f scripts/load_test/locustfile.py --host="https://helpdesk.customer.corp.com"
```

---

## 5. Bảng Kiểm Tra An Toàn Vận Hành (Operational Checklist)

| Hạng mục kiểm tra | Tiêu chuẩn đánh giá | Trạng thái |
| :--- | :--- | :--- |
| **Config Schema Validation** | Không chứa ký tự đặc biệt, không dùng key `ALL`. Khai báo `user_role_mappings` và `domain_keywords`. | ✅ Bắt buộc |
| **Fail-Closed Protection** | Cấu hình sai YAML hoặc thiếu Processor ID sẽ dừng nạp ngay lập tức. | ✅ Bắt buộc |
| **SSO & Real RBAC Role Mapping** | Ánh xạ vai trò chính xác qua YAML hoặc Firestore collection `user_roles`. User ngoài danh sách mặc định là `employee`. | ✅ Bắt buộc |
| **Container Hardening** | Chạy dưới quyền Non-Root `USER appuser` (uid=10001) với `HEALTHCHECK` tích hợp. | ✅ Bắt buộc |
| **Production API Shielding** | `/docs`, `/redoc`, `/openapi.json` được tự động tắt trên Production. | ✅ Bắt buộc |
| **Rate Limiting Hardening** | Rate limit key dùng token-hash hoặc client IP đằng sau Load Balancer; SHA-256 xác định đa worker. | ✅ Bắt buộc |
| **Telemetry Privacy (Fail-Closed)** | Mặc định `TELEMETRY_ANONYMIZE_USERS=true`, `TELEMETRY_INCLUDE_QUERY=false`. Độ trễ đo bằng `perf_counter()`. | ✅ Bắt buộc |
| **Vertex AI Search Pre-Filtering** | Tiền lọc metadata `system: ANY(...)` qua `build_system_filter()` chống injection và rò rỉ IDOR. | ✅ Bắt buộc |
| **ReconciliationMode.FULL** | Xoá bỏ sạch sẽ các chunk mồ côi khi nạp corpus mới vào Discovery Engine. | ✅ Bắt buộc |
| **Section Hierarchy & Multi-Chunk** | Trường `parent_doc_id` và `chunk_index` được trích xuất và bảo toàn đầy đủ. | ✅ Bắt buộc |
| **Redis Shared State & RBAC Hash** | Memorystore Redis kết nối qua Direct VPC Egress, Cache phân tách ranh giới bằng `compute_rbac_hash`. | ✅ Bắt buộc |
| **Load Test Benchmark** | Đạt p95 Latency < 2.5s ở bậc tải Peak CCU theo cam kết SLA. | ✅ Bắt buộc |
