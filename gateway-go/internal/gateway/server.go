package gateway

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"strings"
	"time"

	auditlog "authclaw/gateway-go/internal/audit"
)

type Server struct {
	cfg    Config
	proxy  *httputil.ReverseProxy
	client *http.Client
	audit  *auditlog.Producer
}

func NewServer(cfg Config) *Server {
	proxy := httputil.NewSingleHostReverseProxy(cfg.BackendURL)
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.URL.Scheme = cfg.BackendURL.Scheme
		req.URL.Host = cfg.BackendURL.Host
		req.Host = cfg.BackendURL.Host
		req.URL.Path = backendPath(req.URL.Path)
		req.Header.Del("Accept-Encoding")
		req.Header.Set("X-AuthClaw-Gateway", "go")
		if req.Header.Get("X-AuthClaw-Gateway-Request-ID") == "" {
			req.Header.Set("X-AuthClaw-Gateway-Request-ID", requestID())
		}
	}
	proxy.ModifyResponse = func(resp *http.Response) error {
		resp.Header.Set("X-AuthClaw-Gateway", "go")
		if streamRedactionRequired(resp) {
			if resp.Header.Get("Content-Encoding") != "" {
				log.Printf("stream_redaction_encoded_response_blocked path=%s encoding=%s", resp.Request.URL.Path, resp.Header.Get("Content-Encoding"))
				return errors.New("stream redaction cannot inspect encoded upstream response")
			}
			resp.Body = newRedactingReadCloser(resp.Body, resp.Request.URL.Path)
			resp.Header.Del("Content-Length")
			resp.Header.Set("X-AuthClaw-Streaming-Redaction", "enforced")
			resp.ContentLength = -1
		}
		return nil
	}
	proxy.ErrorHandler = func(w http.ResponseWriter, req *http.Request, err error) {
		log.Printf("gateway_proxy_error method=%s path=%s backend=%s error=%v", req.Method, req.URL.Path, cfg.BackendURL.String(), err)
		writeJSON(w, http.StatusBadGateway, map[string]any{
			"error":   "backend_unavailable",
			"message": "AuthClaw Python governance backend is unavailable.",
		})
	}

	return &Server{
		cfg:   cfg,
		proxy: proxy,
		audit: auditlog.NewProducer(cfg.KafkaBrokers, cfg.KafkaRESTURL, cfg.AuditTopic),
		client: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health/live", s.live)
	mux.HandleFunc("/health/ready", s.ready)
	mux.HandleFunc("/", s.proxyRequest)
	return s.cors(s.recoverPanic(s.logRequest(mux)))
}

func (s *Server) live(w http.ResponseWriter, req *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status":  "live",
		"service": "authclaw-go-gateway",
	})
}

func (s *Server) ready(w http.ResponseWriter, req *http.Request) {
	ctx, cancel := context.WithTimeout(req.Context(), 5*time.Second)
	defer cancel()
	secretHealth := s.cfg.SecretManager.HealthCheck()
	if !secretHealth.Healthy {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{
			"status":         "not_ready",
			"service":        "authclaw-go-gateway",
			"secret_backend": secretHealth.Backend,
			"secret_health":  "failed",
			"error":          secretHealth.Message,
		})
		return
	}

	backendReq, err := http.NewRequestWithContext(ctx, http.MethodGet, s.cfg.BackendURL.String()+"/health/ready", nil)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"status": "not_ready", "error": err.Error()})
		return
	}
	resp, err := s.client.Do(backendReq)
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{
			"status":  "not_ready",
			"service": "authclaw-go-gateway",
			"backend": "unreachable",
			"error":   err.Error(),
		})
		return
	}
	defer resp.Body.Close()

	status := http.StatusOK
	ready := "ready"
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		status = http.StatusServiceUnavailable
		ready = "not_ready"
	}
	writeJSON(w, status, map[string]any{
		"status":         ready,
		"service":        "authclaw-go-gateway",
		"backend":        s.cfg.BackendURL.String(),
		"backend_status": resp.StatusCode,
		"secret_backend": secretHealth.Backend,
		"secret_health":  "ok",
	})
}

