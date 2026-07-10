package gateway

import (
	"errors"
	"regexp"
	"sort"
	"strings"
)

const (
	streamSafePlaceholder = "[AuthClaw blocked unsafe stream chunk]"
	defaultCarryBytes     = 2048
)

type redactionPattern struct {
	trigger     string
	re          *regexp.Regexp
	replacement string
}

type RedactionStats struct {
	ChunksProcessed   int64
	RedactionsApplied int64
	Failures          int64
	TriggerCounts     map[string]int64
}

type StreamingRedactor struct {
	carry       string
	carryBytes  int
	patterns    []redactionPattern
	stats       RedactionStats
	failForTest bool
}

func NewStreamingRedactor() *StreamingRedactor {
	return &StreamingRedactor{
		carryBytes: defaultCarryBytes,
		patterns: []redactionPattern{
			{
				trigger:     "jwt",
				re:          regexp.MustCompile(`(?i)\beyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\b`),
				replacement: "[REDACTED_JWT]",
			},
			{
				trigger:     "aws_access_key",
				re:          regexp.MustCompile(`\bA(KIA|SIA)[A-Z0-9]{16}\b`),
				replacement: "[REDACTED_AWS_KEY]",
			},
			{
				trigger:     "anthropic_api_key",
				re:          regexp.MustCompile(`\bsk-ant-[A-Za-z0-9_-]{16,}\b`),
				replacement: "[REDACTED_API_KEY]",
			},
			{
				trigger:     "openai_api_key",
				re:          regexp.MustCompile(`\bsk-[A-Za-z0-9_-]{16,}\b`),
				replacement: "[REDACTED_API_KEY]",
			},
			{
				trigger:     "sendgrid_api_key",
				re:          regexp.MustCompile(`\bSG\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b`),
				replacement: "[REDACTED_API_KEY]",
			},
			{
				trigger:     "google_api_key",
				re:          regexp.MustCompile(`\bAIza[0-9A-Za-z_-]{20,}\b`),
				replacement: "[REDACTED_API_KEY]",
			},
			{
				trigger:     "authclaw_api_key",
				re:          regexp.MustCompile(`\bac_[A-Za-z0-9_-]{20,}\b`),
				replacement: "[REDACTED_API_KEY]",
			},
			{
				trigger:     "bearer_token",
				re:          regexp.MustCompile(`(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b`),
				replacement: "Bearer [REDACTED_TOKEN]",
			},
			{
				trigger:     "azure_openai_key",
				re:          regexp.MustCompile(`(?i)\bazure[_-]?openai[_-]?(api[_-]?)?key\s*[:=]\s*["']?[A-Za-z0-9._-]{16,}["']?`),
				replacement: "[REDACTED_AZURE_OPENAI_KEY]",
			},
			{
				trigger:     "cohere_api_key",
				re:          regexp.MustCompile(`(?i)\bcohere[_-]?(api[_-]?)?key\s*[:=]\s*["']?[A-Za-z0-9._-]{16,}["']?`),
				replacement: "[REDACTED_COHERE_KEY]",
			},
			{
				trigger:     "secret_assignment",
				re:          regexp.MustCompile(`(?i)\b(api[_-]?key|secret|access[_-]?token|refresh[_-]?token|password|client[_-]?secret)\s*[:=]\s*["']?[A-Za-z0-9._~+/=-]{12,}["']?`),
				replacement: "[REDACTED_SECRET_ASSIGNMENT]",
			},
			{
				trigger:     "email",
				re:          regexp.MustCompile(`\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b`),
				replacement: "[REDACTED_EMAIL]",
			},
			{
				trigger:     "credit_card",
				re:          regexp.MustCompile(`\b(?:\d[ -]*?){13,19}\b`),
				replacement: "[REDACTED_FINANCIAL_IDENTIFIER]",
			},
			{
				trigger:     "phone",
				re:          regexp.MustCompile(`(?i)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)\d{3,5}[\s.-]?\d{3,6}\b`),
				replacement: "[REDACTED_PHONE]",
			},
			{
				trigger:     "ssn",
				re:          regexp.MustCompile(`\b\d{3}-\d{2}-\d{4}\b`),
				replacement: "[REDACTED_SSN]",
			},
			{
				trigger:     "medical_identifier",
				re:          regexp.MustCompile(`(?i)\b(MRN|medical record|patient id|patient identifier)\s*[:#=]?\s*[A-Za-z0-9-]{5,}\b`),
				replacement: "[REDACTED_MEDICAL_IDENTIFIER]",
			},
			{
				trigger:     "phi_context",
				re:          regexp.MustCompile(`(?i)\b(patient|diagnosis|prescription|treatment plan|health history)\b[^\n\r]{0,120}`),
				replacement: "[REDACTED_PHI_CONTEXT]",
			},
			{
				trigger:     "prompt_injection",
				re:          regexp.MustCompile(`(?i)\b(ignore\s+(all\s+)?(previous\s+)?instructions|reveal\s+system\s+prompt|show\s+internal\s+system\s+prompts|developer\s+mode|jailbreak|bypass\s+policy)\b[^\n\r]{0,120}`),
				replacement: "[REDACTED_PROMPT_INJECTION]",
			},
			{
				trigger:     "system_prompt",
				re:          regexp.MustCompile(`(?i)(system\s+prompt|developer\s+message|hidden\s+instruction|internal\s+instruction)s?\s*[:=]\s*[^\n\r]+`),
				replacement: "[REDACTED_INTERNAL_PROMPT]",
			},
			{
				trigger:     "hidden_metadata",
				re:          regexp.MustCompile(`(?i)"?(hidden_metadata|policy_sensitive_metadata|internal_policy|system_prompt)"?\s*:\s*"[^"]*"`),
				replacement: `"[REDACTED_METADATA]"`,
			},
		},
		stats: RedactionStats{TriggerCounts: map[string]int64{}},
	}
}

