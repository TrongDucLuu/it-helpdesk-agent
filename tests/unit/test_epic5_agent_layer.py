"""
Unit tests for Epic 5: Agent Layer (VAIS-050 to VAIS-054)
- VAIS-050: L2 Agent tool wiring (in-process FunctionTool, ticketing, search, manual, email)
- VAIS-051: get_system_manual multi-chunk aggregation across parent_doc_id
- VAIS-052: RAG top_k configurable via RAG_TOP_K environment variable with bounds
- VAIS-053: Semantic cache RBAC-aware scoping with allowed_systems hash & tier TTLs
- VAIS-054: Latency budget & graceful timeout fallback with error logging
"""

import os
import time
import pytest
from unittest.mock import MagicMock, patch

from it_helpdesk_agent.agent import (
    l2_enterprise_rag_agent,
    INDIRECT_PROMPT_INJECTION_DEFENSE_INSTRUCTION,
)
from it_helpdesk_agent.app_utils.sso_auth import SSOUser, current_sso_user
from it_helpdesk_agent.app_utils.semantic_cache import (
    InMemorySemanticCache,
    compute_rbac_hash,
    SemanticCacheEntry,
)
from it_helpdesk_agent.tools.enterprise_rag.rag_tools import (
    search_enterprise_knowledge,
    get_system_manual,
    _get_rag_top_k,
    _get_rag_timeout_seconds,
)
from it_helpdesk_agent.tools.enterprise_rag_mcp.knowledge_store import (
    InMemoryKnowledgeStore,
    KnowledgeArticle,
)


@pytest.fixture(autouse=True)
def default_sso_context():
    """Sets a standard SSO user context with ERP, HRM, CRM permissions."""
    user = SSOUser(
        user_id="test-engineer-01",
        email="eng@company.com",
        roles=["it_admin", "erp_user", "hr_manager", "sales_rep"],
        allowed_systems=["ERP", "HRM", "CRM"],
    )
    token = current_sso_user.set(user)
    yield user
    current_sso_user.reset(token)


# ==============================================================================
# VAIS-050: L2 Agent Tool Wiring
# ==============================================================================
def test_vais_050_l2_agent_tool_wiring():
    """Verify L2 Enterprise RAG Agent has all required tools wired in-process."""
    tool_names = []
    for tool in l2_enterprise_rag_agent.tools:
        if hasattr(tool, "name"):
            tool_names.append(tool.name)
        elif hasattr(tool, "__name__"):
            tool_names.append(tool.__name__)

    assert "search_enterprise_knowledge" in tool_names
    assert "get_system_manual" in tool_names
    assert "draft_email_response" in tool_names
    assert "update_ticket_status" in tool_names
    assert "route_ticket_to_tier" in tool_names
    assert "get_ticket_details" in tool_names
    assert "create_helpdesk_ticket" in tool_names

    assert l2_enterprise_rag_agent.disallow_transfer_to_peers is True
    assert l2_enterprise_rag_agent.before_model_callback is not None
    assert l2_enterprise_rag_agent.after_model_callback is not None

    # Verify instruction contains prompt injection defense
    assert "Indirect Prompt Injection Defense" in l2_enterprise_rag_agent.instruction
    assert "search_enterprise_knowledge" in l2_enterprise_rag_agent.instruction
    assert "get_system_manual" in l2_enterprise_rag_agent.instruction


# ==============================================================================
# VAIS-051: get_system_manual Multi-Chunk Aggregation
# ==============================================================================
def test_vais_051_get_article_by_id_multi_chunk_aggregation():
    """Verify InMemoryKnowledgeStore reassembles multi-chunk articles sorted by chunk_index."""
    store = InMemoryKnowledgeStore()
    store.clear()

    # Create a 3-chunk document sharing parent_doc_id="MANUAL-ERP-001"
    chunk_0 = KnowledgeArticle(
        id="MANUAL-ERP-001#chunk_0",
        title="Quy trình Mở Kỳ Kế Toán ERP - Phần 1",
        system="ERP",
        category="Finance",
        content="Nội dung Chương 1: Kiểm tra chứng từ tồn đọng.",
        chunk_index=0,
        parent_doc_id="MANUAL-ERP-001",
    )
    chunk_1 = KnowledgeArticle(
        id="MANUAL-ERP-001#chunk_1",
        title="Quy trình Mở Kỳ Kế Toán ERP - Phần 2",
        system="ERP",
        category="Finance",
        content="Nội dung Chương 2: Thực hiện lệnh t-code OB52 trên SAP.",
        chunk_index=1,
        parent_doc_id="MANUAL-ERP-001",
    )
    chunk_2 = KnowledgeArticle(
        id="MANUAL-ERP-001#chunk_2",
        title="Quy trình Mở Kỳ Kế Toán ERP - Phần 3",
        system="ERP",
        category="Finance",
        content="Nội dung Chương 3: Xác nhận thông báo và đối chiếu số dư.",
        chunk_index=2,
        parent_doc_id="MANUAL-ERP-001",
    )

    # Add out of order to ensure sorting works
    store.add_article(chunk_1)
    store.add_article(chunk_2)
    store.add_article(chunk_0)

    # 1. Lookup by parent_doc_id
    full_doc = store.get_article_by_id("MANUAL-ERP-001")
    assert full_doc is not None
    assert full_doc.id == "MANUAL-ERP-001"
    expected_content = (
        "Nội dung Chương 1: Kiểm tra chứng từ tồn đọng.\n\n"
        "Nội dung Chương 2: Thực hiện lệnh t-code OB52 trên SAP.\n\n"
        "Nội dung Chương 3: Xác nhận thông báo và đối chiếu số dư."
    )
    assert full_doc.content == expected_content

    # 2. Lookup by chunk_id should also resolve to the parent full doc
    full_doc_via_chunk = store.get_article_by_id("MANUAL-ERP-001#chunk_1")
    assert full_doc_via_chunk is not None
    assert full_doc_via_chunk.content == expected_content