func (s *Server) proxyRequest(w http.ResponseWriter, req *http.Request) {
	if req.Method == http.MethodOptions {
		w.WriteHeader(http.StatusNoContent)
		return
	}

	if isGatewayRuntime(req.URL.Path) {
		req.Header.Set("X-AuthClaw-Gateway-Runtime", "true")
		decision, err := s.evaluatePolicy(req)
		if err != nil {
			log.Printf("policy_preflight_failed method=%s path=%s error=%v", req.Method, req.URL.Path, err)
			writeJSON(w, http.StatusServiceUnavailable, map[string]any{
				"error":   "policy_engine_unavailable",
				"message": "AuthClaw policy engine failed closed before provider routing.",
			})
			return
		}
		req.Header.Set("X-AuthClaw-Policy-Decision", decision.Decision)
		req.Header.Set("X-AuthClaw-Policy-Request-ID", decision.RequestID)
		if !decision.Allowed {
			log.Printf(
				"policy_preflight_blocked method=%s path=%s request_id=%s decision=%s matched_policies=%d evaluation_ms=%d",
				req.Method,
				req.URL.Path,
				decision.RequestID,
				decision.Decision,
				len(decision.MatchedPolicies),
				decision.EvaluationTimeMS,
			)
			writeJSON(w, http.StatusForbidden, map[string]any{
				"error":              "policy_blocked",
				"decision":           decision.Decision,
				"reason":             decision.Reason,
				"request_id":         decision.RequestID,
				"matched_policies":   decision.MatchedPolicies,
				"policy_versions":    decision.PolicyVersions,
				"evaluation_time_ms": decision.EvaluationTimeMS,
			})
			return
		}
		log.Printf(
			"policy_preflight_passed method=%s path=%s request_id=%s decision=%s matched_policies=%d evaluation_ms=%d",
			req.Method,
			req.URL.Path,
			decision.RequestID,
			decision.Decision,
			len(decision.MatchedPolicies),
			decision.EvaluationTimeMS,
		)
	}
	s.proxy.ServeHTTP(w, req)
}

func (s *Server) evaluatePolicy(req *http.Request) (policyDecision, error) {
	requestID := req.Header.Get("X-AuthClaw-Gateway-Request-ID")
	if requestID == "" {
		requestID = requestIDValue()
		req.Header.Set("X-AuthClaw-Gateway-Request-ID", requestID)
	}

	var bodyBytes []byte
	if req.Body != nil {
		var err error
		bodyBytes, err = io.ReadAll(req.Body)
		if err != nil {
			return policyDecision{}, err
		}
		if err := req.Body.Close(); err != nil {
			return policyDecision{}, err
		}
		req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
	}

	var body any
	if len(bytes.TrimSpace(bodyBytes)) > 0 {
		if err := json.Unmarshal(bodyBytes, &body); err != nil {
			body = string(bodyBytes)
		}
	} else {
		body = map[string]any{}
	}

	payload := map[string]any{
		"method":     req.Method,
		"path":       backendPath(req.URL.Path),
		"request_id": requestID,
		"body":       body,
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return policyDecision{}, err
	}

	ctx, cancel := context.WithTimeout(req.Context(), 5*time.Second)
	defer cancel()
	if s.cfg.OPAURL != nil {
		decision, err := s.evaluateOPA(ctx, payload, requestID)
		if err == nil && decision.Decision != "" {
			req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
			return decision, nil
		}
		log.Printf("opa_policy_fallback request_id=%s error=%v", requestID, err)
	}
	policyURL := s.cfg.BackendURL.String() + "/internal/policy/evaluate"
	policyReq, err := http.NewRequestWithContext(ctx, http.MethodPost, policyURL, bytes.NewReader(payloadBytes))
	if err != nil {
		return policyDecision{}, err
	}
	policyReq.Header.Set("Content-Type", "application/json")
	policyReq.Header.Set("X-AuthClaw-Gateway", "go")
	policyReq.Header.Set("X-AuthClaw-Gateway-Request-ID", requestID)
	copyHeader(policyReq.Header, req.Header, "Authorization")
	copyHeader(policyReq.Header, req.Header, "X-API-Key")

	resp, err := s.client.Do(policyReq)
	if err != nil {
		return policyDecision{}, err
	}
	defer resp.Body.Close()

	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return policyDecision{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return policyDecision{}, errors.New("policy engine denied or failed evaluation")
	}

	var decision policyDecision
	if err := json.Unmarshal(responseBody, &decision); err != nil {
		return policyDecision{}, err
	}
	if decision.Decision == "" {
		return policyDecision{}, errors.New("policy engine returned empty decision")
	}
	if decision.RequestID == "" {
		decision.RequestID = requestID
	}
	req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
	return decision, nil
}

