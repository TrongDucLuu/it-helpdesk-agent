"""
Unit Tests for Knowledge Store Factory (VAIS-023).

Verifies:
- Explicit backend parameter resolution for all 3 supported backends.
- Environment variable overrides (KNOWLEDGE_STORE_BACKEND, KNOWLEDGE_BACKEND).
- Strict Fail-Closed enforcement: unknown backends raise ValueError immediately with zero fallback.
"""

import pytest
from it_helpdesk_agent.tools.enterprise_rag_mcp.knowledge_store import (
    get_knowledge_store,
    InMemoryKnowledgeStore,
    BigQueryVectorKnowledgeStore,
)
from it_helpdesk_agent.tools.enterprise_rag.vertex_search_store import (
    VertexAiSearchKnowledgeStore,
)


def test_factory_default_in_memory(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_STORE_BACKEND", raising=False)
    monkeypatch.delenv("KNOWLEDGE_BACKEND", raising=False)

    store = get_knowledge_store()
    assert isinstance(store, InMemoryKnowledgeStore)


def test_factory_explicit_backends():
    # 1. InMemory
    store_mem = get_knowledge_store("in_memory")
    assert isinstance(store_mem, InMemoryKnowledgeStore)

    # 2. BigQuery
    store_bq = get_knowledge_store("bigquery")
    assert isinstance(store_bq, BigQueryVectorKnowledgeStore)

    # 3. Vertex AI Search / Agent Search
    store_vais = get_knowledge_store("vertex_ai_search")
    assert isinstance(store_vais, VertexAiSearchKnowledgeStore)

    store_agent = get_knowledge_store("agent_search")
    assert isinstance(store_agent, VertexAiSearchKnowledgeStore)


def test_factory_env_var_overrides(monkeypatch):
    # Test KNOWLEDGE_STORE_BACKEND
    monkeypatch.setenv("KNOWLEDGE_STORE_BACKEND", "vertex_ai_search")
    store = get_knowledge_store()
    assert isinstance(store, VertexAiSearchKnowledgeStore)

    # Test KNOWLEDGE_BACKEND fallback env
    monkeypatch.delenv("KNOWLEDGE_STORE_BACKEND", raising=False)
    monkeypatch.setenv("KNOWLEDGE_BACKEND", "bigquery")
    store_bq = get_knowledge_store()
    assert isinstance(store_bq, BigQueryVectorKnowledgeStore)


def test_factory_invalid_backend_fails_closed(monkeypatch):
    """Verifies that invalid or unsupported backends fail closed without silent fallback."""
    # 1. Direct argument
    with pytest.raises(ValueError) as exc_info:
        get_knowledge_store("elasticsearch")
    assert "Knowledge store backend không hợp lệ" in str(exc_info.value)
    assert "elasticsearch" in str(exc_info.value)

    # 2. Env variable
    monkeypatch.setenv("KNOWLEDGE_STORE_BACKEND", "redis_vector")
    with pytest.raises(ValueError) as exc_info2:
        get_knowledge_store()
    assert "Knowledge store backend không hợp lệ" in str(exc_info2.value)
    assert "redis_vector" in str(exc_info2.value)
