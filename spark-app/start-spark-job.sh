#!/bin/bash
set -e

# Attende Kafka Connect
echo "Waiting for Kafka Connect..."
until curl -s http://connect:8083/ | grep -q 'Kafka Connect'; do
  sleep 5
done

# Registra il connettore MQTT
curl -X POST -H "Content-Type: application/json" \
     --data "@connectors/mqtt-connector.json" \
     http://connect:8083/connectors || true

exec /etc/confluent/docker/run
