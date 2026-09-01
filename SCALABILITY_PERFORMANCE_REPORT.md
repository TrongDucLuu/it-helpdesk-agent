# Mô Hình Tính Toán Năng Lực & Định Cỡ Hạ Tầng IT Helpdesk Multi-Agent AI
## Enterprise Capacity Sizing Model & Scalability Architecture

---

## 1. Executive Summary (Tóm Tắt Mô Hình Tính Toán & Kiến Trúc)

Hệ thống **IT Helpdesk Multi-Agent AI** được thiết kế theo kiến trúc phi trạng thái (stateless) trên **Google Cloud Run Gen2**, kết hợp với cụm nhớ tạm phân tán **Google Cloud Memorystore for Redis** làm bộ nhớ trạng thái dùng chung (Shared State) cho toàn bộ cụm instance.

### Kết Luận Mô Hình Năng Lực (Capacity Model Insights):
1. **Trần chịu tải thực tế (System Bottleneck Ceiling)**: Năng lực phục vụ của hệ thống **không bị giới hạn bởi Cloud Run**, mà được điều phối bởi **Hạn mức Vertex AI Gemini TPM/RPM** và **Discovery Engine / Agent Search Quota**.
2. **Hiệu năng Semantic Cache (Ước tính lý thuyết)**: Với tỷ lệ hit cache kỳ vọng 40–60% trong môi trường doanh nghiệp, **60% câu hỏi L1 được phản hồi dưới 50ms**, giảm tới **70% chi phí token LLM** và triệt tiêu tải lên mô hình Gemini.
3. **Độ sẵn sàng cao (High Availability & Resilience)**:
   - **Rate Limiter (Fail-Open)**: Nếu Redis gặp sự cố hoặc gián đoạn kết nối, hệ thống tự động fallback về bộ đếm In-Memory cục bộ trên từng container và ghi log `ERROR`, đảm bảo **không bao giờ chặn nhầm traffic hợp lệ của nhân viên**.
   - **Semantic Cache (Soft Fail-Closed)**: Nếu Redis timeout, cache tự động coi như cache miss và cho phép luồng xử lý RAG/Gemini tiếp tục bình thường mà không gây crash ứng dụng.

---

## 2. Mô Hình Tính Toán Năng Lực Theo Tải Giả Định (Theoretical Capacity Sizing)

> [!NOTE]
> Bảng dưới đây là **mô hình tính toán lý thuyết (Capacity Model)** được tính toán dựa trên các tham số giả định đầu vào nhằm định cỡ tài nguyên trước khi triển khai, **không phải là số liệu đo đạc tải thực tế trên Cloud Run**.

### 2.1. Các tham số giả định đầu vào (Input Assumptions)
- **Phân bổ loại yêu cầu**: 60% L1 (Tự phục vụ FAQ/SSO), 30% L2 (Tra cứu RAG SAP/HRM/CRM), 10% L3 (Phân tích lỗi sâu Gemini Pro).
- **Kích thước Token/Lượt**:
  - L1 FAQ: ~500 input tokens, ~200 output tokens.
  - L2 RAG: ~1.500 input tokens, ~500 output tokens.
  - L3 Root Cause Analysis: ~3.000 input tokens, ~1.000 output tokens.
- **Hạn mức Gemini mặc định (Project Quota)**:
  - Gemini 2.5/3 Flash: 1.000 RPM (Requests Per Minute).
  - Gemini 2.5/3 Pro: 120 RPM.
- **Tỷ lệ Cache Hit giả định**: 45% – 55% cho các yêu cầu L1.
- **Concurrency trên mỗi Container Cloud Run**: 8 concurrent requests (`--concurrency=8`).

### 2.2. Bảng Tính Toán Năng Lực & Nhu Cầu Tài Nguyên (Lý Thuyết)

