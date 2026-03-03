import configparser
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, when, lit, to_date
from influxdb_client import InfluxDBClient
import pandas as pd
import warnings

# --- CONFIGURATION ---
config = configparser.ConfigParser()
config.read('/app/configuration/spark.conf')
INFLUX_URL = config.get('INFLUXDB', 'url', fallback="http://influxdb:8086")
MONGO_BASE_URI = config.get('MONGO', 'uri', fallback="mongodb://mongo:27017")
MONGO_DB = config.get('MONGO', 'database', fallback="building_iot")
MONGO_COLLECTION = config.get('MONGO_BATCH', 'collection_daily', fallback="daily_summaries")
MONGO_URI = f"{MONGO_BASE_URI}/{MONGO_DB}.{MONGO_COLLECTION}"

INFLUX_TOKEN = os.getenv("INFLUX_ADMIN_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")


if not INFLUX_TOKEN:
    raise ValueError("Fatal error: INFLUX_ADMIN_TOKEN not set in environment variables!")


def main():
    # Initialize Spark
    spark = (SparkSession.builder
             .appName("DailyComfortReport")
             .config("spark.mongodb.write.connection.uri", MONGO_URI)
             .getOrCreate())

    # Initialize InfluxDB Client (Native Python Library)
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

    # Flux Query:
    # 1. Get the last 24h
    # 2. Pivot: Transform rows "temperature" and "co2" into columns
    flux_query = f"""
            from(bucket: "{INFLUX_BUCKET}")
              |> range(start: -24h) 
              |> filter(fn: (r) => r["_measurement"] == "iot_telemetry")
              |> filter(fn: (r) => r["sensor_type"] == "temperature" or r["sensor_type"] == "co2")
              |> pivot(rowKey:["_time"], columnKey: ["sensor_type"], valueColumn: "_value")
        """

    print("=== [BATCH] Reading from InfluxDB in progress... ===")

    # Execute the query
    try:
        result = client.query_api().query_data_frame(flux_query)
    except Exception as e:
        print(f"InfluxDB connection error: {e}")
        spark.stop()
        return

    # --- FIX FOR PANDAS LIST ---
    # If InfluxDB returns an empty list (no data)
    if type(result) is list and len(result) == 0:
        print("=== [BATCH] No data found! ===")
        spark.stop()
        return

    # If InfluxDB returns a list of DataFrames (multiple tables), merge them
    if type(result) is list:
        pandas_df = pd.concat(result, ignore_index=True)
    else:
        pandas_df = result

    # Now that we are sure pandas_df is a single DataFrame, use .empty
    if pandas_df is None or pandas_df.empty:
        print("=== [BATCH] No data found in the DataFrame! ===")
        spark.stop()
        return
    # --- END FIX ---

    # DATA CLEANING
    pandas_df = pandas_df.reset_index(drop=True)

    # Ensure 'temperature' and 'co2' columns exist
    if 'temperature' not in pandas_df.columns:
        pandas_df['temperature'] = pd.NA
    if 'co2' not in pandas_df.columns:
        pandas_df['co2'] = pd.NA

    # Force conversion to numbers (float) and if there are errors (e.g. strange strings) make them NaN
    pandas_df['temperature'] = pd.to_numeric(pandas_df['temperature'], errors='coerce')
    pandas_df['co2'] = pd.to_numeric(pandas_df['co2'], errors='coerce')

    # Fill "holes" (NaN) with a safe null value, or eliminate them.
    # The best option before passing to Spark is to ignore NaNs during calculation
    pandas_df = pandas_df.fillna(0.0)  # Temporarily replace holes with 0.0 to avoid crash during conversion

    cols_to_drop = ["result", "table", "_start", "_stop",]
    # Drop only columns that actually exist in the DF
    pandas_df = pandas_df.drop(columns=[c for c in cols_to_drop if c in pandas_df.columns])

    if '_time' in pandas_df.columns:
        pandas_df['_time'] = pandas_df['_time'].astype(str)

    print(f"=== [BATCH] Downloaded {len(pandas_df)} records. Converting to Spark... ===")

    # Convert Pandas DataFrame -> Spark DataFrame
    # Spark infers schema automatically (Building, Floor, Room, temperature, co2)
    df_influx = spark.createDataFrame(pandas_df)


    df_influx = df_influx.withColumn("report_date", to_date(col("_time")))

    # Replace fake zeros with real Spark NULLs, so the average will ignore empty cells
    df_influx = df_influx.withColumn(
        "temperature",
        when(col("temperature") == 0.0, lit(None)).otherwise(col("temperature"))
    )
    df_influx = df_influx.withColumn(
        "co2",
        when(col("co2") == 0.0, lit(None)).otherwise(col("co2"))
    )

    # Aggregation and Calculation
    df_report = (df_influx
    .groupBy("report_date", "building", "floor", "room")
    .agg(
        avg("temperature").alias("avg_temp"),
        avg("co2").alias("avg_co2")
    )
    )

    # Enrichment (Business Logic)
    df_enriched = df_report.withColumn(
        "comfort_status",
        when((col("avg_temp") >= 19) & (col("avg_temp") <= 24) & (col("avg_co2") < 800), lit("GOOD"))
        .otherwise(lit("POOR"))
    )

    # Write to MongoDB
    print("=== [BATCH] Writing report to MongoDB... ===")
    df_enriched.write.format("mongodb").mode("append").save()

    print("=== [BATCH] Completed successfully. ===")
    spark.stop()


if __name__ == "__main__":
    main()