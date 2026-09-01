"""
In-Process Enterprise RAG Tools for IT Helpdesk Agents

This module provides in-process callable tools for ADK agents, eliminating the
stdio subprocess boundary of MCP so that contextvars (specifically `current_sso_user`)
propagate seamlessly for strict RBAC enforcement on Cloud Run and local environments.

Official Documentation References (Source-Driven Development):
- Discovery Engine Python SDK: https://cloud.google.com/generative-ai-app-builder/docs/locations
- SearchServiceClient & Filtering: https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
- Document Snippets: https://cloud.google.com/generative-ai-app-builder/docs/snippets
- Document-Level Security & ACL: https://cloud.google.com/generative-ai-app-builder/docs/document-level-access
"""

import logging
from typing import Optional, Any

from it_helpdesk_agent.tools.enterprise_rag_mcp.knowledge_store import (
    get_knowledge_store,
    KnowledgeStoreUnavailableError,
    wrap_retrieved_document,
)
from it_helpdesk_agent.app_utils.system_config import (
    get_configured_systems,
    get_valid_system_filters,
    get_system_required_roles,
)
from it_helpdesk_agent.app_utils.sso_auth import require_role

import os
import concurrent.futures

logger = logging.getLogger(__name__)


def _get_rag_top_k() -> int:
    """Retrieves and validates configured RAG_TOP_K (VAIS-052). Defaults to 8, bounded to [1, 100]."""
    raw = os.getenv("RAG_TOP_K", "8")
    try:
        val = int(raw)
        return max(1, min(100, val))
    except (ValueError, TypeError):
        return 8


def _get_rag_timeout_seconds() -> float:
    """Retrieves and validates configured RAG_SEARCH_TIMEOUT_SECONDS (VAIS-054). Defaults to 4.0s."""
    raw = os.getenv("RAG_SEARCH_TIMEOUT_SECONDS", "4.0")
    try:
        val = float(raw)
        return max(0.1, min(60.0, val))
    except (ValueError, TypeError):
        return 4.0


