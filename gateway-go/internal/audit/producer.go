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
	brokers []string
	restURL string
	topic   string
	queue   chan Event
	client  *http.Client
}

func NewProducer(brokers []string, restURL string, topic string) *Producer {
	p := &Producer{
		brokers: brokers,
		restURL: strings.TrimRight(restURL, "/"),
		topic:   topic,
		queue:   make(chan Event, 1024),
		client:  &http.Client{Timeout: 2 * time.Second},
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
			if err := p.publishKafkaREST(event); err == nil {
				continue
			} else {
				log.Printf("audit_event_kafka_rest_error topic=%s error=%v", p.topic, err)
			}
		}
		log.Printf(
			"audit_event_kafka_scaffold topic=%s brokers=%s payload=%s",
			p.topic,
			strings.Join(p.brokers, ","),
			payload,
		)
	}
}

func (p *Producer) publishKafkaREST(event Event) error {
	endpoint := fmt.Sprintf("%s/topics/%s", p.restURL, url.PathEscape(p.topic))
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
