#!/bin/bash

KAFKA_CONNECT_HOST="kafka-connect"
KAFKA_CONNECT_PORT="8083"
CONNECTOR_FILE="/connectors/mqtt-connector.json"

echo "Waiting for Kafka Connect to be fully ready..."

until [ $(curl -s -o /dev/null -w "%{http_code}" http://${KAFKA_CONNECT_HOST}:${KAFKA_CONNECT_PORT}/connectors) -eq 200 ]; do
  echo "Connect API  is up but /connectors is not ready yet."
  sleep 5
done

echo "Kafka Connect is ready! Registering connector..."

curl -X POST -H "Content-Type: application/json" \
     --data @${CONNECTOR_FILE} \
     http://${KAFKA_CONNECT_HOST}:${KAFKA_CONNECT_PORT}/connectors

echo -e "\nConnector registration attempt complete."