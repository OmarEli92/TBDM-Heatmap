from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, when, lit, current_timestamp

# --- CONFIGURAZIONE ---
# Assicurati che il token sia lo stesso del docker-compose!
INFLUX_URL = "http://influxdb:8086"
INFLUX_TOKEN = "my-influxdb-token"
INFLUX_ORG = "POLOA_org"
INFLUX_BUCKET = "temporal_datalake"
MONGO_URI = "mongodb://mongo:27017/building_iot.daily_summaries"

def main():
    spark = (SparkSession.builder
             .appName("DailyComfortReport")
             .config("spark.mongodb.write.connection.uri", MONGO_URI)
             .getOrCreate())

    # Query Flux: Prende dati delle ultime 24h, filtra per temp e co2
    flux_query = f"""
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "temperature" or r._measurement == "co2")
          |> pivot(rowKey:["_time"], columnKey: ["_measurement"], valueColumn: "_value")
    """

    # Lettura da InfluxDB
    df_influx = (spark.read
        .format("com.github.fsanaulla.influxdb.DataFrame")
        .option("db.url", INFLUX_URL)
        .option("db.token", INFLUX_TOKEN)
        .option("db.organization", INFLUX_ORG)
        .option("db.query", flux_query)
        .load())

    # Aggregazione e Calcolo
    df_report = (df_influx
        .groupBy("building", "floor", "room")
        .agg(avg("temperature").alias("avg_temp"), avg("co2").alias("avg_co2"))
    )

    df_enriched = df_report.withColumn(
        "comfort_status",
        when((col("avg_temp") >= 19) & (col("avg_temp") <= 24) & (col("avg_co2") < 800), lit("GOOD"))
        .otherwise(lit("POOR"))
    ).withColumn("report_date", current_timestamp())

    # Scrittura su MongoDB
    df_enriched.write.format("mongodb").mode("append").save()
    spark.stop()

if __name__ == "__main__":
    main()