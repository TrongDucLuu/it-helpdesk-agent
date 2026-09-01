# Constraints — IT Helpdesk Multi-Agent AI (Vertex AI Search Migration)

Last reviewed: 2026-09-01 by Solution Architect Đức (Gimasys) & Antigravity

## 1. Ràng Buộc Tuyệt Đối (Absolute Invariants)

1. **Không xoá `InMemoryKnowledgeStore`**: Toàn bộ unit test và eval harness offline phụ thuộc vào nó.
2. **Không đổi tên tool `search_enterprise_knowledge` và `get_system_manual`**: Instruction của `l2_enterprise_rag_agent` và các sub-agent tham chiếu trực tiếp; đổi tên là phá vỡ prompt contract.
3. **RBAC luôn được inject bằng code, tuyệt đối không bao giờ để LLM truyền `allowed_systems`**: LLM chỉ được truyền `query` và tối đa là `system` (một gợi ý, không phải một quyền). Giá trị `allowed_systems` cuối cùng phải được tính từ `current_sso_user` ở phía server và intersect với gợi ý của LLM. Tuyệt đối không thêm tham số quyền vào tool signature mà LLM có thể điền (tránh lỗ hổng Prompt Injection tự nâng quyền).
4. **Giữ nguyên các hàm phòng thủ Prompt Injection**: `wrap_retrieved_document()`, `sanitize_retrieved_content()`, `escape_xml_attribute()` và hằng số `INDIRECT_PROMPT_INJECTION_DEFENSE_INSTRUCTION`. Đây là lớp phòng thủ indirect prompt injection, nghiêm cấm "đơn giản hoá" hay gỡ bỏ.
5. **Fail-closed**: Mọi lỗi backend, lỗi timeout, lỗi thiếu identity đều phải dẫn tới 0 kết quả hoặc thông báo lỗi tường minh, tuyệt đối không bao giờ fallback sang dữ liệu không được phân quyền.
6. **Không đánh dấu task DONE nếu chưa chạy thật một lần trên GCP**: PR description / commit report phải ghi rõ: project ID, region, data store ID, timestamp, và output thật của lần chạy đó. Mock không tính là chạy.
7. **Không tự sinh số liệu hiệu năng**: Nếu một task yêu cầu số latency/recall mà chưa đo được, ghi `CHƯA ĐO` chứ không ước lượng ra con số nhìn có vẻ hợp lý.
8. **Một task = một commit = một test**: Không refactor kèm, không gộp nhiều task vào một commit.
9. **Mọi API surface phải có link doc chính thức** trong comment code, ADR hoặc PR description (theo skill `source-driven-development`).

---

## 2. Floor (Luôn Thực Thi, Không Hạ Chuẩn)

- Không thêm comment triệt tiêu linter mới: `# noqa`, `# type: ignore`, `# pylint: disable`.
- Không tạo stub chưa hoàn thiện: `raise NotImplementedError`, `except: pass` im lặng.
- Không xoá hoặc skip test mà không có lý do được ghi rõ trong commit message.
- Không lưu secret / API key / credentials trong mã nguồn.
- File `CONSTRAINTS.md` này không bao giờ bị nới lỏng hay suy giảm để làm cho code pass kiểm thử.

---

## 3. Chỉ Số Kiểm Thử & Đo Đạc (Enforced Dimensions)

| Dimension | Rule | Checked by | Runs at |
|---|---|---|---|
| Unit Test Suite | 100% tests pass | `.venv/bin/pytest tests/unit/` | Mọi edit / task |
| Integration Tests | Pass với RBAC in-process | `.venv/bin/pytest tests/integration/` | Task end |
| Eval Quality Gates | Intent >= 85%, Precision >= 80%, Refusal >= 90%, Injection = 100% | `.venv/bin/python scripts/eval_harness.py` | Task end, CI |
| Code Hygiene | 0 xuất hiện `_mock_return_value` trong `it_helpdesk_agent/` | `grep -rn "_mock_return_value" it_helpdesk_agent/` | VAIS-011, Review |
| Documentation | 100% API Discovery Engine có link official doc | Source code comments / ADRs | Review |

---

## 4. Measured, Not Yet Enforced

| Metric | Baseline Hiện Tại | Target |
|---|---|---|
| L2 RAG p95 Latency | `CHƯA ĐO` (Mô hình tính toán) | Đo thật sau VAIS-062 |
| Vertex AI Search Recall@3 | `CHƯA ĐO` | Đo thật sau VAIS-062 |
| BigQuery Vector Recall@3 | `CHƯA ĐO` | Đo thật sau VAIS-062 |
