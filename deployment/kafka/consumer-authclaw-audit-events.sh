#!/usr/bin/env sh
set -eu

kafka-console-consumer \
  --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" \
  --topic "${AUTHCLAW_AUDIT_TOPIC:-authclaw-audit-events}" \
  --from-beginning
