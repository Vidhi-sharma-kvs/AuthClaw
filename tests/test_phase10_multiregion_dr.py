import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase10_terraform_declares_multiregion_dr_controls():
    terraform = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "deployment" / "terraform").glob("*.tf"))

    required = [
        "enable_multi_region_dr",
        "secondary_region",
        "aws_route53_health_check",
        "aws_route53_record",
        "weighted_routing_policy",
        "aws_s3_bucket_replication_configuration",
        "aws_backup_vault",
        "aws_backup_plan",
        "copy_action",
        "dr_rto_minutes",
        "dr_rpo_minutes",
        "global_authclaw_url",
    ]
    for item in required:
        assert item in terraform


def test_phase10_dr_validation_harness_reports_static_pass():
    module_path = ROOT / "scripts" / "dr_validation.py"
    spec = importlib.util.spec_from_file_location("dr_validation", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    exit_code = module.main(["--static-only"])
    assert exit_code == 0


def test_phase10_runbooks_and_promotion_workflow_exist():
    runbook = read("deployment/aws/dr-runbook.md")
    phase_doc = read("docs/phase10_multiregion_dr.md")
    workflow = read(".github/workflows/production-promotion.yml")

    assert "RTO: 30 minutes" in runbook
    assert "RPO: 15 minutes" in runbook
    assert "Chaos Scenarios" in phase_doc
    assert "environment: production" in workflow
    assert "python scripts/dr_validation.py --static-only" in workflow
    assert "latest" in workflow
