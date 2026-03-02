import configparser
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, stddev, count, lit, when
from influxdb_client import InfluxDBClient
import pandas as pd

# --- CONFIGURATION ---
config = configparser.ConfigParser()
config.read('/app/configuration/spark.conf')
INFLUX_URL = config.get('INFLUXDB', 'url', fallback="http://influxdb:8086")
MONGO_BASE_URI = config.get('MONGO', 'uri', fallback="mongodb://mongo:27017")
MONGO_DB = config.get('MONGO', 'database', fallback="building_iot")
MONGO_COLLECTION = config.get('MONGO_BATCH', 'collection_weekly', fallback="maintenance_alerts")
MONGO_URI = f"{MONGO_BASE_URI}/{MONGO_DB}.{MONGO_COLLECTION}"

INFLUX_TOKEN = os.getenv("INFLUX_ADMIN_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")


if not INFLUX_TOKEN:
    raise ValueError("Fatal error: INFLUX_ADMIN_TOKEN not set in environment variables!")


def main():
    # Initialize Spark
    spark = (SparkSession.builder
             .appName("WeeklyHealthCheck")
             .config("spark.mongodb.write.connection.uri", MONGO_URI)
             .getOrCreate())

    # Initialize InfluxDB Client
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

    # Correct Flux query:
    # 1. Range: All historical data (start: 0)
    # 2. Filter: Correct table name and filter only on temperature
    flux_query = f"""
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: 0)
          |> filter(fn: (r) => r["_measurement"] == "iot_telemetry")
          |> filter(fn: (r) => r["sensor_type"] == "temperature")
          |> pivot(rowKey:["_time"], columnKey: ["sensor_type"], valueColumn: "_value")
    """

    print("=== [BATCH WEEKLY] Reading weekly data from InfluxDB... ===")

    try:
        # Download data in Pandas
        result = client.query_api().query_data_frame(flux_query)
    except Exception as e:
        print(f"InfluxDB error: {e}")
        spark.stop()
        return

    if type(result) is list and len(result) == 0:
        print("=== [BATCH WEEKLY] No data found! ===")
        spark.stop()
        return

    if type(result) is list:
        pandas_df = pd.concat(result, ignore_index=True)
    else:
        pandas_df = result

    if pandas_df is None or pandas_df.empty:
        print("=== [BATCH WEEKLY] No data found in DataFrame! ===")
        spark.stop()
        return

    # --- DATA CLEANING & WEEK EXTRACTION ---
    if pandas_df.index.name == '_time' or '_time' in pandas_df.index.names:
        pandas_df = pandas_df.reset_index()
    else:
        pandas_df = pandas_df.reset_index(drop=True)

    cols_to_drop = ["result", "table", "_start", "_stop"]
    pandas_df = pandas_df.drop(columns=[c for c in cols_to_drop if c in pandas_df.columns])

    if '_time' in pandas_df.columns:
        pandas_df['report_week'] = pd.to_datetime(pandas_df['_time']).dt.strftime('%Y-W%V')
        pandas_df = pandas_df.drop(columns=['_time'])

    # Ensure temperature exists and is numeric
    if 'temperature' not in pandas_df.columns:
        pandas_df['temperature'] = pd.NA

    pandas_df['temperature'] = pd.to_numeric(pandas_df['temperature'], errors='coerce')
    pandas_df = pandas_df.fillna(0.0)

    print(f"=== [BATCH WEEKLY] Analysis on {len(pandas_df)} readings... ===")

    # Convert to Spark DataFrame
    df_influx = spark.createDataFrame(pandas_df)

    # --- SPARK BUSINESS LOGIC: Failure Detection ---

    # Handle NaN values (the fake 0.0)
    df_influx = df_influx.withColumn(
        "temperature",
        when(col("temperature") == 0.0, lit(None)).otherwise(col("temperature"))
    )

    # 1. Group by WEEK, building, floor and room
    # 2. Count how many data points arrived (count)
    # 3. Calculate standard deviation (stddev)
    df_stats = (df_influx
    .groupBy("report_week", "building", "floor", "room")
    .agg(
        count("temperature").alias("msg_count"),
        stddev("temperature").alias("temp_stddev")
    )
    )

    # Definition of Alert Thresholds
    # - LOW BATTERY: < 50 messages per week
    # - FROZEN SENSOR: stddev == 0 (locked value) or NaN (only one message received)
    df_alerts = df_stats.filter(
        (col("msg_count") < 50) | (col("temp_stddev") == 0) | col("temp_stddev").isNull()
    )

    # Add a readable description
    df_alerts = df_alerts.withColumn(
        "issue_type",
        when(col("msg_count") < 50, lit("SENSOR_OFFLINE_OR_LOW_BATTERY"))
        .when((col("temp_stddev") == 0) | col("temp_stddev").isNull(), lit("SENSOR_FROZEN_VALUE"))
        .otherwise(lit("UNKNOWN_ANOMALY"))
    )

    # Write to MongoDB
    alert_count = df_alerts.count()
    print(f"=== [BATCH WEEKLY] Found {alert_count} maintenance alerts. ===")

    if alert_count > 0:
        df_alerts.show(truncate=False)  # Display first 20 alerts in log
        df_alerts.write.format("mongodb").mode("append").save()
        print("=== [BATCH WEEKLY] Alerts saved to MongoDB in 'maintenance_alerts' collection. ===")
    else:
        print("=== [BATCH WEEKLY] All sensors appear healthy. No alerts saved. ===")

    spark.stop()


if __name__ == "__main__":
    main()