func (s *Server) evaluateOPA(ctx context.Context, payload map[string]any, requestID string) (policyDecision, error) {
	opaPayload := map[string]any{
		"input": map[string]any{
			"text":       extractPolicyText(payload["body"]),
			"context":    payload,
			"request_id": requestID,
		},
	}
	opaBytes, err := json.Marshal(opaPayload)
	if err != nil {
		return policyDecision{}, err
	}
	opaReq, err := http.NewRequestWithContext(ctx, http.MethodPost, s.cfg.OPAURL.String(), bytes.NewReader(opaBytes))
	if err != nil {
		return policyDecision{}, err
	}
	opaReq.Header.Set("Content-Type", "application/json")
	resp, err := s.client.Do(opaReq)
	if err != nil {
		return policyDecision{}, err
	}
	defer resp.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return policyDecision{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return policyDecision{}, errors.New("opa policy evaluation failed")
	}

	var wrapper struct {
		Result map[string]any `json:"result"`
	}
	if err := json.Unmarshal(responseBody, &wrapper); err != nil {
		return policyDecision{}, err
	}
	if wrapper.Result == nil {
		return policyDecision{}, errors.New("opa returned empty result")
	}
	decision := policyDecision{
		Decision:         stringValue(wrapper.Result["decision"], "ALLOW"),
		Allowed:          boolValue(wrapper.Result["allow"], true),
		Reason:           stringValue(wrapper.Result["reason"], "OPA policy decision"),
		RequestID:        requestID,
		EvaluationTimeMS: 0,
		PolicyVersions: []map[string]any{
			{"engine": "opa", "status": "evaluated"},
		},
	}
	if findings, ok := wrapper.Result["findings"].([]any); ok {
		for _, item := range findings {
			if finding, ok := item.(map[string]any); ok {
				decision.MatchedPolicies = append(decision.MatchedPolicies, finding)
			}
		}
	}
	return decision, nil
}

func (s *Server) cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		origin := req.Header.Get("Origin")
		if origin != "" && originAllowed(origin, s.cfg.AllowedOrigins) {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type, X-API-Key, X-Session-ID")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		}
		next.ServeHTTP(w, req)
	})
}

func (s *Server) logRequest(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		start := time.Now()
		recorder := &statusRecorder{ResponseWriter: w, statusCode: http.StatusOK}
		next.ServeHTTP(recorder, req)
		requestID := req.Header.Get("X-AuthClaw-Gateway-Request-ID")
		if requestID == "" {
			requestID = req.Header.Get("X-AuthClaw-Policy-Request-ID")
		}
		if s.audit != nil {
			s.audit.Publish(auditlog.Event{
				"event_type":   "gateway_request",
				"request_id":   requestID,
				"method":       req.Method,
				"path":         req.URL.Path,
				"backend_path": backendPath(req.URL.Path),
				"status":       recorder.statusCode,
				"runtime":      isGatewayRuntime(req.URL.Path),
				"duration_ms":  time.Since(start).Milliseconds(),
				"created_at":   time.Now().UTC().Format(time.RFC3339Nano),
			})
		}
		log.Printf(
			"gateway_request method=%s path=%s backend_path=%s status=%d duration_ms=%d runtime=%t",
			req.Method,
			req.URL.Path,
			backendPath(req.URL.Path),
			recorder.statusCode,
			time.Since(start).Milliseconds(),
			isGatewayRuntime(req.URL.Path),
		)
	})
}

