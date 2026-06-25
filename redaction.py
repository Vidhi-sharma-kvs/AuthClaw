import re
import hashlib
from policy import get_policy

def apply_redaction(field: str, match, action: str) -> str:
    """
    Applies the configured redaction action (mask, hash, synthetic, or standard redact fallback)
    on a matched sensitive token.
    """
    val = match.group(0)
    action_lower = action.lower()
    
    if action_lower == "mask":
        if field == "email":
            if "@" in val:
                local, domain = val.split("@", 1)
                if len(local) > 2:
                    return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"
                return f"{'*' * len(local)}@{domain}"
            return "***"
        elif field == "phone":
            return "*" * 6 + val[-4:]
        elif field in ("aadhaar", "credit_card"):
            # Mask digits except last 4, preserving delimiters
            digits = [c for c in val if c.isdigit()]
            total_digits = len(digits)
            masked = []
            digit_count = 0
            for c in val:
                if c.isdigit():
                    if digit_count < total_digits - 4:
                        masked.append("*")
                        digit_count += 1
                    else:
                        masked.append(c)
                else:
                    masked.append(c)
            return "".join(masked)
            
    elif action_lower == "hash":
        h = hashlib.sha256(val.encode("utf-8")).hexdigest()[:16]
        return f"[HASH_{h}]"
        
    elif action_lower == "synthetic":
        if field == "email":
            return "synthetic.email@example.com"
        elif field == "phone":
            return "555-019-9283"
        elif field == "aadhaar":
            return "0000 0000 0000"
        elif field == "credit_card":
            return "4111-1111-1111-1111"
            
    # Fallback / Default ("redact" or other invalid configuration)
    if field == "email":
        return "[REDACTED_EMAIL]"
    elif field == "phone":
        return "[REDACTED_PHONE]"
    elif field == "aadhaar":
        return "[REDACTED_AADHAAR]"
    elif field == "credit_card":
        return "[REDACTED_CARD]"
    return val