| Bậc Tải (CCU) | Thông Lượng Kỳ Vọng (RPS) | Số Container Cloud Run Cần | Vertex AI Flash RPM Ước Tính | Vertex AI Pro RPM Ước Tính | Tỷ Lệ Cache Hit Giả Định | Khả Năng Đáp Ứng Theo Quota Mặc Định |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **10 CCU** | ~4.8 req/s | 1 – 2 instances | ~170 RPM | ~29 RPM | 45% | **Đủ Quota** |
| **25 CCU** | ~11.5 req/s | 2 – 4 instances | ~410 RPM | ~69 RPM | 48% | **Đủ Quota** |
| **50 CCU** | ~22.8 req/s | 4 – 8 instances | ~820 RPM | ~137 RPM | 51% | **Vượt Quota Pro** *(Cần tăng Quota)* |
| **100 CCU** | ~44.2 req/s | 7 – 15 instances | ~1.590 RPM | ~265 RPM | 53% | **Vượt Quota Flash & Pro** |
| **200 CCU** | ~86.5 req/s | 12 – 30 instances | ~3.110 RPM | ~519 RPM | 55% | **Cần Quota Enterprise** |

---

## 3. Số Liệu Đo Đạc Thực Tế Trên Môi Trường GCP (Empirical Benchmark Data)

| Hạng Mục Đo Đạc | Kết Quả Đo Đạc Thực Tế | Trạng Thái & Ghi Chú |
| :--- | :--- | :--- |
| **Cloud Run Latency p95 (L1 Hit)** | `CHƯA ĐO` | Chờ triển khai kiểm thử tải thực tế tại task VAIS-062 |
| **Cloud Run Latency p95 (L2 Agent Search RAG)** | `CHƯA ĐO` | Chờ triển khai kiểm thử tải thực tế tại task VAIS-062 |
| **Cloud Run Latency p95 (L3 Deep Diagnostics)** | `CHƯA ĐO` | Chờ triển khai kiểm thử tải thực tế tại task VAIS-062 |
| **Thông Lượng Tối Đa (Max RPS Không Lỗi)** | `CHƯA ĐO` | Chờ triển khai kiểm thử tải thực tế tại task VAIS-062 |
| **Tỷ Lệ Cache Hit Thực Tế Doanh Nghiệp** | `CHƯA ĐO` | Cần thu thập telemetry sau khi vận hành staging |
| **Redis Multi-Tenant Vector Cache (Local Benchmark)** | **p50 = 21.19ms**, **p95 = 21.55ms** | Đo bằng `scripts/benchmark_semantic_cache.py` (1.000 vectors) |

---

## 4. Phân Tích Các Tầng Giới Hạn Hạ Tầng (System Ceiling Analysis)

