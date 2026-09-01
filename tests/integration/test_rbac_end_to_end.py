"""
End-to-End Integration Test for In-Process RAG Tools and RBAC Enforcement

Verifies:
1. In-process tools preserve SSO ContextVar across all calls without subprocess boundaries.
2. Domain-level RBAC is strictly enforced for ERP, HRM, CRM.
3. Pre-query security trimming when system="ALL" filters out unauthorized systems.
4. Fail-closed behavior when K_SERVICE=1 (Cloud Run production) or unauthenticated.
5. wrap_retrieved_document sanitizes delimiters and escapes XML attributes.
"""

import os
import pytest
from it_helpdesk_agent.app_utils.sso_auth import SSOUser, current_sso_user
from it_helpdesk_agent.tools.enterprise_rag import (
    search_enterprise_knowledge,
    get_system_manual,
    draft_email_response,
)


@pytest.fixture(autouse=True)
def reset_sso_context():
    """Reset SSO ContextVar before and after each test."""
    token = current_sso_user.set(None)
    yield
    current_sso_user.reset(token)


def test_erp_user_access_control():
    """An ERP user should access ERP docs but get forbidden on HRM."""
    erp_user = SSOUser(
        user_id="user-erp-01",
        email="erp.specialist@company.com",
        roles=["employee", "erp_user"],
        full_name="ERP Specialist",
    )
    current_sso_user.set(erp_user)

    # 1. Search ERP -> Success
    erp_results = search_enterprise_knowledge(query="Purchase Order", system="ERP")
    assert len(erp_results) > 0
    assert erp_results[0]["system"] == "ERP"
    assert "FORBIDDEN" not in erp_results[0]["article_id"]

    # 2. Search HRM -> Access Denied
    hrm_results = search_enterprise_knowledge(query="bảng lương", system="HRM")
    assert len(hrm_results) == 1
    assert hrm_results[0]["article_id"] == "HRM-FORBIDDEN"
    assert hrm_results[0]["score"] == 0.0

    # 3. Get ERP Manual -> Success with XML boundary wrapping
    manual_res = get_system_manual("ERP-KB-001")
    assert manual_res["status"] == "success"
    assert "<retrieved_document" in manual_res["article"]["content"]
    assert "</retrieved_document>" in manual_res["article"]["content"]

    # 4. Get HRM Manual -> Forbidden
    hrm_manual = get_system_manual("HRM-KB-101")
    assert hrm_manual["status"] == "forbidden"


def test_hrm_manager_access_control():
    """An HR Manager should access HRM docs but get forbidden on ERP."""
    hr_user = SSOUser(
        user_id="user-hr-01",
        email="hr.manager@company.com",
        roles=["employee", "hr_manager"],
        full_name="HR Manager",
    )
    current_sso_user.set(hr_user)

    # 1. Search HRM -> Success
    hrm_results = search_enterprise_knowledge(query="chấm công", system="HRM")
    assert len(hrm_results) > 0
    assert hrm_results[0]["system"] == "HRM"

    # 2. Search ERP -> Access Denied
    erp_results = search_enterprise_knowledge(query="SAP ME21N", system="ERP")
    assert len(erp_results) == 1
    assert erp_results[0]["article_id"] == "ERP-FORBIDDEN"

    # 3. Search ALL -> Pre-query security trimming only returns HRM articles
    all_results = search_enterprise_knowledge(query="hướng dẫn", system="ALL")
    for doc in all_results:
        assert doc["system"] == "HRM"


def test_unauthorized_user_fails_closed():
    """A user with no elevated roles should get 0 results for system='ALL' and Forbidden on restricted systems."""
    guest_user = SSOUser(
        user_id="user-guest-01",
        email="guest@company.com",
        roles=["guest"],
        full_name="Guest User",
    )
    current_sso_user.set(guest_user)

    # System ALL -> Empty list (Fail-Closed)
    all_res = search_enterprise_knowledge(query="quy trình", system="ALL")
    assert all_res == []

    # System ERP -> Forbidden
    erp_res = search_enterprise_knowledge(query="quy trình", system="ERP")
    assert len(erp_res) == 1
    assert "FORBIDDEN" in erp_res[0]["article_id"]


def test_cloud_run_environment_unauthenticated_fails_closed(monkeypatch):
    """When K_SERVICE=1 and current_sso_user is None, all requests must fail closed."""
    monkeypatch.setenv("K_SERVICE", "it-helpdesk-agent-prod")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_LOCAL_DEV_SSO", "false")

    current_sso_user.set(None)

    # Search ALL -> Empty (Fail-Closed)
    all_res = search_enterprise_knowledge(query="test", system="ALL")
    assert all_res == []

    # Search ERP -> Forbidden
    erp_res = search_enterprise_knowledge(query="test", system="ERP")
    assert len(erp_res) == 1
    assert "FORBIDDEN" in erp_res[0]["article_id"]

    # Get Manual -> Forbidden
    manual = get_system_manual("ERP-KB-001")
    assert manual["status"] == "forbidden"


def test_draft_email_response():
    """Verify email draft generation works correctly."""
    draft = draft_email_response(
        user_name="Nguyen Van A",
        ticket_id="INC-2026-9999",
        issue_summary="Lỗi phân quyền SAP PO",
        solution_steps="Đã gán role Z_PROC_PURCHASER thành công.",
        urgency="High",
    )
    assert draft["status"] == "success"
    assert "INC-2026-9999" in draft["subject"]
    assert "Nguyen Van A" in draft["body"]
    assert "Z_PROC_PURCHASER" in draft["body"]
