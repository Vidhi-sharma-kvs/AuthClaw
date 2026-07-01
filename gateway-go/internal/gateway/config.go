package gateway

import (
	"net/url"
	"os"
	"strings"
	"time"

	"authclaw/gateway-go/internal/secrets"
)

type Config struct {
	ListenAddr     string
	BackendURL     *url.URL
	AllowedOrigins []string
	ReadTimeout    time.Duration
	WriteTimeout   time.Duration
	SecretManager  secrets.Manager
}

func LoadConfig() (Config, error) {
	if err := secrets.BootstrapLocalProcessSecrets(); err != nil {
		return Config{}, err
	}
	secretManager := secrets.NewManager()
	if err := secretManager.ValidateStartup(); err != nil {
		return Config{}, err
	}
	backendRaw := env("AUTHCLAW_BACKEND_URL", "http://127.0.0.1:8000")
	backendURL, err := url.Parse(backendRaw)
	if err != nil {
		return Config{}, err
	}

	origins := splitCSV(env("AUTHCLAW_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"))
	return Config{
		ListenAddr:     env("AUTHCLAW_GATEWAY_ADDR", "127.0.0.1:9000"),
		BackendURL:     backendURL,
		AllowedOrigins: origins,
		ReadTimeout:    30 * time.Second,
		WriteTimeout:   120 * time.Second,
		SecretManager:  secretManager,
	}, nil
}

func env(name, fallback string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	return value
}

func splitCSV(raw string) []string {
	parts := strings.Split(raw, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		value := strings.TrimSpace(part)
		if value != "" {
			values = append(values, value)
		}
	}
	return values
}
