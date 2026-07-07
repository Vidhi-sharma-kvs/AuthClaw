package authclaw.policy

default allow := true
default decision := "ALLOW"
default reason := "Allowed by AuthClaw OPA policy"

blocked_keywords := {
  "ignore all instructions",
  "reveal system prompt",
  "dump database",
  "disable logging",
}

high_risk_keywords := {
  "delete database",
  "drop table",
  "export customer data",
  "production database",
  "admin credentials",
}

normalized_text := lower(sprintf("%v", [input.text]))

body_text := lower(sprintf("%v", [input.context.body]))

combined_text := concat(" ", [normalized_text, body_text])

block if {
  some keyword in blocked_keywords
  contains(combined_text, keyword)
}

requires_approval if {
  some keyword in high_risk_keywords
  contains(combined_text, keyword)
}

allow := false if block
allow := false if requires_approval

decision := "BLOCK" if block
decision := "REQUIRE_APPROVAL" if {
  not block
  requires_approval
}

reason := "Blocked by OPA enterprise policy" if block
reason := "High-risk action requires approval" if {
  not block
  requires_approval
}

risk_level := "HIGH" if block
risk_level := "HIGH" if requires_approval
risk_level := "LOW" if {
  not block
  not requires_approval
}

findings contains finding if {
  some keyword in blocked_keywords
  contains(combined_text, keyword)
  finding := {
    "policy_name": "OPA blocked keyword",
    "category": "opa",
    "action": "BLOCK",
    "matched": keyword,
  }
}

findings contains finding if {
  some keyword in high_risk_keywords
  contains(combined_text, keyword)
  finding := {
    "policy_name": "OPA high risk keyword",
    "category": "opa",
    "action": "REQUIRE_APPROVAL",
    "matched": keyword,
  }
}
