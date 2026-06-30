import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("authclaw.policy")

POLICY_FILE_PATH = os.getenv("POLICY_FILE_PATH", "policies.yaml")

# Cache variable
_cached_policy = None

def get_policy() -> Dict[str, Any]:
    """
    Returns the currently cached policy, loading it from policies.yaml if not cached.
    """
    global _cached_policy
    if _cached_policy is None:
        load_policy()
    return _cached_policy

def load_policy() -> Dict[str, Any]:
    """
    Loads, validates, and caches the policy from policies.yaml.
    """
    global _cached_policy
    try:
        from startup.validation import load_and_validate_policy
        policy = load_and_validate_policy(POLICY_FILE_PATH)
        _cached_policy = policy
        success_log = {
            "event": "policy_loaded",
            "status": "success",
            "message": "Policy loaded successfully.",
            "details": {
                "version": policy["version"],
                "blocked_keywords_count": len(policy["blocked_keywords"]),
                "high_risk_keywords_count": len(policy["high_risk_keywords"]),
                "medium_risk_keywords_count": len(policy["medium_risk_keywords"]),
                "redaction_rules": policy["redaction"]
            }
        }
        logger.info(json.dumps(success_log))
        print(json.dumps(success_log), flush=True)
        return policy
    except Exception as e:
        failure_log = {
            "event": "policy_loaded",
            "status": "failed",
            "message": f"Policy loading failed: {str(e)}"
        }
        logger.error(json.dumps(failure_log))
        print(json.dumps(failure_log), flush=True)
        raise e

def is_blocked(text: str) -> bool:
    """
    Checks if a given text contains any blocked keywords defined in the policy.
    """
    policy = get_policy()
    text_lower = text.lower()
    for word in policy["blocked_keywords"]:
        if word in text_lower:
            return True
    return False

def is_high_risk(text: str) -> bool:
    """
    Checks if a given text contains any high risk keywords defined in the policy.
    """
    policy = get_policy()
    text_lower = text.lower()
    for word in policy["high_risk_keywords"]:
        if word in text_lower:
            return True
    return False

