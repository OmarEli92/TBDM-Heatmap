import os
import json
import paho.mqtt.client as mqtt
from confluent_kafka import Producer


MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "/POLOA/#")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "iot_sensors")

# 1. Configurazione Producer Kafka
kafka_config = {'bootstrap.servers': KAFKA_BROKER}
producer = Producer(kafka_config)


def delivery_report(err, msg):
    """ Callback per confermare l'invio a Kafka """
    if err is not None:
        print(f"Errore consegna Kafka: {err}")
    else:
        pass  # Messaggio inviato con successo


# 2. Callback MQTT: Cosa fare quando arriva un messaggio dai sensori
def on_message(client, userdata, msg):
    try:
        # Decodifica il payload JSON proveniente da mqtt_publish.py
        data = json.loads(msg.payload.decode())


        # Invia a Kafka
        producer.produce(
            KAFKA_TOPIC,
            key=data.get("sensor_id"),
            value=json.dumps(data),
            callback=delivery_report
        )

        # Forza l'invio (polling per gestire i callback)
        producer.poll(0)
        print(f"Inoltrato a Kafka: {data.get('sensor_id')} da topic MQTT: {msg.topic}")

    except Exception as e:
        print(f"Errore nel bridge: {e}")


# 3. Setup MQTT Client
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_message = on_message

if __name__ == "__main__":
    print(f"ETL Bridge IN avviato. MQTT: {MQTT_BROKER} -> Kafka: {KAFKA_BROKER}")

    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.subscribe(MQTT_TOPIC)

    # Resta in ascolto per sempre
    mqtt_client.loop_forever()