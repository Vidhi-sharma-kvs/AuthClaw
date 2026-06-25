from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from policy import check_policy_violations, enforce_policy


@dataclass
class PolicyAgentResult:
    approved: bool
    policy_decision: str
    violated_policies: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    category: str = ""


class PolicyAgent:
    def evaluate(self, text: str, username: str = "system", tenant_id: int = None) -> PolicyAgentResult:
        is_blocked, reason, category = enforce_policy(text)
        if is_blocked:
            return PolicyAgentResult(
                approved=False,
                policy_decision="block",
                reason=reason,
                category=category,
                violated_policies=[{
                    "policy_name": "Active Policy Enforcement",
                    "policy_type": category,
                    "matched_pattern": reason,
                    "redacted_value": "N/A",
                    "username": username,
                    "timestamp": datetime.now(),
                    "tenant_id": tenant_id,
                }],
            )

        allowed, triggered_blocks = check_policy_violations(text, tenant_id)
        for policy in triggered_blocks:
            policy["username"] = username
            policy["timestamp"] = datetime.now()
            policy["tenant_id"] = tenant_id

        return PolicyAgentResult(
            approved=allowed,
            policy_decision="allow" if allowed else "block",
            violated_policies=triggered_blocks,
        )