def _execute_with_timeout(func, *args, timeout_sec: float, **kwargs) -> Any:
    """Executes a callable with a strict timeout boundary. Returns (success, result, is_timeout)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            res = future.result(timeout=timeout_sec)
            return True, res, False
        except concurrent.futures.TimeoutError:
            return False, None, True
        except Exception as exc:
            return False, exc, False


def _check_system_access(system: str) -> tuple[bool, Optional[str]]:
    """
    Verifies if the current authenticated caller is authorized to access documentation for the specified system.
    Fails closed if SSO authorization layer cannot be resolved or credentials are absent.
    """
    sys_upper = system.upper().strip()
    if sys_upper == "ALL":
        return True, None

    needed_roles = get_system_required_roles(sys_upper)
    if not needed_roles:
        # Check if the system is known in configuration
        configured = get_configured_systems()
        if sys_upper not in configured:
            return False, f"Hệ thống '{system}' không được định nghĩa trong cấu hình doanh nghiệp (Fail-Closed)."
        return True, None

    return require_role(needed_roles)


def _get_authorized_systems() -> list[str]:
    """
    Returns the list of enterprise systems the current user is authorized to access.
    Dynamically resolves systems from configuration and user SSO context.
    """
    authorized = []
    for sys_name in get_configured_systems():
        allowed, _ = _check_system_access(sys_name)
        if allowed:
            authorized.append(sys_name)
    return authorized


def search_enterprise_knowledge(
    query: str,
    system: Optional[str] = "ALL"
) -> list[dict]:
    """
    Searches enterprise knowledge base for technical manuals and troubleshooting procedures.
    
    Args:
        query: Keyword or natural language question regarding an enterprise system issue.
        system: Optional target system identifier (e.g. 'ERP', 'HRM', 'CRM', or 'ALL' to search all authorized systems).
    
    Security & RBAC:
        Enforces domain-level RBAC authorization and Pre-Query Security Trimming server-side
        based on the authenticated SSO user's context. LLM cannot bypass or elevate permissions.
    """
    clean_sys = system.upper().strip() if system else "ALL"
    valid_systems = get_valid_system_filters()
    store = get_knowledge_store()
    top_k = _get_rag_top_k()
    timeout_sec = _get_rag_timeout_seconds()

    # Explicit input boundary validation
    if clean_sys not in valid_systems:
        valid_names = ", ".join(sorted(list(get_configured_systems())))
        return [{
            "article_id": "INVALID-SYSTEM",
            "title": f"Invalid System Specified: '{system}'",
            "snippet": f"Hệ thống '{system}' không hợp lệ. Các hệ thống được hỗ trợ bao gồm: {valid_names}, hoặc 'ALL'.",
            "system": system or "UNKNOWN",
            "score": 0.0,
            "is_truncated": False,
        }]

    if clean_sys != "ALL":
        is_allowed, error_msg = _check_system_access(clean_sys)
        if not is_allowed:
            return [{
                "article_id": f"{clean_sys}-FORBIDDEN",
                "title": f"Access Denied: Restricted {clean_sys} System Documentation",
                "snippet": error_msg or f"Truy cập tài liệu {clean_sys} bị từ chối do không đủ quyền hạn.",
                "system": clean_sys,
                "score": 0.0,
                "is_truncated": False,
            }]

        ok, res, timed_out = _execute_with_timeout(
            store.search,
            query=query,
            system=clean_sys,
            limit=top_k,
            timeout_sec=timeout_sec,
        )
        if timed_out:
            logger.error("RAG search timeout after %.2fs for query='%s', system='%s'", timeout_sec, query, clean_sys)
            return [{
                "article_id": "SEARCH-TIMEOUT",
                "title": "Hệ thống Tra cứu Tri thức Quá tải",
                "snippet": f"⚠️ [Hệ thống bận] Thời gian tra cứu tài liệu vượt quá giới hạn cho phép ({timeout_sec:.0f}s). Vui lòng thử lại với từ khóa ngắn gọn hơn hoặc liên hệ trực tiếp IT Support.",
                "system": clean_sys,
                "score": 0.0,
                "is_truncated": False,
            }]
        if not ok:
            logger.error("Knowledge store error during search: %s", res)
            return [{
                "article_id": "STORE-UNAVAILABLE",
                "title": "Dịch vụ Tra cứu Tri thức Tạm thời Gián đoạn",
                "snippet": "Cơ sở dữ liệu tri thức doanh nghiệp hiện không phản hồi. Vui lòng thử lại sau.",
                "system": clean_sys,
                "score": 0.0,
                "is_truncated": False,
            }]
        return [r.model_dump() for r in res]

    # Pre-query Security Trimming for system == "ALL":
    authorized_systems = _get_authorized_systems()
    if not authorized_systems:
        logger.info("No authorized systems for current user SSO context (Fail-Closed)")
        return []

    ok, res, timed_out = _execute_with_timeout(
        store.search,
        query=query,
        system="ALL",
        limit=top_k,
        allowed_systems=authorized_systems,
        timeout_sec=timeout_sec,
    )
    if timed_out:
        logger.error("RAG search ALL timeout after %.2fs for query='%s'", timeout_sec, query)
        return [{
            "article_id": "SEARCH-TIMEOUT",
            "title": "Hệ thống Tra cứu Tri thức Quá tải",
            "snippet": f"⚠️ [Hệ thống bận] Thời gian tra cứu tài liệu vượt quá giới hạn cho phép ({timeout_sec:.0f}s). Vui lòng thử lại với từ khóa ngắn gọn hơn hoặc liên hệ trực tiếp IT Support.",
            "system": "ALL",
            "score": 0.0,
            "is_truncated": False,
        }]
    if not ok:
        logger.error("Knowledge store error during search ALL: %s", res)
        return [{
            "article_id": "STORE-UNAVAILABLE",
            "title": "Dịch vụ Tra cứu Tri thức Tạm thời Gián đoạn",
            "snippet": "Cơ sở dữ liệu tri thức doanh nghiệp hiện không phản hồi. Vui lòng thử lại sau.",
            "system": "ALL",
            "score": 0.0,
            "is_truncated": False,
        }]
    return [r.model_dump() for r in res]


def get_system_manual(article_id: str) -> dict:
    """
    Retrieves the complete technical manual or troubleshooting guide for a specific article ID.
    
    Args:
        article_id: The unique identifier of the knowledge base article.
        
    Security & RBAC:
        Enforces domain-level RBAC for sensitive enterprise system operational guides.
        Wraps returned content in secure XML boundary tags to defend against Prompt Injection.
    """
    store = get_knowledge_store()
    timeout_sec = _get_rag_timeout_seconds()

    ok, res, timed_out = _execute_with_timeout(
        store.get_article_by_id,
        article_id,
        timeout_sec=timeout_sec,
    )
    if timed_out:
        logger.error("get_system_manual timeout after %.2fs for article_id='%s'", timeout_sec, article_id)
        return {
            "status": "error",
            "error_code": "SEARCH_TIMEOUT",
            "message": f"⚠️ [Hệ thống bận] Thời gian tải tài liệu '{article_id}' vượt quá giới hạn cho phép ({timeout_sec:.0f}s). Vui lòng thử lại sau.",
            "article_id": article_id,
        }
    if not ok:
        logger.error("Knowledge store error during get_system_manual: %s", res)
        return {
            "status": "error",
            "error_code": "KNOWLEDGE_STORE_UNAVAILABLE",
            "message": "Dịch vụ cơ sở dữ liệu tri thức tạm thời gián đoạn. Vui lòng thử lại sau.",
            "article_id": article_id
        }

    article = res
    if not article:
        return {"status": "error", "message": f"Article '{article_id}' not found."}
    
    is_allowed, error_msg = _check_system_access(article.system)
    if not is_allowed:
        return {
            "status": "forbidden",
            "error": "Access Denied",
            "message": error_msg or f"Truy cập tài liệu {article.system} bị từ chối do không đủ quyền hạn.",
            "article_id": article_id,
            "system": article.system,
        }

    art_dict = article.model_dump()
    raw_content = art_dict.get("content", "")
    art_dict["content"] = wrap_retrieved_document(
        content=raw_content,
        doc_id=article.id,
        system=article.system,
        title=article.title,
    )
    return {"status": "success", "article": art_dict}


def draft_email_response(
    user_name: str,
    ticket_id: str,
    issue_summary: str,
    solution_steps: str,
    urgency: str = "Normal"
) -> dict:
    """
    Drafts a standardized, polite, and professional email response to update the user regarding their ticket.
    """
    email_subject = f"[IT Helpdesk - {ticket_id}] Cập nhật xử lý: {issue_summary}"
    email_body = f"""Kính gửi Anh/Chị {user_name},

Bộ phận IT Helpdesk xin thông báo về tiến độ xử lý yêu cầu hỗ trợ của Anh/Chị:
- Mã Ticket: {ticket_id}
- Vấn đề ghi nhận: {issue_summary}
- Mức độ ưu tiên: {urgency}

--- HƯỚNG DẪN XỬ LÝ / KẾT QUẢ ---
{solution_steps}

Nếu Anh/Chị cần hỗ trợ thêm hoặc sự cố chưa được giải quyết triệt để, vui lòng phản hồi trực tiếp email này hoặc liên hệ hotline IT Helpdesk (Ext: 1080).

Trân trọng,
Đội ngũ IT Helpdesk & Enterprise Support
"""
    return {
        "status": "success",
        "subject": email_subject,
        "body": email_body
    }
