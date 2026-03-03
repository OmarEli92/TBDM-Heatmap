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
for testing purpose the temporal window is 10 minutes"""

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
aggregator = TumblingWindowAggregator(window_duration=WINDOW_SIZE, watermark="10 seconds")
aggr_writer = MongoWriter("building_iot", "aggr_iot_metrics")
dataframe_kafka = reader.read_stream(spark)
dataframe_parsed = parser.parse(dataframe_kafka)
dataframe_with_ts = dataframe_parsed.withColumn("event_time", col("ts"))
dataframe_aggr = aggregator.aggregate(dataframe_with_ts)
query_agg = aggr_writer.write(dataframe_aggr, output_mode="append")
query_agg.awaitTermination()