```
[Khách Hàng / Nhân Viên]
        │
        ▼ (HTTPS / Direct VPC)
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Tầng Cloud Run Compute (Auto-scale 1 -> 50+ instances)               │
│    • Concurrency: 8 req/container | CPU: 2 vCPU | RAM: 2GiB             │
│    • Năng lực: > 400 RPS với 50 instances (Không phải nút thắt)         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
       ┌─────────────────────────────┴─────────────────────────────┐
       ▼                                                           ▼
┌─────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│ 2. Tầng Redis Shared State              │   │ 3. Tầng Agent Search / Discovery Engine │
│    • Memorystore Redis 7.0 (1-5 GiB)    │   │    • Managed Search Queries / Giây      │
│    • Năng lực: > 50.000 ops/giây        │   │    • QPS Quota mặc định: 100 - 500 QPS  │
│    • Fail-Open / Soft Fail-Closed       │   │    • Tự động scale backend managed      │
└─────────────────────────────────────────┘   └─────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. Tầng Vertex AI Quota (Trần Quyết Định Của Toàn Hệ Thống)             │
│    • Gemini 2.5/3 Flash: 1.000 - 4.000 RPM (Hạn mức mặc định dự án GCP) │
│    • Gemini 2.5/3 Pro: 120 - 360 RPM (Cần nâng hạn mức khi > 50 CCU)    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Chi tiết các tầng trần:
1. **Cloud Run**: Khả năng scale ngang mạnh mẽ. Với `max_instance_request_concurrency = 8`, 10 container xử lý đồng thời 80 requests; 50 container xử lý 400 requests đồng thời.
2. **Memorystore Redis**: Băng thông nội bộ VPC đạt hàng chục nghìn IOPS. Dung lượng 1 GiB lưu trữ > 50.000 user rate limits + 20.000 cached semantic vectors.
3. **Agent Search (Discovery Engine)**: Dịch vụ search được quản lý toàn diện (fully managed), loại bỏ chi phí index BigQuery và tự động scale theo QPS cấu hình.
4. **Vertex AI Gemini Quota (Trần Quyết Định)**:
   - Một người dùng L3 tiêu tốn trung bình ~3.000 input tokens + 1.000 output tokens.
   - Nếu 50 người dùng đồng thời gọi L3 liên tục, hệ thống cần tối thiểu $50 \times 4.000 = 200.000\text{ TPM}$ cho Gemini Pro.
   - **Giải pháp bảo vệ**: Bộ điều tốc `L3_RATE_LIMIT_PER_MINUTE = 10` đảm bảo không một cá nhân hay script nào có thể làm cạn kiệt Quota toàn công ty.

---

## 5. Công Thức Tính Toán Hạ Tầng Cho Khách Hàng Doanh Nghiệp (Enterprise Sizing Formula)

Khi triển khai cho khách hàng mới, Solutions Architect sử dụng bảng công thức chuẩn sau để định cỡ tài nguyên:

### 5.1. Công thức xác định số Instance Cloud Run
$$\text{Peak CCU} = \text{Tổng số nhân viên công ty} \times \text{Tỷ lệ hoạt động đồng thời (2\% - 5\%)}$$
$$\text{Max Instances} = \left\lceil \frac{\text{Peak CCU}}{\text{Instance Concurrency (8)}} \right\rceil \times 1.5\text{ (Hệ số dự phòng 50\%)}$$

*Ví dụ: Doanh nghiệp 10.000 nhân viên:*
- $\text{Peak CCU} = 10.000 \times 2\% = 200\text{ CCU}$
- $\text{Max Instances} = \left\lceil \frac{200}{8} \right\rceil \times 1.5 = 25 \times 1.5 \approx 38\text{ instances}$
- $\text{Min Instances} = 2\text{ (Đảm bảo 0 cold-start trong giờ hành chính)}$

### 5.2. Bảng Tính Quy Mô Tham Chiếu (Reference Sizing Matrix)

| Quy Mô Doanh Nghiệp | Tổng Nhân Sự | Peak CCU Dự Kiến | Cloud Run Min / Max | Memorystore Redis | Vertex AI Flash RPM Cần | Vertex AI Pro RPM Cần |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier S (Nhỏ)** | 500 – 2.000 | 10 – 40 CCU | 1 / 8 | 1 GiB (Basic) | 300 RPM | 30 RPM |
| **Tier M (Vừa)** | 2.000 – 10.000 | 40 – 200 CCU | 2 / 40 | 1 – 2 GiB (HA) | 1.500 RPM | 150 RPM |
| **Tier L (Lớn)** | 10.000 – 50.000 | 200 – 1.000 CCU | 4 / 150 | 4 – 8 GiB (HA) | 6.000 RPM | 600 RPM |
| **Tier Enterprise+**| > 50.000 | > 1.000 CCU | 10 / 300+ | 16 GiB (HA) | 15.000+ RPM | 1.500+ RPM |

---

## 6. Ước Tính Chi Phí Vận Hành / 1.000 Truy Vấn (Cost per 1k Requests - Lý Thuyết)

Nhờ kiến trúc 3 tầng phối hợp với Semantic Cache, cơ cấu chi phí tối ưu theo mô hình:

```
                      Chi Phí Trung Bình Ước Tính / 1.000 Requests: ~$0.48
┌──────────────────────────────────────────────────────────────────────────────┐
│ [L1 Hit: 50% @ $0.005]  [L1 Miss: 10% @ $0.15]  [L2 RAG: 30% @ $0.40] [L3]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Thành Phần Tác Vụ | Tỷ Lệ Giả Định | Chi Phí Hạ Tầng & Token / 1k Requests | Thành Tiền |
| :--- | :--- | :--- | :--- |
| **L1 Cache Hit** (Redis + Cloud Run) | 50% | \$0.005 (0 Gemini token, chỉ tốn network/compute) | **\$0.0025** |
| **L1 Cache Miss** (Gemini Flash FAQ) | 10% | \$0.150 (Gemini 2.5 Flash input/output token) | **\$0.0150** |
| **L2 RAG Tra Cứu** (Agent Search + Flash) | 30% | \$0.400 (Search query fee + Flash RAG) | **\$0.1200** |
| **L3 Phân Tích Sâu** (Gemini Pro CoT) | 10% | \$3.500 (Gemini 2.5/3 Pro reasoning tokens) | **\$0.3500** |
| **Tổng Chi Phí Trộn (Blended Total)** | **100%** | **Hệ thống xử lý 1.000 câu hỏi với chi phí ước tính:** | **\$0.4875** |