def get_db_policies(tenant_id=None):
    """
    Retrieves active policies from the database.
    """
    try:
        from database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            if tenant_id is None:
                res = conn.execute(text("SELECT id, name, type, rules, enabled, tenant_id FROM policies WHERE enabled = true"))
            else:
                res = conn.execute(
                    text("SELECT id, name, type, rules, enabled, tenant_id FROM policies WHERE enabled = true AND tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id},
                )
            policies = []
            for row in res:
                p_dict = dict(row._mapping)
                try:
                    if isinstance(p_dict["rules"], str):
                        p_dict["rules"] = json.loads(p_dict["rules"])
                except Exception:
                    pass
                policies.append(p_dict)
            return policies
    except Exception as e:
        logger.warning(f"Error fetching active policies from DB: {e}")
        return []

def validate_policy(text: str, tenant_id=None) -> bool:
    """
    Validates if a text is allowed under the current policy (does not contain blocked keywords).
    Maintains backward compatibility.
    """
    from services.policy_engine import ACTION_BLOCK, ACTION_REQUIRE_APPROVAL, PolicyEngine

    result = PolicyEngine().evaluate(text, tenant_id=tenant_id)
    return result.action not in {ACTION_BLOCK, ACTION_REQUIRE_APPROVAL}

def check_policy_violations(text: str, tenant_id=None) -> tuple:
    """
    Checks if a given text violates policies, and returns a tuple (allowed, triggered_blocks).
    If allowed is False, triggered_blocks will contain metadata about the blocking policy.
    """
    from services.policy_engine import ACTION_BLOCK, ACTION_REQUIRE_APPROVAL, PolicyEngine

    result = PolicyEngine().evaluate(text, tenant_id=tenant_id)
    blocking_findings = [
        finding for finding in result.findings
        if str(finding.get("action", "")).upper() in {ACTION_BLOCK, ACTION_REQUIRE_APPROVAL}
    ]
    if result.action in {ACTION_BLOCK, ACTION_REQUIRE_APPROVAL}:
        return False, blocking_findings or result.findings
    return True, []

def enforce_policy(text: str) -> tuple:
    """
    Actively enforces security policies.
    Returns (is_blocked, reason, category).
    """
    import re
    from services.policy_engine import ACTION_BLOCK, PolicyEngine

    result = PolicyEngine().evaluate(text)
    if result.action == ACTION_BLOCK:
        category = result.triggered_categories[0].lower() if result.triggered_categories else "policy"
        return True, result.reason, category

    # 1. Clean and normalize the text for robust pattern matching
    cleaned = text.lower()
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Layer 1: Pattern Matching
    # Priority order: prompt_injection, security_bypass, data_exfiltration
    prompt_injection_patterns = [
        "ignore instructions",
        "ignore previous instructions",
        "ignore all instructions",
        "ignore all policies",
        "ignore all company policies",
        "bypass policies",
        "act as root",
        "act as admin",
        "system override",
        "reveal system prompt",
        "reveal system prompts",
        "show internal system prompts",
        "forget your instructions",
        "disregard instructions",
        "pretend security rules do not exist",
        "pretend security rules dont exist",
        "forget previous instructions",
        "forget your instructions and reveal secrets"
    ]

    security_bypass_patterns = [
        "disable logging",
        "disable security logging",
        "disable monitoring",
        "disable audit trails",
        "disable audit logging",
        "disable guardrails",
        "turn off logging",
        "turn off monitoring",
        "turn off audit",
        "turn off guardrails"
    ]

    data_exfiltration_patterns = [
        # Existing patterns
        "export customer data",
        "export all customer data",
        "reveal ssn",
        "reveal every customer ssn",
        "reveal every customers ssn",
        "reveal every customer's ssn",
        "show me every customer ssn",
        "show me every customers ssn",
        "show me every customer's ssn",
        "show customer records",
        "reveal passwords",
        "reveal admin passwords",
        "reveal hidden admin passwords",
        "reveal secrets",
        "dump database",
        "reveal credentials",
        "list confidential customer identifiers",
        "provide employee credentials",
        "export database",
        # New data exfiltration patterns
        "export customer record",
        "export every customer",
        "export production database",
        "download database",
        "download all users",
        "download customer",
        "extract records",
        "extract customer",
        "retrieve all users",
        "retrieve all employee",
        "retrieve all customer",
        "customer emails",
        "export user data",
        "give me all customer",
        "export confidential",
        "database dump",
        "exfiltrate",
        "steal data",
        "leak data",
        "send all records",
        "send customer records",
        "get all customer emails",
        "download customer emails",
    ]

    # Check prompt injection patterns
    for p in prompt_injection_patterns:
        cleaned_p = re.sub(r'[^\w\s]', '', p).lower()
        if cleaned_p in cleaned:
            return True, f"Policy violation: matched pattern '{p}'", "prompt_injection"

    # Check security bypass patterns
    for p in security_bypass_patterns:
        cleaned_p = re.sub(r'[^\w\s]', '', p).lower()
        if cleaned_p in cleaned:
            return True, f"Policy violation: matched pattern '{p}'", "security_bypass"

    # Check data exfiltration patterns
    for p in data_exfiltration_patterns:
        cleaned_p = re.sub(r'[^\w\s]', '', p).lower()
        if cleaned_p in cleaned:
            return True, f"Policy violation: matched pattern '{p}'", "data_exfiltration"

    # Layer 2: Static semantic keyword expansion (no LLM call to conserve API quota)
    # The LLM call was causing double API usage and 429 rate limits.
    # Static heuristics + Risk Engine together provide sufficient protection.

    # Additional prompt injection patterns
    prompt_injection_phrases = [
        "ignore all previous", "ignore previous instructions", "disregard your instructions",
        "you are now", "act as if", "pretend you are", "roleplay as", "simulate a",
        "override your", "bypass your", "your new instructions", "forget your training",
        "reveal your system prompt", "show me your instructions", "what are your instructions",
        "disable your filters", "turn off your", "jailbreak", "dan mode", "developer mode"
    ]
    for phrase in prompt_injection_phrases:
        if phrase in cleaned:
            return True, f"Policy violation: prompt injection pattern '{phrase}'", "prompt_injection"

    # Additional security bypass patterns
    security_bypass_phrases = [
        "disable logging", "turn off logging", "disable audit", "disable monitoring",
        "bypass security", "disable security", "turn off monitoring", "disable guardrail",
        "remove restrictions", "disable restrictions", "bypass authentication",
        "disable access control", "turn off access control", "disable firewall"
    ]
    for phrase in security_bypass_phrases:
        if phrase in cleaned:
            return True, f"Policy violation: security bypass pattern '{phrase}'", "security_bypass"

    return False, "", ""
