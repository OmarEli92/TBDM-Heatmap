from pyspark.sql import SparkSession
from pyspark.sql.functions import col, stddev, count, lit, current_timestamp, when
from influxdb_client import InfluxDBClient
import pandas as pd
import warnings

# --- CONFIGURAZIONE ---
INFLUX_URL = "http://influxdb:8086"
INFLUX_TOKEN = "my-influxdb-token"
INFLUX_ORG = "POLOA_org"
INFLUX_BUCKET = "temporal_datalake"
MONGO_URI = "mongodb://mongo:27017/building_iot.maintenance_alerts"


def main():
    # Inizializza Spark
    spark = (SparkSession.builder
             .appName("WeeklyHealthCheck")
             .config("spark.mongodb.write.connection.uri", MONGO_URI)
             .getOrCreate())

    # Inizializza Client InfluxDB
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

    # Query Flux:
    # 1. Range: Ultimi 7 giorni (-7d)
    # 2. Filter: Controlliamo solo la temperatura (spesso il sensore più critico)
    flux_query = f"""
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -7d)
          |> filter(fn: (r) => r._measurement == "temperature")
          |> pivot(rowKey:["_time"], columnKey: ["_measurement"], valueColumn: "_value")
    """

    print("=== [BATCH WEEKLY] Lettura dati settimanali da InfluxDB... ===")

    try:
        # Scarica i dati in Pandas
        pandas_df = client.query_api().query_data_frame(flux_query)
    except Exception as e:
        print(f"Errore InfluxDB: {e}")
        spark.stop()
        return

    if pandas_df.empty:
        print("=== [BATCH WEEKLY] Nessun dato trovato negli ultimi 7 giorni! ===")
        spark.stop()
        return

    # PULIZIA DATI (Identica al Daily Report)
    pandas_df = pandas_df.reset_index(drop=True)
    cols_to_drop = ["result", "table", "_start", "_stop", "_time"]
    pandas_df = pandas_df.drop(columns=[c for c in cols_to_drop if c in pandas_df.columns])

    print(f"=== [BATCH WEEKLY] Analisi su {len(pandas_df)} rilevazioni... ===")

    # Converti in Spark DataFrame
    df_influx = spark.createDataFrame(pandas_df)

    # --- LOGICA DI BUSINESS: Rilevamento Guasti ---

    # 1. Raggruppa per stanza
    # 2. Conta quanti dati sono arrivati (count)
    # 3. Calcola la deviazione standard (stddev) per vedere se il valore cambia
    df_stats = (df_influx
    .groupBy("building", "floor", "room")
    .agg(
        count("temperature").alias("msg_count"),
        stddev("temperature").alias("temp_stddev")
    )
    )

    # Definizione delle Soglie di Allarme
    # - LOW BATTERY/OFFLINE: Se in una settimana sono arrivati meno di 50 messaggi (assumendo invii frequenti)
    # - FROZEN SENSOR: Se la deviazione standard è 0 (il valore è identico al millesimo per una settimana)

    df_alerts = df_stats.filter(
        (col("msg_count") < 50) | (col("temp_stddev") == 0)
    ).withColumn("alert_date", current_timestamp())

    # Aggiungiamo una descrizione leggibile del problema
    df_alerts = df_alerts.withColumn(
        "issue_type",
        when(col("msg_count") < 50, lit("SENSOR_OFFLINE_OR_LOW_BATTERY"))
        .when(col("temp_stddev") == 0, lit("SENSOR_FROZEN_VALUE"))
        .otherwise(lit("UNKNOWN_ANOMALY"))
    )

    # Scrittura su MongoDB (Solo se ci sono problemi)
    alert_count = df_alerts.count()
    print(f"=== [BATCH WEEKLY] Trovati {alert_count} sensori problematici. ===")

    if alert_count > 0:
        df_alerts.show()  # Mostra nel log per debug
        df_alerts.write.format("mongodb").mode("append").save()
        print("Alert salvati su MongoDB.")
    else:
        print("Tutti i sensori sembrano sani.")

    spark.stop()


if __name__ == "__main__":
    main()