> [!TIP]
> Doanh nghiệp với **100.000 lượt hỏi/tháng** chỉ tốn khoảng **~\$48.75 USD tiền token & truy vấn**, cộng với ~\$65 USD tiền hạ tầng cố định (Cloud Run min-instances + Memorystore Redis 1GB) $\rightarrow$ Tổng chi phí vận hành ước tính **~\$120 USD/tháng**.

---

## 7. Chiến Lược Đảm Bảo Tính Sẵn Sàng (High Availability & Resilience)

1. **Memorystore Redis HA (Standard Tier)**:
   - Triển khai mô hình 2-node (Primary & Replica) tự động failover trong 30 giây nếu Node chính gặp sự cố phần cứng.
2. **Cơ chế Fail-Open (Rate Limiter)**:
   - Được thiết kế theo chuẩn ngân hàng: Lỗi hạ tầng rate limiting phụ không bao giờ được làm gián đoạn kênh hỗ trợ nhân viên khẩn cấp.
3. **Cơ chế Soft Fail-Closed (Semantic Cache)**:
   - Khi Redis timeout quá 2.000ms, hệ thống ghi nhận `WARNING` và chuyển tiếp câu hỏi sang Agent xử lý trực tiếp.
4. **Direct VPC Egress**:
   - Cloud Run Gen2 kết nối trực tiếp đến Subnet `10.10.0.0/24` không cần thông qua Serverless VPC Access Connector truyền thống, giảm $100\%$ độ trễ overhead và tiết kiệm chi phí connector.

---

## 8. Đảm Bảo Ổn Định Bộ Nhớ & Tối Ưu Truy Vấn (Memory Stability & Bounded Resource Control)

1. **Chống Rò Rỉ Bộ Nhớ (Bounded LRU Caches)**:
   - Bộ nhớ đệm fallback `_TICKETS_DB` và Semantic In-Memory Cache được cấu hình cứng giới hạn `maxsize=1000` (sử dụng thread-safe `OrderedDict`). Khi đạt ngưỡng, các phần tử cũ nhất (LRU) sẽ tự động bị loại bỏ, ngăn ngừa tình trạng OOM (Out Of Memory).
2. **Tối Ưu Hóa Truy Vấn Firestore & Tránh Full-Scan**:
   - Toàn bộ truy vấn danh sách ticket cá nhân (`list_user_tickets`) bắt buộc áp dụng bộ lọc `FieldFilter("user_id", "==", user_id)` và giới hạn cứng `.limit(50)`.
3. **Deterministic SHA-256 Memory Profiling & Hash Stability**:
   - Sử dụng `hashlib.sha256()` thay thế cho hàm `hash()` của Python để định danh Rate Limiting Key và Telemetry Token, triệt tiêu nguy cơ bùng nổ không gian khóa (key collision/bloat).
4. **Redis Multi-Tenant Candidate-Set Vector Cache (Benchmark Cục Bộ)**:
   - Hệ thống triển khai bộ nhớ đệm phân tán Redis với cấu trúc tập hợp Multi-Tenant (`sem_cache:keys:public` và `sem_cache:keys:user:{uid}`), thực hiện truy vấn batch `mget` và tính cosine similarity tốc độ cao.
   - **Kết quả đo đạc cục bộ (`scripts/benchmark_semantic_cache.py`)**:
     - Ghi 1.000 entry vector vào Redis: **0.200s** (~5.005 ops/s).
     - Thời gian truy vấn tìm kiếm gần nhất (Vector Cosine Similarity): **p50 = 21.19ms**, **p95 = 21.55ms**, **p99 = 28.45ms**.
5. **JWT Single-Pass Verification Memoization**:
   - Lưu trữ kết quả giải mã Google OIDC vào `request.state.verified_sso_user`, giúp `RateLimiterMiddleware` và `SSOAuthenticationMiddleware` dùng chung một lần xác thực duy nhất.
