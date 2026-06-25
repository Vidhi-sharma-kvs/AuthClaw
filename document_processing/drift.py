import os
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import text
from database import engine

logger = logging.getLogger("authclaw.document_processing.drift")

def get_current_framework_scores() -> dict:
    """
    Computes live compliance scores (0-100) for each framework based on current database findings.
    """
    scores = {"SOC2": 100, "GDPR": 100, "HIPAA": 100, "PCI-DSS": 100, "ISO27001": 100}
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                SELECT df.finding_type, df.matched_pattern, df.risk_level 
                FROM document_findings df
                JOIN documents d ON df.document_id = d.id
                WHERE d.status NOT IN ('deleted', 's3_deleted')
                """)
            ).fetchall()
            
        for row in rows:
            ftype, pattern, risk = row[0], row[1], row[2]
            rl = risk.upper()
            penalty = 3
            if rl == "CRITICAL":
                penalty = 20
            elif rl == "HIGH":
                penalty = 15
            elif rl == "MEDIUM":
                penalty = 8
                
            # Map findings to frameworks by checking substrings in pattern name
            pat_upper = pattern.upper()
            matched_any = False
            for framework in scores.keys():
                if framework in pat_upper:
                    scores[framework] -= penalty
                    matched_any = True
                    
            # If it's a general secret or credential leak, it affects all security frameworks!
            if ftype in ("Secret", "Credentials") and not matched_any:
                for framework in scores.keys():
                    scores[framework] -= penalty
    except Exception as e:
        logger.error(f"Failed to calculate live framework scores: {e}")

    # Keep bounds between 20 and 100
    for fw in scores:
        scores[fw] = max(20, min(100, scores[fw]))
        
    return scores

def record_compliance_snapshot():
    """
    Saves a compliance score snapshot for each framework and checks for score drift.
    """
    timestamp = datetime.now(timezone.utc)
    scores = get_current_framework_scores()
    
    try:
        with engine.connect() as conn:
            for framework, score in scores.items():
                # 1. Fetch previous score for the framework to calculate drift
                prev = conn.execute(
                    text("""
                    SELECT score FROM compliance_score_history 
                    WHERE framework = :fw 
                    ORDER BY id DESC LIMIT 1
                    """),
                    {"fw": framework}
                ).fetchone()
                
                # Save the new snapshot
                conn.execute(
                    text("""
                    INSERT INTO compliance_score_history (timestamp, framework, score, details)
                    VALUES (:ts, :fw, :score, :details)
                    """),
                    {
                        "ts": timestamp,
                        "fw": framework,
                        "score": score,
                        "details": f"Snapshot score is {score}%"
                    }
                )
                
                if prev:
                    prev_score = prev[0]
                    score_drop = prev_score - score
                    
                    if score_drop > 5:
                        # Drift detected! Log drift alert.
                        logger.warning(f"Compliance Drift Detected! {framework} dropped by {score_drop} points.")
                        
                        conn.execute(
                            text("""
                            INSERT INTO compliance_drift_alerts 
                            (timestamp, framework, score_drop, previous_score, current_score, details)
                            VALUES (:ts, :fw, :drop, :prev, :curr, :details)
                            """),
                            {
                                "ts": timestamp,
                                "fw": framework,
                                "drop": score_drop,
                                "prev": prev_score,
                                "curr": score,
                                "details": f"Framework score dropped from {prev_score}% to {score}% due to new scan findings."
                            }
                        )
                        
                        # Write to cryptographic audit logs
                        from document_processing.auditor import create_document_audit
                        # We use 0 as virtual doc_id representing the system compliance status
                        create_document_audit(
                            0, 
                            "compliance_drift", 
                            "system", 
                            f"Compliance drift detected for framework {framework}. Score dropped from {prev_score}% to {score}% (Drop: {score_drop}%)."
                        )
                        
                        # Trigger alert notification
                        try:
                            from document_processing.alerts import trigger_security_alert
                            trigger_security_alert({
                                "finding_type": "Regulatory",
                                "risk_level": "HIGH",
                                "matched_pattern": f"{framework}_SCORE_DRIFT",
                                "matched_text": f"{framework} compliance score dropped by {score_drop} points.",
                                "recommendation": "Review recent file uploads and resolve exposed secrets or policy violations.",
                                "impact": "Decreased security readiness and high exposure to compliance audit failures.",
                                "priority": "P1",
                                "location_evidence": "Workspace compliance snapshot"
                            }, "System Health")
                        except Exception as alert_err:
                            logger.error(f"Failed to alert on drift: {alert_err}")
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to record score snapshot history: {e}")
