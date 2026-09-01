# Technical Specification: Epic 2 — Knowledge Layer Adapter Mới (Agent Search / Discovery Engine)

## 1. Objective & Scope
Epic 2 xây dựng adapter tri thức mới kết nối với Google Cloud Discovery Engine (Agent Search / Vertex AI Search), chuẩn hóa contract truy vấn tri thức thống nhất trên cả 3 backend (`in_memory`, `bigquery`, `vertex_ai_search`), bảo đảm an ninh RBAC với filter builder chống injection, và chuẩn hóa điểm số tương đồng `relevance_score` về dải $[0.0, 1.0]$.

### Tasks Included:
- **VAIS-020**: Chuẩn hoá contract `BaseKnowledgeStore` và `SearchResult` (thêm `chunk_id`, `parent_doc_id`, chuẩn hóa `relevance_score` về $[0.0, 1.0]$).
- **VAIS-021**: Hiện thực `VertexAiSearchKnowledgeStore` trong `it_helpdesk_agent/tools/enterprise_rag/vertex_search_store.py` sử dụng `google-cloud-discoveryengine`.
- **VAIS-022**: Xây dựng `FilterBuilder` an toàn (`it_helpdesk_agent/tools/enterprise_rag/filter_builder.py`) và bộ kiểm thử Fuzzing chống Injection (≥20 payloads).
- **VAIS-023**: Nâng cấp `get_knowledge_store()` Factory hỗ trợ 3 backend tường minh, fail-closed khi gặp backend lạ.
- **VAIS-024**: Hiện thực cơ chế lọc Governance (ngày hiệu lực/hết hạn và tài liệu xoá mềm) trên `VertexAiSearchKnowledgeStore`.

---

## 2. Source-Driven Documentation References
Mọi API surface của Discovery Engine được xác thực trực tiếp qua tài liệu chính thức của Google:
1. **SearchServiceClient API & ServingConfig**:
   - URL: `https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.services.search_service.SearchServiceClient`
   - Python Client: `google.cloud.discoveryengine_v1.SearchServiceClient`
   - Search Method: `search(request=google.cloud.discoveryengine_v1.SearchRequest(...))`
2. **Filter Expressions Syntax in Discovery Engine**:
   - URL: `https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata`
   - Metadata Filter Syntax: `system: ANY("ERP", "HRM")` hoặc `structData.system: ANY("ERP")`.
3. **ContentSearchSpec & Snippet Extraction**:
   - URL: `https://cloud.google.com/generative-ai-app-builder/docs/snippets`
   - `ContentSearchSpec.SnippetSpec(return_snippet=True)`
4. **DataStore and Document ACLs**:
   - URL: `https://cloud.google.com/generative-ai-app-builder/docs/document-level-access`

---

## 3. Architecture & Data Structures

### 3.1. Standardized `SearchResult` Dataclass
```python
@dataclass
class SearchResult:
    article_id: str
    system: str
    title: str
    snippet: str
    relevance_score: float  # Bắt buộc chuẩn hóa 0.0 <= relevance_score <= 1.0
    section_hierarchy: Optional[SectionHierarchy] = None
    context_path: Optional[str] = None
    source_uri: Optional[str] = None
    category: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    owner: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    is_deleted: bool = False
    is_truncated: bool = False
    chunk_id: Optional[str] = None        # Mới: VAIS-020
    parent_doc_id: Optional[str] = None   # Mới: VAIS-020
```

### 3.2. `build_system_filter` Contract (VAIS-022)
- Nhận: `allowed_systems: list[str]`.
- Logic:
  1. Loại bỏ các giá trị không nằm trong whitelist `get_configured_systems()`.
  2. Escape các ký tự đặc biệt nếu có.
  3. Nếu danh sách hợp lệ rỗng: Trả về filter chặn toàn bộ `system: ANY("__NO_SYSTEM_ACCESS__")` (Fail-Closed, tuyệt đối không trả chuỗi rỗng `""`).
  4. Nếu danh sách có giá trị: Sinh chuỗi `system: ANY("SYS1", "SYS2")`.

### 3.3. Factory Backend Enum (VAIS-023)
`KNOWLEDGE_BACKEND` chấp nhận 3 giá trị:
- `"in_memory"`: `InMemoryKnowledgeStore`
- `"bigquery"`: `BigQueryVectorKnowledgeStore`
- `"vertex_ai_search"` (hoặc `"agent_search"`): `VertexAiSearchKnowledgeStore`
- Bất kỳ giá trị nào khác: Raise `SystemConfigurationError` (Fail-Closed, không fallback ngầm).

---

## 4. Verification & Testing Plan
1. **VAIS-020**: `tests/unit/test_schema_parity.py` kiểm tra schema parity và khoảng giá trị `relevance_score` của cả 3 store.
2. **VAIS-021**: `tests/unit/test_vertex_search_store.py` kiểm thử mock SearchServiceClient và mapping SearchResult.
3. **VAIS-022**: `tests/unit/test_filter_builder_fuzz.py` kiểm thử ≥20 vector tấn công injection vào metadata filter.
4. **VAIS-023**: `tests/unit/test_knowledge_store_factory.py` kiểm thử cả 3 nhánh factory và fail-closed khi truyền giá trị sai.
5. **VAIS-024**: `tests/unit/test_governance_vertex_search.py` kiểm thử lọc tài liệu hết hạn và tombstone.