func (r *StreamingRedactor) Process(chunk []byte, final bool) ([]byte, error) {
	if r.failForTest {
		r.stats.Failures++
		return []byte(streamSafePlaceholder), errors.New("stream redactor forced failure")
	}
	if len(chunk) > 0 {
		r.stats.ChunksProcessed++
	}

	combined := r.carry + string(chunk)
	if combined == "" {
		return nil, nil
	}

	redacted := r.redactText(combined)
	if final {
		r.carry = ""
		return []byte(redacted), nil
	}

	flushLen := safeFlushLength(redacted, r.carryBytes)
	if flushLen <= 0 {
		r.carry = redacted
		return nil, nil
	}

	out := redacted[:flushLen]
	r.carry = redacted[flushLen:]
	return []byte(out), nil
}

func (r *StreamingRedactor) Stats() RedactionStats {
	counts := map[string]int64{}
	for key, value := range r.stats.TriggerCounts {
		counts[key] = value
	}
	return RedactionStats{
		ChunksProcessed:   r.stats.ChunksProcessed,
		RedactionsApplied: r.stats.RedactionsApplied,
		Failures:          r.stats.Failures,
		TriggerCounts:     counts,
	}
}

func (r *StreamingRedactor) redactText(input string) string {
	output := input
	lowerInput := strings.ToLower(input)
	digitCount := countDigits(input)
	for _, pattern := range r.patterns {
		if !redactionPatternMayMatch(pattern.trigger, input, lowerInput, digitCount) {
			continue
		}
		matches := pattern.re.FindAllStringIndex(output, -1)
		if len(matches) == 0 {
			continue
		}
		r.stats.RedactionsApplied += int64(len(matches))
		r.stats.TriggerCounts[pattern.trigger] += int64(len(matches))
		output = pattern.re.ReplaceAllString(output, pattern.replacement)
	}
	return output
}

func countDigits(value string) int {
	count := 0
	for _, char := range value {
		if char >= '0' && char <= '9' {
			count++
		}
	}
	return count
}

