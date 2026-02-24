import os
from pyspark.sql import SparkSession
from utils.config_loader import load_config
from utils.schema_loader import load_iot_schema
from jobs.kafka_stream_reader import KafkaStreamReader
from jobs.stream_parser import StreamParser
from jobs.stream_writer import ConsoleWriter
from jobs.stream_writer import MongoWriter
from jobs.aggregator import TumblingWindowAggregator
from pyspark.sql.functions import col, from_unixtime, concat_ws

"""The entry point for the job of spark streaming, it only contains the aggregation of data from a temporal window
for testing purpose the temporal window is 1 minute"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONF_PATH = os.path.join(BASE_DIR, "configuration", "spark.conf")
SCHEMA_PATH = os.path.join(BASE_DIR, "configuration", "schema.conf")

config = load_config(CONF_PATH)

KAFKA_BOOTSTRAP = config.get("KAFKA", "bootstrap_servers")
KAFKA_TOPIC = config.get("KAFKA", "topic")
KAFKA_OFFSET = config.get("KAFKA", "startingOffsets")
MONGO_URI = config.get("MONGO", "uri")
WINDOW_SIZE = config.get("AGGREGATION", "window_size")
iot_schema = load_iot_schema(SCHEMA_PATH)

spark = (
    SparkSession.builder
    .appName("HeatMapSparkProcessor")
    .config("spark.mongodb.write.connection.uri", MONGO_URI)
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")
reader = KafkaStreamReader(KAFKA_BOOTSTRAP, KAFKA_TOPIC, KAFKA_OFFSET)
parser = StreamParser(iot_schema)
#writer = ConsoleWriter()
aggregator = TumblingWindowAggregator(window_duration=WINDOW_SIZE)
#writer = MongoWriter("building_iot", "iot_metrics")
aggr_writer = MongoWriter("building_iot","aggr_iot_metrics") # writer for the aggregated data
dataframe_kafka = reader.read_stream(spark)
dataframe_parsed = parser.parse(dataframe_kafka)
console_query = ConsoleWriter().write(dataframe_parsed)

#Ho aggiunto una colonna timestamp che mi serve per il watermark che altrimenti mi crea problemi nell'aggregation
dataframe_with_ts = dataframe_parsed.withColumn("event_time", col("ts"))

WATERMARK_DURATION = "10 seconds"
dataframe_watermarked = dataframe_with_ts.withWatermark("event_time", WATERMARK_DURATION)
dataframe_aggr = aggregator.aggregate(dataframe_watermarked)
#query = writer.write(dataframe_parsed)
query_agg = aggr_writer.write(dataframe_aggr, output_mode="append")

#query.awaitTermination()
query_agg.awaitTermination()

console_query.awaitTermination()
