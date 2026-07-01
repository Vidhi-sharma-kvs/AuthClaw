package main

import (
	"log"
	"net/http"

	"authclaw/gateway-go/internal/gateway"
)

func main() {
	cfg, err := gateway.LoadConfig()
	if err != nil {
		log.Fatalf("gateway_config_error: %v", err)
	}

	server := &http.Server{
		Addr:         cfg.ListenAddr,
		Handler:      gateway.NewServer(cfg).Routes(),
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	}

	log.Printf("authclaw_go_gateway_starting addr=%s backend=%s", cfg.ListenAddr, cfg.BackendURL.String())
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("authclaw_go_gateway_stopped: %v", err)
	}
}
