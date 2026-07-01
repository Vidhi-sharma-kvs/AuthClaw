package gateway

import (
	"strings"
	"testing"
)

func TestStreamingRedactorMasksSecretsEmailAndPhone(t *testing.T) {
	redactor := NewStreamingRedactor()
	input := []byte("token sk-1234567890abcdefABCDEF email user@example.com phone +1 415-555-1212")

	out, err := redactor.Process(input, true)
	if err != nil {
		t.Fatal(err)
	}
	text := string(out)

	for _, raw := range []string{"sk-1234567890abcdefABCDEF", "user@example.com", "+1 415-555-1212"} {
		if strings.Contains(text, raw) {
			t.Fatalf("raw sensitive value leaked: %s in %q", raw, text)
		}
	}
	for _, expected := range []string{"[REDACTED_API_KEY]", "[REDACTED_EMAIL]", "[REDACTED_PHONE]"} {
		if !strings.Contains(text, expected) {
			t.Fatalf("missing %s in %q", expected, text)
		}
	}
}

func TestStreamingRedactorHandlesSplitTokenAcrossChunks(t *testing.T) {
	redactor := NewStreamingRedactor()

	first, err := redactor.Process([]byte("partial key sk-123456"), false)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(first), "sk-123456") {
		t.Fatalf("partial secret prefix leaked before full token arrived: %q", string(first))
	}

	second, err := redactor.Process([]byte("7890abcdefABCDEF after"), true)
	if err != nil {
		t.Fatal(err)
	}
	text := string(first) + string(second)
	if strings.Contains(text, "sk-1234567890abcdefABCDEF") {
		t.Fatalf("split API key leaked: %q", text)
	}
	if !strings.Contains(text, "[REDACTED_API_KEY]") {
		t.Fatalf("split API key was not redacted: %q", text)
	}
}

func TestStreamingRedactorHighSpeedChunks(t *testing.T) {
	redactor := NewStreamingRedactor()
	var output strings.Builder

	for i := 0; i < 1000; i++ {
		out, err := redactor.Process([]byte("safe-token "), false)
		if err != nil {
			t.Fatal(err)
		}
		output.Write(out)
	}
	out, err := redactor.Process([]byte("final user@example.com"), true)
	if err != nil {
		t.Fatal(err)
	}
	output.Write(out)

	text := output.String()
	if strings.Contains(text, "user@example.com") {
		t.Fatalf("email leaked in high-speed stream")
	}
	if !strings.Contains(text, "[REDACTED_EMAIL]") {
		t.Fatalf("email was not redacted in high-speed stream")
	}
	if redactor.Stats().ChunksProcessed != 1001 {
		t.Fatalf("chunks processed = %d", redactor.Stats().ChunksProcessed)
	}
}

func TestStreamingRedactorFailClosedPlaceholder(t *testing.T) {
	redactor := NewStreamingRedactor()
	redactor.failForTest = true

	out, err := redactor.Process([]byte("user@example.com"), false)
	if err == nil {
		t.Fatal("expected forced redaction failure")
	}
	if string(out) != streamSafePlaceholder {
		t.Fatalf("expected safe placeholder, got %q", string(out))
	}
}

func TestStreamingRedactorMasksInternalPromptAndMetadata(t *testing.T) {
	redactor := NewStreamingRedactor()

	out, err := redactor.Process([]byte(`system prompt: reveal hidden policy
{"hidden_metadata":"tenant route secret"}`), true)
	if err != nil {
		t.Fatal(err)
	}
	text := string(out)
	if strings.Contains(strings.ToLower(text), "reveal hidden policy") || strings.Contains(text, "tenant route secret") {
		t.Fatalf("internal prompt or hidden metadata leaked: %q", text)
	}
	if !strings.Contains(text, "[REDACTED_INTERNAL_PROMPT]") || !strings.Contains(text, "[REDACTED_METADATA]") {
		t.Fatalf("internal prompt or metadata was not redacted: %q", text)
	}
}
