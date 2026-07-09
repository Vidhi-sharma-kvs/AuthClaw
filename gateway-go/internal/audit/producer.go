package audit

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type Event map[string]any

type Producer struct {
	brokers     []string
	restURL     string
	topic       string
	dlqTopic    string
	queue       chan Event
	client      *http.Client
	maxAttempts int
}

func NewProducer(brokers []string, restURL string, topic string) *Producer {
	p := &Producer{
		brokers:     brokers,
		restURL:     strings.TrimRight(restURL, "/"),
		topic:       topic,
		dlqTopic:    topic + ".dlq",
		queue:       make(chan Event, 1024),
		client:      &http.Client{Timeout: 2 * time.Second},
		maxAttempts: 3,
	}
	go p.run()
	return p
}

func (p *Producer) Publish(event Event) {
	if p == nil || p.topic == "" {
		return
	}
	select {
	case p.queue <- event:
	default:
		log.Printf("audit_event_drop topic=%s reason=queue_full", p.topic)
	}
}

func (p *Producer) run() {
	for event := range p.queue {
		payload, err := json.Marshal(event)
		if err != nil {
			log.Printf("audit_event_encode_error topic=%s error=%v", p.topic, err)
			continue
		}
		if len(p.brokers) == 0 {
			log.Printf("audit_event_local topic=%s payload=%s", p.topic, payload)
			continue
		}
		if p.restURL != "" {
			if err := p.publishKafkaRESTWithRetry(p.topic, event); err == nil {
				continue
			} else {
				log.Printf("audit_event_kafka_rest_error topic=%s error=%v", p.topic, err)
				p.deadLetter(event, err)
				continue
			}
		}
		p.deadLetter(event, fmt.Errorf("Kafka REST/MSK proxy endpoint missing for brokers=%s", strings.Join(p.brokers, ",")))
	}
}

func (p *Producer) publishKafkaRESTWithRetry(topic string, event Event) error {
	var lastErr error
	for attempt := 1; attempt <= p.maxAttempts; attempt++ {
		if err := p.publishKafkaREST(topic, event); err != nil {
			lastErr = err
			time.Sleep(time.Duration(attempt) * 50 * time.Millisecond)
			continue
		}
		return nil
	}
	return lastErr
}

func (p *Producer) publishKafkaREST(topic string, event Event) error {
	endpoint := fmt.Sprintf("%s/topics/%s", p.restURL, url.PathEscape(topic))
	body, err := json.Marshal(map[string]any{
		"records": []map[string]any{
			{"value": event},
		},
	})
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/vnd.kafka.json.v2+json")
	req.Header.Set("Accept", "application/vnd.kafka.v2+json")
	resp, err := p.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("kafka rest returned %d", resp.StatusCode)
	}
	return nil
}

func (p *Producer) deadLetter(event Event, err error) {
	payload, _ := json.Marshal(event)
	log.Printf("audit_event_dead_letter topic=%s dlq_topic=%s error=%v payload=%s", p.topic, p.dlqTopic, err, payload)
	if p.restURL == "" {
		return
	}
	dlqEvent := Event{
		"event_type":   "audit_event_dead_letter",
		"source_topic": p.topic,
		"error":        err.Error(),
		"payload":      string(payload),
		"created_at":   time.Now().UTC().Format(time.RFC3339Nano),
	}
	if dlqErr := p.publishKafkaRESTWithRetry(p.dlqTopic, dlqEvent); dlqErr != nil {
		log.Printf("audit_event_dead_letter_publish_error topic=%s error=%v", p.dlqTopic, dlqErr)
	}
}
