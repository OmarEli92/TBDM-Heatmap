# TBDM-Heatmap
**Project for the exam of Technologies for Big Data Management**

This project implements a complete IoT data processing pipeline. It simulates sensor data ingestion into **ThingsBoard**, processes telemetry through a Big Data stack (**Kafka, Spark, InfluxDB, MongoDB**), and closes the loop by sending aggregated analytics back to the dashboard.

---

## Architecture & Data Flow

The system supports two ingestion strategies via Docker profiles:

1.  **Polling Profile**: An ETL process polls ThingsBoard every **5 seconds**. It uses a **Watermark** (storing the last timestamp per device) to ensure data consistency and avoid duplicates.
2.  **Rule-Chain Profile**: ThingsBoard uses a custom Rule Chain to push data directly to a **FastAPI** endpoint. This endpoint transforms the data and forwards it to Kafka.

### The Pipeline:
* **Simulation**: Data is read from a dataset and sent to ThingsBoard.
* **Ingestion**: Data is captured by the chosen profile (ETL Polling or Rule-Chain/FastAPI) and converted into the Kafka payload.
* **Persistence (Raw)**: Raw data is persisted into **InfluxDB**.
* **Stream Processing**: **Apache Spark** listens to the `iot_sensors` Kafka topic, performing windowed aggregations (**Avg, Min, Max, StdDev, Variance**, etc.) per device.
* **Persistence (Aggregated)**: Results are stored in **MongoDB**.
* **Closing the Loop**: A secondary ETL polls MongoDB and updates ThingsBoard with the calculated aggregations.

---

## Installation & Setup

### 1. Start Docker Containers
Choose **one** of the following profiles to start the stack:

**For Polling-based extraction:**
> docker compose --profile polling up -d --build

**For Rule-Chain based extraction:**
> docker compose --profile rulechain up -d --build

**IMPORTANT - If using the Rule-Chain profile:**
1. Open ThingsBoard UI.
2. Import the `root_rule_chain.json` file into the Rule Chains section.
3. Set it as the **Root Rule Chain**.


### 2. Initialize Data
After the containers are up and running, execute these scripts in order to set up the environment:

1.  **Generate and copy InfluxDB Token**: execute this command in the terminal `docker exec -it influxdb influx auth list`. Then copy the token in the environment variable "INFLUX_ADMIN_TOKEN"
2.  **Generate Mapping**: Create the building/sensor map from the dataset.
    > python mapping_geojson_initializer.py
3.  **Provision Devices**: Map the devices from the generated file to ThingsBoard.
    > python map_devices_to_thingsboard.py
4.  **Load Initial Data**: Project the first hour of sensor data to ThingsBoard.
    > python initialize_data_on_thingsboard.py

*Note: To avoid overwhelming the memory  only the first hour of data for each device is sent during initialization.*

---

## Service Endpoints &  Credentials

Once the stack is running, you can access the various services using the following local endpoints and default credentials:

| Service | Endpoint | Credentials / Details |
| :--- | :--- | :--- |
| **ThingsBoard UI** | [http://localhost:9191](http://localhost:9191) | **User**: `tenant@thingsboard.org` <br> **Pass**: `tenant` |
| **InfluxDB UI** | [http://localhost:8086](http://localhost:8086) | **User**: `poloa_admin` <br> **Pass**: `password` <br> **Org**: `POLOA_org` <br> **Bucket**: `temporal_datalake` |
| **Spark Master UI** | [http://localhost:8080](http://localhost:8080) | *No authentication required* |
| **Kafka Connect REST** | [http://localhost:8083](http://localhost:8083) | *API for connector management* |
| **MongoDB** | `mongodb://localhost:27017` | *No auth* <br> **Database**: `building_iot` <br> **Collection**: `aggr_iot_metrics` |
| **Kafka Broker** | `localhost:29092` | *External listener for local debugging* |
| **MQTT Broker** | `localhost:1883` | *Eclipse Mosquitto port* |

---

## Technical Specifications

### Data Payload
The internal data format used across the pipeline (Kafka/Spark) is as follows:
{
    "timestamp": "timestamp_value",
    "building": "building_name",
    "floor": "floor_level",
    "room": "room_id",
    "sensor_type": "type",
    "sensor_id": 123,
    "value": 25.5
}

### Technology Stack
* **ThingsBoard**: IoT Platform & Visualization.
* **FastAPI**: Transformation endpoint (Rule-Chain profile).
* **Apache Kafka**: Message Broker.
* **Apache Spark**: Real-time Analytics.
* **InfluxDB**: Time-series Database (Raw data).
* **MongoDB**: Document Store (Aggregated data).
* **MQTT**: Connectivity protocol.

##  Authors 

* **[Omar El Idrissi ]**   
* **[Lorenzo Gezzi ]** 
* **[Nicolas Rossi ]**  