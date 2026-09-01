"""
Discovery Engine / Vertex AI Search Filter Expression Builder.

Constructs secure, sanitized metadata filter expressions for Discovery Engine (Agent Search).
Guarantees Fail-Closed RBAC: strictly whitelists system names against configured enterprise systems
and blocks all SQL/Boolean/Delimiter injection vectors.

Google Cloud Official Documentation:
- Filter search results by metadata:
  https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
- SearchServiceClient reference:
  https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.services.search_service.SearchServiceClient
"""

import re
import logging
from typing import Optional, Any

try:
    from it_helpdesk_agent.app_utils.system_config import get_configured_systems
except ImportError:
    try:
        from app_utils.system_config import get_configured_systems
    except ImportError:
        def get_configured_systems() -> list[str]:
            return ["ERP", "HRM", "CRM"]

logger = logging.getLogger(__name__)

# Constant sentinel for fail-closed zero-result queries
NO_ACCESS_SENTINEL = "__NO_SYSTEM_ACCESS__"
NO_ACCESS_FILTER = f'system: ANY("{NO_ACCESS_SENTINEL}")'

# Strict regex for valid system identifiers
SYSTEM_TOKEN_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")


def build_system_filter(
    allowed_systems: Optional[list[Any]],
    target_system: Optional[str] = "ALL",
    field_name: str = "system",
) -> str:
    """
    Builds a secure, injection-proof metadata filter expression for Discovery Engine.

    Parameters:
        allowed_systems: List of system names the authenticated user is authorized to access.
        target_system: Optional specific system filter requested (e.g. 'ERP', 'HRM', 'ALL').
        field_name: Metadata field name to filter on (default 'system').

    Returns:
        A sanitized filter expression string like 'system: ANY("ERP", "HRM")'
        or 'system: ANY("__NO_SYSTEM_ACCESS__")' if no systems are authorized (Fail-Closed).

    Security Invariants:
        1. Pure whitelist: Only system names present in get_configured_systems() are accepted.
        2. Any injection characters (quotes, parens, OR, AND, wildcards, unprintable chars) cause
           the candidate token to be rejected.
        3. If allowed_systems is empty or None, returns NO_ACCESS_FILTER (never empty string "").
        4. If target_system is not in allowed_systems, returns NO_ACCESS_FILTER (IDOR protection).
    """
    configured_systems = set(s.upper().strip() for s in get_configured_systems())

    # 1. Validate & sanitize allowed_systems against whitelist
    if not allowed_systems or not isinstance(allowed_systems, (list, tuple, set)):
        logger.debug("allowed_systems is empty or invalid type (%s). Returning fail-closed filter.", type(allowed_systems))
        return NO_ACCESS_FILTER

    valid_allowed: set[str] = set()
    for item in allowed_systems:
        if not isinstance(item, str):
            continue
        # Strict validation: reject any item with whitespace, control characters, or non-token format
        if not SYSTEM_TOKEN_REGEX.match(item):
            logger.warning("Rejected non-token or dirty system string in allowed_systems: %r", item)
            continue
        cleaned = item.upper()
        if cleaned in configured_systems:
            valid_allowed.add(cleaned)
        else:
            logger.warning("Rejected unconfigured system token in allowed_systems: %r", item)

    if not valid_allowed:
        logger.info("No valid configured systems in allowed_systems after sanitization. Returning fail-closed filter.")
        return NO_ACCESS_FILTER

    # 2. Reconcile with target_system (Intersection)
    target_raw = target_system if target_system is not None else "ALL"
    if not isinstance(target_raw, str):
        logger.warning("Invalid target_system type: %s", type(target_raw))
        return NO_ACCESS_FILTER

    clean_target = target_raw.upper()
    
    if clean_target != "ALL":
        if not SYSTEM_TOKEN_REGEX.match(target_raw):
            logger.warning("Rejected dirty or non-token target_system: %r", target_raw)
            return NO_ACCESS_FILTER
        if clean_target in valid_allowed:
            final_systems = [clean_target]
        else:
            # User attempted to query a system they lack authorization for -> fail closed
            logger.info("Target system %r is not in user's authorized systems %s. Blocking access.", clean_target, valid_allowed)
            return NO_ACCESS_FILTER
    else:
        final_systems = sorted(list(valid_allowed))

    if not final_systems:
        return NO_ACCESS_FILTER

    # 3. Construct Discovery Engine filter expression
    # Syntax: system: ANY("SYS1", "SYS2")
    formatted_tokens = ", ".join(f'"{s}"' for s in final_systems)
    return f"{field_name}: ANY({formatted_tokens})"
