from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, when, lit, current_timestamp
from influxdb_client import InfluxDBClient
import pandas as pd
import warnings

# --- CONFIGURAZIONE ---
INFLUX_URL = "http://influxdb:8086"
INFLUX_TOKEN = "my-influxdb-token"
INFLUX_ORG = "POLOA_org"
INFLUX_BUCKET = "temporal_datalake"
MONGO_URI = "mongodb://mongo:27017/building_iot.daily_summaries"


def main():
    # Inizializza Spark
    spark = (SparkSession.builder
             .appName("DailyComfortReport")
             .config("spark.mongodb.write.connection.uri", MONGO_URI)
             .getOrCreate())

    # Inizializza Client InfluxDB (Libreria Python Nativa)
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

    # Query Flux:
    # 1. Prende le ultime 24h
    # 2. Pivot: Trasforma le righe "temperature" e "co2" in colonne
    flux_query = f"""
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "temperature" or r._measurement == "co2")
          |> pivot(rowKey:["_time"], columnKey: ["_measurement"], valueColumn: "_value")
    """

    print("=== [BATCH] Lettura da InfluxDB in corso... ===")

    # Esegue la query e mette i risultati in un DataFrame Pandas
    try:
        pandas_df = client.query_api().query_data_frame(flux_query)
    except Exception as e:
        print(f"Errore connessione InfluxDB: {e}")
        spark.stop()
        return

    # Se non ci sono dati, chiudi tutto
    if pandas_df.empty:
        print("=== [BATCH] Nessun dato trovato per le ultime 24h! ===")
        spark.stop()
        return

    # PULIZIA DATI
    # Rimuoviamo le colonne interne di InfluxDB che a Spark non servono
    # Nota: '_time' è spesso l'indice, resettiamo l'indice per sicurezza
    pandas_df = pandas_df.reset_index(drop=True)
    cols_to_drop = ["result", "table", "_start", "_stop", "_time"]
    # Droppa solo le colonne che esistono effettivamente nel DF
    pandas_df = pandas_df.drop(columns=[c for c in cols_to_drop if c in pandas_df.columns])

    print(f"=== [BATCH] Scaricati {len(pandas_df)} record. Conversione in Spark... ===")

    # Converti Pandas DataFrame -> Spark DataFrame
    # Spark inferisce lo schema automaticamente (Building, Floor, Room, temperature, co2)
    df_influx = spark.createDataFrame(pandas_df)

    # --- DA QUI IN POI È LOGICA SPARK PURA ---

    # Aggregazione e Calcolo
    df_report = (df_influx
    .groupBy("building", "floor", "room")
    .agg(
        avg("temperature").alias("avg_temp"),
        avg("co2").alias("avg_co2")
    )
    )

    # Arricchimento (Logica di Business)
    df_enriched = df_report.withColumn(
        "comfort_status",
        when((col("avg_temp") >= 19) & (col("avg_temp") <= 24) & (col("avg_co2") < 800), lit("GOOD"))
        .otherwise(lit("POOR"))
    ).withColumn("report_date", current_timestamp())

    # Scrittura su MongoDB
    print("=== [BATCH] Scrittura report su MongoDB... ===")
    df_enriched.write.format("mongodb").mode("append").save()

    print("=== [BATCH] Completato con successo. ===")
    spark.stop()


if __name__ == "__main__":
    main()