def test_vais_051_get_system_manual_tool_multi_chunk():
    """Verify get_system_manual tool formats and returns full reassembled document."""
    with patch("it_helpdesk_agent.tools.enterprise_rag.rag_tools.get_knowledge_store") as mock_get_store:
        mock_store = InMemoryKnowledgeStore()
        mock_store.clear()
        mock_store.add_article(
            KnowledgeArticle(
                id="DOC-777",
                title="SOP Hướng dẫn Backup",
                system="ERP",
                category="Infra",
                content="Bước 1: Snapshot DB.\n\nBước 2: Upload GCS.",
            )
        )
        mock_get_store.return_value = mock_store

        result = get_system_manual(article_id="DOC-777")
        assert result["status"] == "success"
        assert "article" in result
        content = result["article"]["content"]
        assert "retrieved_document" in content
        assert "Bước 1: Snapshot DB" in content
        assert "Bước 2: Upload GCS" in content


# ==============================================================================
# VAIS-052: RAG top_k Configurable & Bounds
# ==============================================================================
def test_vais_052_rag_top_k_bounds_and_configuration():
    """Verify _get_rag_top_k parses RAG_TOP_K and clamps to [1, 100]."""
    # Default when unset
    with patch.dict(os.environ, {}, clear=True):
        assert _get_rag_top_k() == 8

    # Custom valid value
    with patch.dict(os.environ, {"RAG_TOP_K": "15"}):
        assert _get_rag_top_k() == 15

    # Boundary lower clamp (<= 0 -> 1)
    with patch.dict(os.environ, {"RAG_TOP_K": "0"}):
        assert _get_rag_top_k() == 1
    with patch.dict(os.environ, {"RAG_TOP_K": "-5"}):
        assert _get_rag_top_k() == 1

    # Boundary upper clamp (> 100 -> 100)
    with patch.dict(os.environ, {"RAG_TOP_K": "150"}):
        assert _get_rag_top_k() == 100

    # Invalid non-integer string fallback
    with patch.dict(os.environ, {"RAG_TOP_K": "not-a-number"}):
        assert _get_rag_top_k() == 8


