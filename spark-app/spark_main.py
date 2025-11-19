import os
from pyspark.sql import SparkSession
from utils.config_loader import load_config
from utils.schema_loader import load_iot_schema
from jobs.kafka_stream_reader import KafkaStreamReader
from jobs.stream_parser import StreamParser
from jobs.stream_writer import ConsoleWriter
from jobs.stream_writer import MongoWriter

"""The starting point for the jobs of spark streaming"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONF_PATH = os.path.join(BASE_DIR, "configuration", "spark.conf")
SCHEMA_PATH = os.path.join(BASE_DIR, "configuration", "schema.conf")

config = load_config(CONF_PATH)

KAFKA_BOOTSTRAP = config.get("KAFKA", "bootstrap_servers")
KAFKA_TOPIC = config.get("KAFKA", "topic")
KAFKA_OFFSET = config.get("KAFKA", "startingOffsets")
MONGO_URI = config.get("MONGO", "uri")

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
writer = MongoWriter("building_iot", "iot_metrics")
dataframe_kafka = reader.read_stream(spark)
dataframe_parsed = parser.parse(dataframe_kafka)
query = writer.write(dataframe_parsed)
query.awaitTermination()