func (s *Server) recoverPanic(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		defer func() {
			if recovered := recover(); recovered != nil {
				log.Printf("gateway_panic path=%s error=%v", req.URL.Path, recovered)
				writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "gateway_internal_error"})
			}
		}()
		next.ServeHTTP(w, req)
	})
}

func backendPath(path string) string {
	if path == "/api" {
		return "/"
	}
	if strings.HasPrefix(path, "/api/") {
		return strings.TrimPrefix(path, "/api")
	}
	return path
}

func isGatewayRuntime(path string) bool {
	normalized := backendPath(path)
	return normalized == "/gateway/chat" ||
		normalized == "/chat" ||
		normalized == "/v1/chat/completions" ||
		strings.HasPrefix(normalized, "/gateway/documents/")
}

func streamRedactionRequired(resp *http.Response) bool {
	if resp == nil || resp.Request == nil || !isGatewayRuntime(resp.Request.URL.Path) {
		return false
	}
	contentType := strings.ToLower(resp.Header.Get("Content-Type"))
	if strings.Contains(contentType, "text/event-stream") {
		return true
	}
	for _, encoding := range resp.TransferEncoding {
		if strings.EqualFold(encoding, "chunked") {
			return true
		}
	}
	return resp.ContentLength < 0
}

func originAllowed(origin string, allowed []string) bool {
	for _, item := range allowed {
		if item == "*" || item == origin {
			return true
		}
	}
	return false
}

func requestID() string {
	return requestIDValue()
}

func requestIDValue() string {
	return "gw-" + strings.ReplaceAll(time.Now().UTC().Format("20060102T150405.000000000"), ".", "")
}

func copyHeader(dst http.Header, src http.Header, name string) {
	if value := src.Get(name); value != "" {
		dst.Set(name, value)
	}
}

func extractPolicyText(body any) string {
	switch value := body.(type) {
	case string:
		return value
	case map[string]any:
		if message, ok := value["message"].(string); ok {
			return message
		}
		if messages, ok := value["messages"].([]any); ok && len(messages) > 0 {
			if last, ok := messages[len(messages)-1].(map[string]any); ok {
				if content, ok := last["content"].(string); ok {
					return content
				}
			}
		}
		bytes, _ := json.Marshal(value)
		return string(bytes)
	default:
		bytes, _ := json.Marshal(value)
		return string(bytes)
	}
}

func stringValue(value any, fallback string) string {
	if text, ok := value.(string); ok && text != "" {
		return text
	}
	return fallback
}

func boolValue(value any, fallback bool) bool {
	if boolean, ok := value.(bool); ok {
		return boolean
	}
	return fallback
}

func writeJSON(w http.ResponseWriter, status int, payload map[string]any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil && !errors.Is(err, net.ErrClosed) {
		log.Printf("gateway_json_write_error error=%v", err)
	}
}

type statusRecorder struct {
	http.ResponseWriter
	statusCode int
}

func (r *statusRecorder) WriteHeader(statusCode int) {
	r.statusCode = statusCode
	r.ResponseWriter.WriteHeader(statusCode)
}

type policyDecision struct {
	Decision         string           `json:"decision"`
	Allowed          bool             `json:"allowed"`
	Reason           string           `json:"reason"`
	RequestID        string           `json:"request_id"`
	EvaluationTimeMS int              `json:"evaluation_time_ms"`
	MatchedPolicies  []map[string]any `json:"matched_policies"`
	PolicyVersions   []map[string]any `json:"policy_versions"`
}
