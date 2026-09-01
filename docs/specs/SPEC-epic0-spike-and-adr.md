# Spec: Epic 0 — Spike Discovery Engine (Agent Search) & Architecture Decision Records (ADRs)

## 1. Objective
Xác thực toàn bộ API surface thực tế của Google Cloud Discovery Engine / Vertex AI Search (Agent Search) thông qua tài liệu chính thức và mã thực nghiệm có thể chạy được, đồng thời thiết lập 3 bản ADR cốt lõi định hình kiến trúc trước khi bước vào triển khai mã nguồn:
- **VAIS-001**: Spike API surface, xác minh SDK `google-cloud-discoveryengine`, version `v1`/`v1beta`, cú pháp `filter` metadata, tính bất biến của `acl_enabled`, hỗ trợ vùng `asia-southeast1`, và giới hạn công cụ ADK `VertexAiSearchTool`.
- **VAIS-002**: ADR RBAC Enforcement: So sánh Option A (Metadata filter + service account) và Option B (Document-level ACL + end-user credential), ma trận khách hàng và hệ quả của cờ `acl_enabled`.
- **VAIS-003**: ADR Retrieval Granularity & Chunking Strategy: Trade-off giữa client-side chunking (`chunkers.py`) và managed layout-aware chunking của Google Discovery Engine.

## 2. Tech Stack & Official Sources
- **SDK**: `google-cloud-discoveryengine>=0.13.0` (Client: `discoveryengine_v1.SearchServiceClient`, `discoveryengine_v1.DocumentServiceClient`, `discoveryengine_v1.DataStoreServiceClient`).
- **Official Documentation Links (Source-Driven Development)**:
  - Locations & Endpoints: https://cloud.google.com/generative-ai-app-builder/docs/locations
  - Data Store Creation & Content Config: https://cloud.google.com/generative-ai-app-builder/docs/create-data-store-es
  - Metadata Filtering Syntax: https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
  - Snippets & ContentSearchSpec: https://cloud.google.com/generative-ai-app-builder/docs/snippets
  - Document Import & Reconciliation: https://cloud.google.com/generative-ai-app-builder/docs/import-documents
  - Document Level Access Control (ACL): https://cloud.google.com/generative-ai-app-builder/docs/document-level-access

## 3. Commands
- Run Spike script:
  ```bash
  .venv/bin/python scripts/spike/vais_smoke.py --project-id <PROJECT_ID> --location <LOCATION>
  ```
- Validate Syntax & Lint:
  ```bash
  .venv/bin/pytest tests/unit/ -k "not integration"
  ```

## 4. Project Structure
```
docs/
├── adr/
│   ├── 0001-knowledge-layer-agent-search.md  (VAIS-001)
│   ├── 0002-rbac-enforcement.md               (VAIS-002)
│   └── 0003-chunking-strategy.md              (VAIS-003)
└── specs/
    ├── SPEC-capability-map.md
    └── SPEC-epic0-spike-and-adr.md
scripts/
└── spike/
    └── vais_smoke.py                          (Spike verification script)
```

## 5. Testing & Verification Strategy
- `scripts/spike/vais_smoke.py`: Script độc lập kiểm tra kết nối API, tạo Data Store test, nạp tài liệu mẫu và thực thi search có bộ lọc metadata.
- Unit tests: Kiểm tra các module không yêu cầu kết nối mạng vẫn hoạt động khi không có credential.

## 6. Boundaries
- **Always do**: Trích dẫn URL tài liệu chính thức cho mọi khẳng định API; kiểm tra kỹ ràng buộc immutable của `acl_enabled`.
- **Ask first**: Không tự ý tạo resource tính phí trên GCP nếu chưa có cấu hình project/credentials môi trường.
- **Never do**: Bịa đặt thông số latency, hỗ trợ vùng hoặc cú pháp filter; không xoá `InMemoryKnowledgeStore`.

## 7. Success Criteria
- [ ] ADR `docs/adr/0001-knowledge-layer-agent-search.md` hoàn thành với đầy đủ API surface, phiên bản SDK, cú pháp `filter`, kết luận về `asia-southeast1`.
- [ ] Script `scripts/spike/vais_smoke.py` được tạo với cú pháp chuẩn xác theo official SDK.
- [ ] ADR `docs/adr/0002-rbac-enforcement.md` hoàn thành với threat model 2 phương án (A vs B), ma trận phân loại khách hàng và khuyến nghị rõ ràng.
- [ ] ADR `docs/adr/0003-chunking-strategy.md` hoàn thành với phân tích trade-off chi tiết giữa tự chunk và managed chunking.
