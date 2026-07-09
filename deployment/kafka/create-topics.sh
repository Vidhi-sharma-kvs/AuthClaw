#!/usr/bin/env sh
set -eu

create_topic() {
  kafka-topics \
    --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" \
    --create \
    --if-not-exists \
    --topic "$1" \
    --partitions "$2" \
    --replication-factor "$3" \
    --config "retention.ms=$4" \
    --config "compression.type=producer"
}

create_topic "${AUTHCLAW_AUDIT_TOPIC:-authclaw-audit-events}" "${AUTHCLAW_AUDIT_TOPIC_PARTITIONS:-3}" "${AUTHCLAW_AUDIT_TOPIC_REPLICATION_FACTOR:-1}" "${AUTHCLAW_AUDIT_TOPIC_RETENTION_MS:-604800000}"
create_topic "${KAFKA_ANALYTICS_TOPIC:-authclaw-analytics-events}" "${KAFKA_ANALYTICS_TOPIC_PARTITIONS:-3}" "${KAFKA_ANALYTICS_TOPIC_REPLICATION_FACTOR:-1}" "${KAFKA_ANALYTICS_TOPIC_RETENTION_MS:-604800000}"
create_topic "${KAFKA_DLQ_TOPIC:-authclaw-dead-letter-events}" "${KAFKA_DLQ_TOPIC_PARTITIONS:-1}" "${KAFKA_DLQ_TOPIC_REPLICATION_FACTOR:-1}" "${KAFKA_DLQ_TOPIC_RETENTION_MS:-1209600000}"
