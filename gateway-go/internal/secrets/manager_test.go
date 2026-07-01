package secrets

import "testing"

func TestBootstrapLocalProcessSecrets(t *testing.T) {
	t.Setenv("AUTHCLAW_ENV", "development")
	t.Setenv("AUTHCLAW_SECRET_BACKEND", "")
	t.Setenv("JWT_SECRET", "")
	t.Setenv("AUTHCLAW_JWT_SECRET", "")
	t.Setenv("AUTHCLAW_ENCRYPTION_KEY", "")
	t.Setenv("AUTHCLAW_REDACTION_SALT", "")

	if err := BootstrapLocalProcessSecrets(); err != nil {
		t.Fatalf("bootstrap failed: %v", err)
	}
	manager := NewManager()
	health := manager.HealthCheck()
	if !health.Healthy {
		t.Fatalf("expected healthy local secrets, got: %#v", health)
	}
}

func TestProductionRejectsLocalSecretBackend(t *testing.T) {
	t.Setenv("AUTHCLAW_ENV", "production")
	t.Setenv("AUTHCLAW_SECRET_BACKEND", "local_env")
	t.Setenv("JWT_SECRET", "abcdefghijklmnopqrstuvwxyz123456")
	t.Setenv("AUTHCLAW_ENCRYPTION_KEY", "abcdefghijklmnopqrstuvwxyz123456789012345=")
	t.Setenv("AUTHCLAW_REDACTION_SALT", "abcdefghijklmnopqrstuvwxyz123456")

	manager := NewManager()
	if err := manager.ValidateStartup(); err == nil {
		t.Fatal("expected production local_env validation to fail")
	}
}

func TestManagedBackendValidation(t *testing.T) {
	t.Setenv("AUTHCLAW_ENV", "production")
	t.Setenv("AUTHCLAW_SECRET_BACKEND", "aws_secrets_manager")
	t.Setenv("AWS_REGION", "us-east-1")

	manager := NewManager()
	if err := manager.ValidateStartup(); err != nil {
		t.Fatalf("expected configured AWS secret backend to validate: %v", err)
	}
}
