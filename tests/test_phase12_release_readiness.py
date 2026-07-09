import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_script(name: str):
    module_path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase12_ci_security_scans_are_blocking():
    workflow = read(".github/workflows/ci.yml")

    assert "bypassing block" not in workflow
    assert "bandit -r" in workflow
    assert "pip-audit -r requirements.txt --strict" in workflow
    assert "semgrep/semgrep-action" in workflow
    assert "npm audit --audit-level=high" in workflow
    assert "aquasecurity/trivy-action" in workflow
    assert 'exit-code: "1"' in workflow
    assert "release-readiness:" in workflow
    assert "scripts/red_team_harness.py" in workflow
    assert "scripts/release_readiness.py --strict" in workflow


def test_phase12_red_team_and_readiness_harnesses_pass():
    red_team = load_script("red_team_harness.py")
    readiness = load_script("release_readiness.py")

    red_team_report = red_team.run_harness()
    readiness_report = readiness.build_report()

    assert red_team_report["status"] == "pass"
    assert readiness_report["status"] == "pass"


def test_phase12_threat_model_and_release_report_cover_required_evidence():
    threat_model = read("docs/threat_model.md")
    report = read("docs/release_readiness_report.md")

    for item in [
        "Cross-tenant data access",
        "Approval or MFA bypass",
        "Provider credential exfiltration",
        "Audit tampering",
        "Regional outage",
    ]:
        assert item in threat_model

    for item in [
        "Blocking SAST",
        "dependency",
        "container scans",
        "External pentest",
        "DR validation report",
        "SRS traceability matrix",
    ]:
        assert item in report
