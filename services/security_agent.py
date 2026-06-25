from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Tuple

from redaction import redact_sensitive_data_rich
from risk import calculate_risk
from services.response_inspection import ResponseInspectionService


@dataclass
class SecurityAgentResult:
    approved: bool
    risk_level: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    sanitized_text: str = ""


class SecurityAgent:
    secret_patterns = {
        "api_key": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16})\b"),
        "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE),
        "password_assignment": re.compile(r"\b(password|passwd|secret)\s*[:=]\s*\S+", re.IGNORECASE),
    }

    prompt_injection_terms = (
        "ignore previous instructions",
        "ignore all instructions",
        "reveal system prompt",
        "show internal system prompts",
        "disable audit",
        "disable logging",
        "bypass policies",
    )

    def inspect_input(self, text: str, username: str = "system", tenant_id=None) -> SecurityAgentResult:
        risk_level = calculate_risk(text)
        sanitized_text, triggered = redact_sensitive_data_rich(text, username, tenant_id)
        findings = list(triggered)

        lowered = text.lower()
        for term in self.prompt_injection_terms:
            if term in lowered:
                findings.append({
                    "policy_name": "Security Agent",
                    "policy_type": "prompt_injection",
                    "matched_pattern": term,
                    "redacted_value": "N/A",
                    "username": username,
                })

        for finding_type, pattern in self.secret_patterns.items():
            for match in pattern.finditer(text):
                findings.append({
                    "policy_name": "Security Agent",
                    "policy_type": finding_type,
                    "matched_pattern": finding_type,
                    "redacted_value": match.group(0),
                    "username": username,
                })
                sanitized_text = sanitized_text.replace(match.group(0), "[REDACTED_SECRET]")

        approved = not any(
            finding.get("policy_type") in {"prompt_injection", "api_key", "bearer_token", "password_assignment"}
            for finding in findings
        )
        return SecurityAgentResult(
            approved=approved,
            risk_level=risk_level,
            findings=findings,
            sanitized_text=sanitized_text,
        )

    def classify_risk(self, text: str) -> str:
        return calculate_risk(text)

    def sanitize_output(self, text: str, username: str = "system", tenant_id=None) -> Tuple[str, List[Dict[str, Any]]]:
        return ResponseInspectionService().inspect(text, username, tenant_id)
