#!/usr/bin/env sh
set -eu

kafka-topics \
  --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" \
  --create \
  --if-not-exists \
  --topic "${AUTHCLAW_AUDIT_TOPIC:-authclaw-audit-events}" \
  --partitions "${AUTHCLAW_AUDIT_TOPIC_PARTITIONS:-3}" \
  --replication-factor "${AUTHCLAW_AUDIT_TOPIC_REPLICATION_FACTOR:-1}"
