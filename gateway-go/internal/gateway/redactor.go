package gateway

import (
	"errors"
	"regexp"
	"sort"
	"strings"
)

const (
	streamSafePlaceholder = "[AuthClaw blocked unsafe stream chunk]"
	defaultCarryBytes     = 512
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
				trigger:     "email",
				re:          regexp.MustCompile(`\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b`),
				replacement: "[REDACTED_EMAIL]",
			},
			{
				trigger:     "phone",
				re:          regexp.MustCompile(`(?i)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)\d{3,5}[\s.-]?\d{3,6}\b`),
				replacement: "[REDACTED_PHONE]",
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
	for _, pattern := range r.patterns {
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