def test_vais_052_search_enterprise_knowledge_passes_top_k():
    """Verify search_enterprise_knowledge passes configured top_k to knowledge store."""
    with patch("it_helpdesk_agent.tools.enterprise_rag.rag_tools.get_knowledge_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.search.return_value = []
        mock_get_store.return_value = mock_store

        with patch.dict(os.environ, {"RAG_TOP_K": "12"}):
            results = search_enterprise_knowledge(query="kiem tra quota")
            assert isinstance(results, list)
            assert len(results) == 0
            mock_store.search.assert_called_once()
            _, kwargs = mock_store.search.call_args
            assert kwargs.get("limit") == 12


# ==============================================================================
# VAIS-053: Semantic Cache RBAC-Aware Scoping & TTLs
# ==============================================================================
def test_vais_053_compute_rbac_hash():
    """Verify compute_rbac_hash is deterministic, case-insensitive, and order-independent."""
    assert compute_rbac_hash(None) is None

    hash1 = compute_rbac_hash(["ERP", "HRM"])
    hash2 = compute_rbac_hash(["hrm", "ERP"])
    hash3 = compute_rbac_hash(["HRM", "ERP", "ERP"])  # deduplication
    assert hash1 == hash2 == hash3
    assert len(hash1) == 16

    hash_diff = compute_rbac_hash(["CRM"])
    assert hash1 != hash_diff


def test_vais_053_semantic_cache_rbac_isolation_and_permission_revocation():
    """Verify cache hit when RBAC permissions match and cache miss when permissions change."""
    cache = InMemorySemanticCache()
    cache.clear()

    # User caches a query with ERP and HRM access
    cache.set(
        query="Hướng dẫn phân quyền Purchase Order SAP",
        response="Để phân quyền PO, truy cập t-code SU01...",
        user_id="user-erp-01",
        is_public=False,
        tier="l2_enterprise_rag_agent",
        allowed_systems=["ERP", "HRM"],
    )

    # 1. Same user with identical permissions -> Cache Hit
    hit = cache.get(
        query="Hướng dẫn phân quyền Purchase Order SAP",
        user_id="user-erp-01",
        tier="l2_enterprise_rag_agent",
        allowed_systems=["ERP", "HRM"],
    )
    assert hit is not None
    assert hit["status"] == "cache_hit"
    assert "SU01" in hit["response"]

    # 2. User has permission revoked (e.g. only HRM left) -> Cache Miss (Hash Mismatch)
    miss_revoked = cache.get(
        query="Hướng dẫn phân quyền Purchase Order SAP",
        user_id="user-erp-01",
        tier="l2_enterprise_rag_agent",
        allowed_systems=["HRM"],
    )
    assert miss_revoked is None

    # 3. Different user without access -> Cache Miss
    miss_diff_user = cache.get(
        query="Hướng dẫn phân quyền Purchase Order SAP",
        user_id="user-other-02",
        tier="l2_enterprise_rag_agent",
        allowed_systems=["ERP", "HRM"],
    )
    assert miss_diff_user is None


def test_vais_053_semantic_cache_tier_aware_ttl():
    """Verify L2 cache entry receives SEMANTIC_CACHE_TTL_L2 (1800s) default TTL."""
    cache = InMemorySemanticCache()
    cache.clear()

    entry_l2 = cache.set(
        query="Quy trình mở cổng VPN L2",
        response="Hướng dẫn cấu hình OpenVPN L2",
        user_id="user-01",
        tier="l2_enterprise_rag_agent",
    )
    assert entry_l2 is not None
    # TTL should be around 1800s
    expected_expiry = entry_l2.created_at + 1800
    assert abs(entry_l2.expires_at - expected_expiry) < 5.0

    entry_l1 = cache.set(
        query="Giờ làm việc IT Helpdesk",
        response="Từ 8:00 đến 17:30",
        user_id="user-01",
        tier="l1_selfservice_agent",
    )
    assert entry_l1 is not None
    # TTL should be default 86400s
    expected_expiry_l1 = entry_l1.created_at + 86400
    assert abs(entry_l1.expires_at - expected_expiry_l1) < 5.0


# ==============================================================================
# VAIS-054: Latency Budget & Timeout Fallback
# ==============================================================================
def test_vais_054_rag_timeout_seconds_config():
    """Verify _get_rag_timeout_seconds defaults to 4.0s and respects env."""
    with patch.dict(os.environ, {}, clear=True):
        assert _get_rag_timeout_seconds() == 4.0

    with patch.dict(os.environ, {"RAG_SEARCH_TIMEOUT_SECONDS": "2.5"}):
        assert _get_rag_timeout_seconds() == 2.5

    with patch.dict(os.environ, {"RAG_SEARCH_TIMEOUT_SECONDS": "invalid"}):
        assert _get_rag_timeout_seconds() == 4.0


def test_vais_054_search_enterprise_knowledge_timeout_fallback():
    """Verify slow knowledge search exceeding timeout returns graceful Vietnamese fallback."""
    with patch("it_helpdesk_agent.tools.enterprise_rag.rag_tools.get_knowledge_store") as mock_get_store:
        mock_store = MagicMock()

        def slow_search(*args, **kwargs):
            time.sleep(0.5)
            return []

        mock_store.search.side_effect = slow_search
        mock_get_store.return_value = mock_store

        # Set aggressive timeout of 0.05s to test timeout handling
        with patch.dict(os.environ, {"RAG_SEARCH_TIMEOUT_SECONDS": "0.05"}):
            results = search_enterprise_knowledge(query="truy van he thong bi treo")
            assert isinstance(results, list)
            assert len(results) == 1
            assert results[0]["article_id"] == "SEARCH-TIMEOUT"
            assert "⚠️ [Hệ thống bận]" in results[0]["snippet"]
            assert "vượt quá giới hạn cho phép" in results[0]["snippet"]


def test_vais_054_get_system_manual_timeout_fallback():
    """Verify slow get_system_manual exceeding timeout returns graceful Vietnamese fallback."""
    with patch("it_helpdesk_agent.tools.enterprise_rag.rag_tools.get_knowledge_store") as mock_get_store:
        mock_store = MagicMock()

        def slow_get_article(*args, **kwargs):
            time.sleep(0.5)
            return None

        mock_store.get_article_by_id.side_effect = slow_get_article
        mock_get_store.return_value = mock_store

        with patch.dict(os.environ, {"RAG_SEARCH_TIMEOUT_SECONDS": "0.05"}):
            result = get_system_manual(article_id="DOC-TIMEOUT-001")
            assert result["status"] == "error"
            assert result["error_code"] == "SEARCH_TIMEOUT"
            assert "⚠️ [Hệ thống bận]" in result["message"]
            assert "vượt quá giới hạn cho phép" in result["message"]
