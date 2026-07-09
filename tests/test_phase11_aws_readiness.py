from pathlib import Path

from startup.validation import validate_production_environment


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase11_terraform_stack_declares_required_aws_resources():
    terraform = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "deployment" / "terraform").glob("*.tf")
    )

    required_resources = [
        "resource \"aws_ecs_cluster\"",
        "resource \"aws_ecs_service\"",
        "resource \"aws_db_instance\" \"postgres\"",
        "resource \"aws_secretsmanager_secret\"",
        "resource \"aws_s3_bucket\" \"documents\"",
        "resource \"aws_cloudwatch_log_group\"",
        "resource \"aws_lb\" \"main\"",
        "resource \"aws_security_group\"",
        "resource \"aws_nat_gateway\"",
    ]

    for resource in required_resources:
        assert resource in terraform

    assert "db.t3.small" in read("deployment/terraform/variables.tf")
    assert "/health/ready" in terraform
    assert "skip_final_snapshot        = false" in terraform
    assert "backup_retention_period" in terraform
    assert "authclaw/tenants/*" in terraform


def test_phase11_containers_and_compose_include_backend_frontend_health_checks():
    backend_dockerfile = read("Dockerfile")
    frontend_dockerfile = read("frontend/Dockerfile")
    compose = read("docker-compose.production.yml")
    nginx = read("frontend/nginx/authclaw.conf")

    assert "uvicorn" in backend_dockerfile
    assert "tesseract-ocr" in backend_dockerfile
    assert "/health/ready" in backend_dockerfile
    assert "USER authclaw" in backend_dockerfile

    assert "nginx:1.27-alpine" in frontend_dockerfile
    assert "npm run build" in frontend_dockerfile
    assert "HEALTHCHECK" in frontend_dockerfile
    assert "try_files $uri $uri/ /index.html" in nginx

    assert "authclaw-api:" in compose
    assert "authclaw-frontend:" in compose
    assert "postgres:" in compose


def test_phase11_production_validation_requires_s3_bucket_when_s3_enabled(monkeypatch):
    monkeypatch.setenv("AUTHCLAW_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("AUTHCLAW_ENCRYPTION_KEY", "not-the-development-default")
    monkeypatch.setenv("AUTHCLAW_ALLOWED_ORIGINS", "https://app.authclaw.example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.sendgrid.net")
    monkeypatch.setenv("SMTP_FROM", "no-reply@authclaw.example.com")
    monkeypatch.setenv("AUTHCLAW_RATE_LIMIT_PER_MINUTE", "120")
    monkeypatch.setenv("AUTHCLAW_OPA_ENABLED", "true")
    monkeypatch.setenv("AUTHCLAW_OPA_POLICY_URL", "http://opa:8181/v1/data/authclaw/policy")
    monkeypatch.setenv("AWS_SECRETS_MANAGER_ENABLED", "true")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AUTHCLAW_DOCUMENT_STORAGE_BACKEND", "s3")
    monkeypatch.delenv("AUTHCLAW_DOCUMENT_S3_BUCKET", raising=False)

    errors = validate_production_environment()

    assert "AUTHCLAW_DOCUMENT_S3_BUCKET is required when AUTHCLAW_DOCUMENT_STORAGE_BACKEND=s3." in errors

    monkeypatch.setenv("AUTHCLAW_DOCUMENT_S3_BUCKET", "authclaw-production-documents")

    assert validate_production_environment() == []
