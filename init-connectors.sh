#!/bin/bash

KAFKA_CONNECT_HOST="kafka-connect"
KAFKA_CONNECT_PORT="8083"
CONNECTOR_FILE="/connectors/mqtt-connector.json"

echo "Waiting for Kafka Connect"

until curl -s http://${KAFKA_CONNECT_HOST}:${KAFKA_CONNECT_PORT}/connectors; do
  echo "Connect API not ready yet. Sleeping..."
  sleep 5
done


curl -X POST -H "Content-Type: application/json" \
     --data @${CONNECTOR_FILE} \
     http://${KAFKA_CONNECT_HOST}:${KAFKA_CONNECT_PORT}/connectors

echo "Connector registration complete."

