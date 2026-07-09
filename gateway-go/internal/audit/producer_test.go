package audit

import (
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
)

func TestProducerRetriesKafkaRESTBeforeSuccess(t *testing.T) {
	var calls int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		atomic.AddInt32(&calls, 1)
		if calls < 3 {
			http.Error(w, "temporary failure", http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	p := NewProducer([]string{"broker:9092"}, server.URL, "authclaw-audit-events")
	p.maxAttempts = 3

	err := p.publishKafkaRESTWithRetry(p.topic, Event{"event_type": "gateway_request", "request_id": "req-1"})
	if err != nil {
		t.Fatalf("expected retry to succeed: %v", err)
	}
	if calls != 3 {
		t.Fatalf("calls = %d, expected 3", calls)
	}
}

func TestProducerPublishesDeadLetterToDLQTopic(t *testing.T) {
	var dlqSeen atomic.Bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		if req.URL.Path == "/topics/authclaw-audit-events.dlq" {
			dlqSeen.Store(true)
			w.WriteHeader(http.StatusOK)
			return
		}
		http.Error(w, "permanent failure", http.StatusServiceUnavailable)
	}))
	defer server.Close()

	p := NewProducer([]string{"broker:9092"}, server.URL, "authclaw-audit-events")
	p.maxAttempts = 1
	p.deadLetter(Event{"event_type": "gateway_request", "request_id": "req-2"}, http.ErrHandlerTimeout)

	if !dlqSeen.Load() {
		t.Fatalf("expected DLQ topic publish")
	}
}
