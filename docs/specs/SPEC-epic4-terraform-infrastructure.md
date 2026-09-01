# Technical Specification: Epic 4 — Terraform & Hạ Tầng cho Vertex AI Search (Agent Search)

**Target Backlog Tasks:** VAIS-040, VAIS-041, VAIS-042, VAIS-043, VAIS-044  
**Date:** 2026-09-01  
**Status:** DRAFT (Ready for Review)  

---

## 1. Mục tiêu và Bối cảnh

Epic 4 chịu trách nhiệm cấu hình hạ tầng Infrastructure as Code (Terraform) để cung cấp tài nguyên Discovery Engine (Agent Search) trên Google Cloud tuân thủ nguyên tắc Least Privilege, Data Residency và Bảo mật cấp Doanh nghiệp.

Các mục tiêu chính:
1. **Module Discovery Engine (`vertex_ai_search.tf`)**:
   - Khởi tạo Data Store và Search Engine/App.
   - Tạo GCS Corpus Bucket với Uniform Bucket-Level Access, Object Versioning, Public Access Prevention.
   - Ghi rõ tính chất **IMMUTABLE** của thuộc tính `acl_enabled`.
2. **Data Residency & Localization**:
   - Xoá bỏ giá trị default `us-central1` trong `variables.tf`.
   - Bổ sung `validation` block giới hạn các location Discovery Engine được chứng thực (`asia-southeast1`, `global`, `us`, `eu`).
   - Cập nhật mục kiểm tra Data Residency trong `Runbook_Onboarding_Khach_Hang.md`.
3. **IAM Least Privilege**:
   - Cấp quyền `roles/discoveryengine.viewer` cho Cloud Run Service Account khi dùng backend `vertex_ai_search`.
   - Chuyển `roles/bigquery.jobUser` và `dataViewer` sang dạng điều kiện (`knowledge_backend == "bigquery"`).
4. **Conditional BigQuery Resources**:
   - BigQuery Dataset, Knowledge Table, và DLQ Table chuyển sang `count = var.knowledge_backend == "bigquery" ? 1 : 0`.
   - Đặt default `knowledge_backend = "vertex_ai_search"`.
5. **Audit Logging & Enterprise Security**:
   - Kích hoạt Google Cloud Project Audit Config cho `discoveryengine.googleapis.com` (DATA_READ, DATA_WRITE).
   - Thiết lập các biến tuỳ chọn cho CMEK (Customer-Managed Encryption Keys) và VPC Service Controls.

---

## 2. Ràng buộc Tuân thủ (CONSTRAINTS.md)

1. **Source-Driven Development**:
   - *Discovery Engine Terraform Resource Reference*: `https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/discovery_engine_data_store`
   - *Discovery Engine IAM Roles Reference*: `https://cloud.google.com/generative-ai-app-builder/docs/access-control`
   - *Discovery Engine Audit Logs Reference*: `https://cloud.google.com/generative-ai-app-builder/docs/audit-logging`
2. **Fail-Closed**: Không cấu hình mặc định sai vùng hoặc quyền vượt ngưỡng.

---

## 3. Danh sách File cần Tạo và Chỉnh sửa

| File | Hành động | Mục đích |
|---|---|---|
| `deployment/terraform/vertex_ai_search.tf` | **Tạo mới** | Tài nguyên Data Store, Search Engine, GCS Corpus Bucket, IAM cho Discovery Engine. |
| `deployment/terraform/variables.tf` | **Chỉnh sửa** | Bỏ default region, thêm validation block, đổi default `knowledge_backend = "vertex_ai_search"`. |
| `deployment/terraform/main.tf` | **Chỉnh sửa** | Điều kiện hoá BigQuery resources và IAM, thêm Audit Config cho `discoveryengine.googleapis.com`. |
| `Runbook_Onboarding_Khach_Hang.md` | **Chỉnh sửa** | Thêm mục khảo sát "Data Residency & Compliance" bắt buộc trước khi triển khai. |

---