func redactionPatternMayMatch(trigger string, input string, lowerInput string, digitCount int) bool {
	switch trigger {
	case "jwt":
		return strings.Contains(lowerInput, "eyj") && strings.Count(input, ".") >= 2
	case "aws_access_key":
		return strings.Contains(input, "AKIA") || strings.Contains(input, "ASIA")
	case "anthropic_api_key":
		return strings.Contains(lowerInput, "sk-ant-")
	case "openai_api_key":
		return strings.Contains(lowerInput, "sk-")
	case "sendgrid_api_key":
		return strings.Contains(input, "SG.")
	case "google_api_key":
		return strings.Contains(input, "AIza")
	case "authclaw_api_key":
		return strings.Contains(lowerInput, "ac_")
	case "bearer_token":
		return strings.Contains(lowerInput, "bearer")
	case "azure_openai_key":
		return strings.Contains(lowerInput, "azure")
	case "cohere_api_key":
		return strings.Contains(lowerInput, "cohere")
	case "secret_assignment":
		if !strings.ContainsAny(input, ":=") {
			return false
		}
		return strings.Contains(lowerInput, "api") ||
			strings.Contains(lowerInput, "key") ||
			strings.Contains(lowerInput, "secret") ||
			strings.Contains(lowerInput, "token") ||
			strings.Contains(lowerInput, "password") ||
			strings.Contains(lowerInput, "client")
	case "email":
		return strings.Contains(input, "@")
	case "credit_card":
		return digitCount >= 13
	case "phone":
		return digitCount >= 10
	case "ssn":
		return digitCount >= 9 && strings.Contains(input, "-")
	case "medical_identifier":
		return strings.Contains(lowerInput, "mrn") ||
			strings.Contains(lowerInput, "medical record") ||
			strings.Contains(lowerInput, "patient id") ||
			strings.Contains(lowerInput, "patient identifier")
	case "phi_context":
		return strings.Contains(lowerInput, "patient") ||
			strings.Contains(lowerInput, "diagnosis") ||
			strings.Contains(lowerInput, "prescription") ||
			strings.Contains(lowerInput, "treatment plan") ||
			strings.Contains(lowerInput, "health history")
	case "prompt_injection":
		return strings.Contains(lowerInput, "ignore") ||
			strings.Contains(lowerInput, "reveal system prompt") ||
			strings.Contains(lowerInput, "show internal") ||
			strings.Contains(lowerInput, "developer mode") ||
			strings.Contains(lowerInput, "jailbreak") ||
			strings.Contains(lowerInput, "bypass policy")
	case "system_prompt":
		return strings.Contains(lowerInput, "system prompt") ||
			strings.Contains(lowerInput, "developer message") ||
			strings.Contains(lowerInput, "hidden instruction") ||
			strings.Contains(lowerInput, "internal instruction")
	case "hidden_metadata":
		return strings.Contains(lowerInput, "hidden_metadata") ||
			strings.Contains(lowerInput, "policy_sensitive_metadata") ||
			strings.Contains(lowerInput, "internal_policy") ||
			strings.Contains(lowerInput, "system_prompt")
	default:
		return true
	}
}

func safeFlushLength(value string, carryBytes int) int {
	if len(value) <= carryBytes {
		if idx := strings.LastIndex(value, "\n\n"); idx >= 0 {
			return idx + 2
		}
		return 0
	}

	flushLen := len(value) - carryBytes
	if idx := strings.LastIndex(value[:flushLen], "\n\n"); idx >= 0 {
		return idx + 2
	}
	if idx := strings.LastIndex(value[:flushLen], "\n"); idx >= 0 {
		return idx + 1
	}
	return flushLen
}

func triggerSummary(stats RedactionStats) string {
	if len(stats.TriggerCounts) == 0 {
		return "none"
	}
	keys := make([]string, 0, len(stats.TriggerCounts))
	for key := range stats.TriggerCounts {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, key)
	}
	return strings.Join(parts, ",")
}
