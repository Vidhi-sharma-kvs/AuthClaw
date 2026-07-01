package secrets

import (
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"os"
	"strings"
)

type Manager struct {
	Backend string
}

type Health struct {
	Backend string
	Healthy bool
	Message string
}

func NewManager() Manager {
	backend := strings.TrimSpace(strings.ToLower(os.Getenv("AUTHCLAW_SECRET_BACKEND")))
	if backend == "" {
		backend = "local_env"
	}
	return Manager{Backend: backend}
}

func BootstrapLocalProcessSecrets() error {
	if isProduction() {
		return nil
	}
	if strings.TrimSpace(os.Getenv("AUTHCLAW_SECRET_BACKEND")) == "" {
		_ = os.Setenv("AUTHCLAW_SECRET_BACKEND", "local_env")
	}
	if strings.TrimSpace(os.Getenv("JWT_SECRET")) == "" && strings.TrimSpace(os.Getenv("AUTHCLAW_JWT_SECRET")) == "" {
		value, err := randomSecret(48)
		if err != nil {
			return err
		}
		_ = os.Setenv("JWT_SECRET", value)
	}
	if strings.TrimSpace(os.Getenv("AUTHCLAW_ENCRYPTION_KEY")) == "" {
		value, err := fernetKey()
		if err != nil {
			return err
		}
		_ = os.Setenv("AUTHCLAW_ENCRYPTION_KEY", value)
	}
	if strings.TrimSpace(os.Getenv("AUTHCLAW_REDACTION_SALT")) == "" {
		value, err := randomSecret(48)
		if err != nil {
			return err
		}
		_ = os.Setenv("AUTHCLAW_REDACTION_SALT", value)
	}
	return nil
}

func (m Manager) HealthCheck() Health {
	if m.Backend == "local" {
		m.Backend = "local_env"
	}
	switch m.Backend {
	case "local_env":
		if err := requireEnv("JWT_SECRET", "AUTHCLAW_JWT_SECRET"); err != nil {
			return Health{Backend: m.Backend, Healthy: false, Message: err.Error()}
		}
		if err := requireEnv("AUTHCLAW_ENCRYPTION_KEY"); err != nil {
			return Health{Backend: m.Backend, Healthy: false, Message: err.Error()}
		}
		if err := requireEnv("AUTHCLAW_REDACTION_SALT"); err != nil {
			return Health{Backend: m.Backend, Healthy: false, Message: err.Error()}
		}
		if isProduction() {
			return Health{Backend: m.Backend, Healthy: false, Message: "production requires a managed secret backend"}
		}
		return Health{Backend: m.Backend, Healthy: true, Message: "local secret provider healthy"}
	case "aws_secrets_manager":
		if err := requireEnv("AWS_REGION", "AWS_DEFAULT_REGION"); err != nil {
			return Health{Backend: m.Backend, Healthy: false, Message: err.Error()}
		}
		return Health{Backend: m.Backend, Healthy: true, Message: "aws secret provider configured"}
	case "hashicorp_vault", "vault":
		if err := requireEnv("VAULT_ADDR"); err != nil {
			return Health{Backend: "hashicorp_vault", Healthy: false, Message: err.Error()}
		}
		if err := requireEnv("VAULT_TOKEN"); err != nil {
			return Health{Backend: "hashicorp_vault", Healthy: false, Message: err.Error()}
		}
		return Health{Backend: "hashicorp_vault", Healthy: true, Message: "vault secret provider configured"}
	case "azure_key_vault":
		if err := requireEnv("AZURE_KEY_VAULT_URL"); err != nil {
			return Health{Backend: m.Backend, Healthy: false, Message: err.Error()}
		}
		return Health{Backend: m.Backend, Healthy: true, Message: "azure key vault provider configured"}
	case "google_secret_manager":
		if err := requireEnv("GOOGLE_CLOUD_PROJECT"); err != nil {
			return Health{Backend: m.Backend, Healthy: false, Message: err.Error()}
		}
		return Health{Backend: m.Backend, Healthy: true, Message: "google secret provider configured"}
	default:
		return Health{Backend: m.Backend, Healthy: false, Message: fmt.Sprintf("unsupported secret backend %q", m.Backend)}
	}
}

func (m Manager) ValidateStartup() error {
	health := m.HealthCheck()
	if !health.Healthy {
		return errors.New(health.Message)
	}
	return nil
}

func requireEnv(names ...string) error {
	for _, name := range names {
		if strings.TrimSpace(os.Getenv(name)) != "" {
			return nil
		}
	}
	return fmt.Errorf("required secret/config %s is missing", strings.Join(names, " or "))
}

func isProduction() bool {
	env := strings.ToLower(strings.TrimSpace(os.Getenv("AUTHCLAW_ENV")))
	return env == "production" || env == "prod"
}

func randomSecret(byteCount int) (string, error) {
	bytes := make([]byte, byteCount)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return base64.URLEncoding.EncodeToString(bytes), nil
}

func fernetKey() (string, error) {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return base64.URLEncoding.EncodeToString(bytes), nil
}
