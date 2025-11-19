from pyspark.sql import SparkSession

class KafkaStreamReader:
    def __init__(self, bootstrap, topic, offset):
        self.bootstrap = bootstrap
        self.topic = topic
        self.offset = offset
        
    def read_stream(self, spark):
        dataframe_raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", self.bootstrap)
        .option("subscribe", self.topic)
        .option("startingOffsets", self.offset)
        .load()
        )
        return dataframe_raw