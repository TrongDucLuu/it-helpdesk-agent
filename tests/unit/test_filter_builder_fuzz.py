"""
Unit and Fuzzing Tests for Discovery Engine Filter Builder (VAIS-022).

Validates strict RBAC whitelist enforcement and tests against >=20 malicious injection vectors:
- SQL & Boolean injection bypasses
- Syntax break-out characters (quotes, parens, delimiters)
- Unicode spoofing & unprintable bytes
- Type confusion & boundary conditions
"""

import pytest
from it_helpdesk_agent.tools.enterprise_rag.filter_builder import (
    build_system_filter,
    NO_ACCESS_FILTER,
    NO_ACCESS_SENTINEL,
)
from it_helpdesk_agent.app_utils.system_config import get_configured_systems


# List of 25 adversarial and boundary test payloads
ADVERSARIAL_INJECTION_PAYLOADS = [
    'ERP") OR (1=1',
    'ERP" OR system: ANY("HRM',
    'ERP,HRM',
    '*',
    'ANY("")',
    'ERP*',
    'ERP?',
    'ERP|HRM',
    'ERP\x00',
    'ERP\nOR\nsystem:ANY("HRM")',
    'ERP\r\n',
    'ERP"',
    "ERP'",
    'ERP`',
    'ERP; DROP TABLE knowledge_articles;',
    'ERP; rm -rf /',
    '%(system)s',
    '${system}',
    '<retrieved_document>ERP</retrieved_document>',
    '<system>ERP</system>',
    '\\u0415RP',  # Cyrillic Look-alike E
    'ＥＲＰ',       # Fullwidth Unicode
    '   ',         # Whitespace only
    'UNKNOWN_SYS_999',  # Unconfigured system
    'ALL',         # Reserved system name (not in configured systems)
]


def test_valid_allowed_systems_construction():
    """Verifies standard valid filter expressions."""
    res1 = build_system_filter(allowed_systems=["ERP"])
    assert res1 == 'system: ANY("ERP")'

    res2 = build_system_filter(allowed_systems=["ERP", "HRM"])
    assert res2 == 'system: ANY("ERP", "HRM")'

    # Case insensitive normalization
    res3 = build_system_filter(allowed_systems=["erp", "hrm", "crm"])
    assert res3 == 'system: ANY("CRM", "ERP", "HRM")'


def test_empty_and_none_allowed_systems_fails_closed():
    """Empty or None allowed_systems MUST return NO_ACCESS_FILTER, never empty string."""
    assert build_system_filter([]) == NO_ACCESS_FILTER
    assert build_system_filter(None) == NO_ACCESS_FILTER
    assert build_system_filter("") == NO_ACCESS_FILTER
    assert NO_ACCESS_SENTINEL in build_system_filter([])
    assert build_system_filter([]) != ""


def test_target_system_authorization_and_idor_protection():
    """Verifies that requesting a target system outside allowed_systems fails closed."""
    # User has ERP access, queries ERP -> allowed
    assert build_system_filter(allowed_systems=["ERP", "HRM"], target_system="ERP") == 'system: ANY("ERP")'

    # User only has HRM access, queries ERP -> blocked (Fail-Closed)
    res = build_system_filter(allowed_systems=["HRM"], target_system="ERP")
    assert res == NO_ACCESS_FILTER

    # User queries unconfigured target system -> blocked
    res_unconf = build_system_filter(allowed_systems=["HRM"], target_system="SAP_TEST")
    assert res_unconf == NO_ACCESS_FILTER


@pytest.mark.parametrize("payload", ADVERSARIAL_INJECTION_PAYLOADS)
def test_adversarial_injection_payloads_rejected(payload):
    """
    Fuzz test: Injects malicious strings into allowed_systems.
    None of these payloads must appear in the final filter or cause syntax escape.
    """
    # 1. Payload as sole allowed_systems item -> Must return NO_ACCESS_FILTER
    result_sole = build_system_filter(allowed_systems=[payload])
    assert result_sole == NO_ACCESS_FILTER, f"Payload {payload!r} was not completely rejected!"

    # 2. Payload mixed with valid system -> Valid system preserved, payload discarded
    result_mixed = build_system_filter(allowed_systems=["ERP", payload])
    assert result_mixed == 'system: ANY("ERP")', f"Payload {payload!r} corrupted mixed filter: {result_mixed}"

    # 3. Payload as target_system -> Must return NO_ACCESS_FILTER (unless target_system is the 'ALL' wildcard)
    if payload != "ALL":
        result_target = build_system_filter(allowed_systems=["ERP", "HRM"], target_system=payload)
        assert result_target == NO_ACCESS_FILTER, f"Payload {payload!r} as target_system was not rejected!"
    else:
        # 'ALL' as target_system queries all authorized systems
        assert build_system_filter(allowed_systems=["ERP", "HRM"], target_system="ALL") == 'system: ANY("ERP", "HRM")'


def test_type_confusion_payloads():
    """Verifies handling of non-string and complex objects in allowed_systems."""
    weird_types = [
        123,
        45.67,
        True,
        False,
        {"sys": "ERP"},
        ["ERP"],
        object(),
        b"ERP",
    ]
    result = build_system_filter(allowed_systems=weird_types)
    assert result == NO_ACCESS_FILTER


def test_custom_field_name_filter():
    """Verifies custom field name (e.g. structData.system)."""
    res = build_system_filter(allowed_systems=["ERP"], field_name="structData.system")
    assert res == 'structData.system: ANY("ERP")'