def redact_sensitive_data_rich(text: str, username: str = "admin_user", tenant_id=None) -> tuple:
    """
    Identifies sensitive fields based on active database guardrail policies
    and applies [REDACTED] replacement. Also checks baseline yaml redactions.
    Returns (redacted_text, triggered_policies).
    """
    import re
    import os
    from datetime import datetime
    from policy import get_db_policies

    triggered_policies = []

    def record_baseline_trigger(policy_name: str, field: str, value: str):
        triggered_policies.append({
            "policy_name": policy_name,
            "policy_type": "Security",
            "matched_pattern": field,
            "redacted_value": value,
            "username": username,
            "timestamp": datetime.now()
        })
    
    # 1. Fetch active policies from the database
    db_policies = get_db_policies(tenant_id)
    active_types = {p["type"]: p for p in db_policies}

    # GDPR compliance check (Passport, SSN)
    if "GDPR" in active_types:
        gdpr_p = active_types["GDPR"]
        rules = gdpr_p.get("rules", {})
        if rules.get("pii_redaction", False):
            # SSN Pattern (with dashes 123-45-6789 or raw 9 digits)
            ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
            for m in re.finditer(ssn_pattern, text):
                val = m.group(0)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": gdpr_p["name"],
                        "policy_type": "GDPR",
                        "matched_pattern": "ssn",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(ssn_pattern, "[REDACTED]", text)

            # Raw 9 digit SSN
            ssn_raw_pattern = r"\b\d{9}\b"
            for m in re.finditer(ssn_raw_pattern, text):
                val = m.group(0)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": gdpr_p["name"],
                        "policy_type": "GDPR",
                        "matched_pattern": "ssn",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(ssn_raw_pattern, "[REDACTED]", text)

            # Passport Pattern (e.g. A1234567, P12345678, or generic 1-2 letters + 7-9 digits)
            passport_pattern = r"\b[A-Za-z]{1,2}\d{7,9}\b"
            for m in re.finditer(passport_pattern, text):
                val = m.group(0)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": gdpr_p["name"],
                        "policy_type": "GDPR",
                        "matched_pattern": "passport",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(passport_pattern, "[REDACTED]", text)

            # Keyword-based backup check (e.g. passport number A1234567)
            kw_pattern = r"\b(passport|ssn|social security number)(\s+(?:number|no|code|is|of|:)?\s*)([A-Za-z0-9_-]+)\b"
            for m in re.finditer(kw_pattern, text, flags=re.IGNORECASE):
                val = m.group(3)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": gdpr_p["name"],
                        "policy_type": "GDPR",
                        "matched_pattern": m.group(1),
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(kw_pattern, r"\1\2[REDACTED]", text, flags=re.IGNORECASE)

    # HIPAA compliance check (medical record, diagnosis, health history, patient identifiers)
    if "HIPAA" in active_types:
        hipaa_p = active_types["HIPAA"]
        rules = hipaa_p.get("rules", {})
        if rules.get("pii_redaction", False):
            # Medical Record ID pattern (MR-12345, EMR-45678, Patient IDs like PT-12345 or PID-12345)
            mr_pattern = r"\b(?:MR|EMR|PT|PID|PATIENT|PATIENTID)[- ]?\d{4,8}\b"
            for m in re.finditer(mr_pattern, text, flags=re.IGNORECASE):
                val = m.group(0)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": hipaa_p["name"],
                        "policy_type": "HIPAA",
                        "matched_pattern": "medical record",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(mr_pattern, "[REDACTED]", text, flags=re.IGNORECASE)

            # Keyword-context match (medical record 98765, diagnosis is diabetes, health history includes asthma)
            hipaa_pattern = r"\b(medical record|diagnosis|diagnoses|health history|patient identifier|patient identifiers)(\s+(?:number|no|code|is|of|includes|:)?\s*)([A-Za-z0-9_-]+)\b"
            for m in re.finditer(hipaa_pattern, text, flags=re.IGNORECASE):
                val = m.group(3)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": hipaa_p["name"],
                        "policy_type": "HIPAA",
                        "matched_pattern": m.group(1),
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(hipaa_pattern, r"\1\2[REDACTED]", text, flags=re.IGNORECASE)

    # SOC2 compliance check (credit card, bank routing, pin number)
    if "SOC2" in active_types:
        soc2_p = active_types["SOC2"]
        rules = soc2_p.get("rules", {})
        if rules.get("pii_redaction", False):
            # Card-brand specific credit card check
            # Visa, Mastercard, Amex, Discover pattern matching
            cc_regex = r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6(?:011|5\d{2}|4[4-9]\d{1})\d{12})\b"
            for m in re.finditer(cc_regex, text):
                val = m.group(0)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": soc2_p["name"],
                        "policy_type": "SOC2",
                        "matched_pattern": "credit card",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(cc_regex, "[REDACTED]", text)

            # Standard Credit Card Pattern (with dashes/spaces)
            cc_pattern1 = r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"
            for m in re.finditer(cc_pattern1, text):
                val = m.group(0)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": soc2_p["name"],
                        "policy_type": "SOC2",
                        "matched_pattern": "credit card",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(cc_pattern1, "[REDACTED]", text)

            cc_pattern2 = r"\b\d{13,19}\b"
            for m in re.finditer(cc_pattern2, text):
                val = m.group(0)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": soc2_p["name"],
                        "policy_type": "SOC2",
                        "matched_pattern": "credit card",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(cc_pattern2, "[REDACTED]", text)

            # Bank routing: 9 digit ABA routing number
            routing_pattern = r"\b\d{9}\b"
            for m in re.finditer(routing_pattern, text):
                val = m.group(0)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": soc2_p["name"],
                        "policy_type": "SOC2",
                        "matched_pattern": "bank routing",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(routing_pattern, "[REDACTED]", text)

            # Keyword-context match for Bank routing and PIN numbers
            soc2_pattern = r"\b(bank routing|routing number|pin|pin number|personal identification number)(\s+(?:number|no|code|is|of|includes|:)?\s*)([A-Za-z0-9_-]+)\b"
            for m in re.finditer(soc2_pattern, text, flags=re.IGNORECASE):
                val = m.group(3)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": soc2_p["name"],
                        "policy_type": "SOC2",
                        "matched_pattern": m.group(1),
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(soc2_pattern, r"\1\2[REDACTED]", text, flags=re.IGNORECASE)

            # PIN Numbers: 4-6 digit financial PINs when preceded or near PIN keywords
            pin_near_pattern = r"\b(?:pin|pin number|personal identification number)\b.{1,15}\b(\d{4,6})\b"
            for m in re.finditer(pin_near_pattern, text, flags=re.IGNORECASE):
                val = m.group(1)
                if val != "[REDACTED]":
                    triggered_policies.append({
                        "policy_name": soc2_p["name"],
                        "policy_type": "SOC2",
                        "matched_pattern": "pin number",
                        "redacted_value": val,
                        "username": username,
                        "timestamp": datetime.now()
                    })
            text = re.sub(
                pin_near_pattern,
                lambda m: m.group(0).replace(m.group(1), "[REDACTED]"),
                text,
                flags=re.IGNORECASE
            )

    # ── API KEY / SECRET TOKEN DETECTION (always active, baseline security) ──────
    # Detects: OpenAI keys, Gemini keys, AWS keys, JWTs, Bearer tokens,
    #          and generic api_key=/secret=/token= patterns.
    import os as _os
    from datetime import datetime as _dt

    _api_key_patterns = [
        # OpenAI / generic sk- keys:  sk-prod-xxxxx, sk-xxxx
        (r"\bsk-[A-Za-z0-9\-_]{8,}\b",                           "openai_api_key"),
        # Google / Gemini:  AIzaSyXXX...
        (r"\bAIza[A-Za-z0-9\-_]{20,}\b",                         "google_api_key"),
        # AWS Access Key ID:  AKIA..., ASIA..., AROA...
        (r"\b(?:AKIA|ASIA|AROA|ANPA)[A-Z0-9]{16}\b",             "aws_access_key"),
        # JWT tokens:  eyJhbGci...
        (r"\beyJ[A-Za-z0-9\-_=]{20,}\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\b", "jwt_token"),
        # Bearer tokens in text:  Bearer <token>
        (r"\bBearer\s+[A-Za-z0-9\-_.~+/]{8,}={0,2}\b",           "bearer_token"),
        # Generic api_key=VALUE or api-key=VALUE (URL / query string / code)
        (r"(?i)\bapi[_\-]?key\s*[=:]\s*['\"]?([A-Za-z0-9\-_./+]{8,})['\"]?", "api_key_param"),
        # Generic secret=VALUE
        (r"(?i)\bsecret\s*[=:]\s*['\"]?([A-Za-z0-9\-_./+]{8,})['\"]?",        "secret_param"),
        # Generic token=VALUE
        (r"(?i)\btoken\s*[=:]\s*['\"]?([A-Za-z0-9\-_./+]{8,})['\"]?",         "token_param"),
        # Generic access_token=VALUE
        (r"(?i)\baccess[_\-]token\s*[=:]\s*['\"]?([A-Za-z0-9\-_./+]{8,})['\"]?", "access_token"),
        # Generic private_key / private-key
        (r"(?i)\bprivate[_\-]?key\s*[=:]\s*['\"]?([A-Za-z0-9\-_./+]{8,})['\"]?", "private_key"),
    ]

    for pattern, key_type in _api_key_patterns:
        for m in re.finditer(pattern, text):
            val = m.group(0)
            if "[REDACTED" not in val:
                triggered_policies.append({
                    "policy_name": "API Key Detection",
                    "policy_type": "Security",
                    "matched_pattern": key_type,
                    "redacted_value": val[:30] + ("..." if len(val) > 30 else ""),
                    "username": username,
                    "timestamp": _dt.now()
                })
        # Replace full match with redaction label
        text = re.sub(pattern, "[REDACTED_API_KEY]", text)

    # ─────────────────────────────────────────────────────────────────────────────

    # 2. Check baseline yaml redactions
    try:
        policy = get_policy()
        redaction_rules = policy.get("redaction", {})
    except Exception:
        redaction_rules = {}

    # Email
    email_action = redaction_rules.get("email", "redact")
    email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
    for m in re.finditer(email_pattern, text):
        if "[REDACTED" not in m.group(0):
            record_baseline_trigger("PII Protection", "email", m.group(0))
    text = re.sub(
        email_pattern,
        lambda m: apply_redaction("email", m, email_action),
        text
    )

    # Aadhaar
    aadhaar_action = redaction_rules.get("aadhaar", "redact")
    aadhaar_pattern = r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
    for m in re.finditer(aadhaar_pattern, text):
        if "[REDACTED" not in m.group(0):
            record_baseline_trigger("PII Protection", "aadhaar", m.group(0))
    text = re.sub(
        aadhaar_pattern,
        lambda m: apply_redaction("aadhaar", m, aadhaar_action),
        text
    )

    # Phone
    phone_action = redaction_rules.get("phone", "redact")
    phone_pattern = r"\b\d{10}\b"
    for m in re.finditer(phone_pattern, text):
        if "[REDACTED" not in m.group(0):
            record_baseline_trigger("PII Protection", "phone", m.group(0))
    text = re.sub(
        phone_pattern,
        lambda m: apply_redaction("phone", m, phone_action),
        text
    )

    # Standardize all target redactions to [REDACTED] for triggered compliance fields
    if triggered_policies:
        # Save to /logs/audit.log and print to console
        os.makedirs("logs", exist_ok=True)
        log_file = os.path.join("logs", "audit.log")
        with open(log_file, "a", encoding="utf-8") as f:
            for trigger in triggered_policies:
                log_msg = f"Time: {trigger['timestamp']} | Policy: {trigger['policy_name']} ({trigger['policy_type']}) | Matched: {trigger['matched_pattern']} | Redacted: {trigger['redacted_value']} | User: {trigger['username']}"
                print(f"[POLICY TRIGGERED] {log_msg}", flush=True)
                f.write(f"\n[POLICY TRIGGERED] {log_msg}\n")

    return text, triggered_policies

def redact_sensitive_data(text: str) -> str:
    """
    Identifies sensitive fields (Credit Card, Aadhaar, Email, Phone) and applies
    configured redaction strategies defined in the policy.
    """
    redacted_text, _ = redact_sensitive_data_rich(text)
    return redacted_text
