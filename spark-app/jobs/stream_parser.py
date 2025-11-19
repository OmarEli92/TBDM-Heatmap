from pyspark.sql.functions import from_json, col, to_timestamp

class StreamParser:
    def __init__(self, schema):
        self.schema = schema
        
    def parse(self, dataframe):
        dataframe_json = dataframe.selectExpr("CAST(value AS STRING) AS json_str")
        dataframe_parsed = (
            dataframe_json
            .select(from_json(col("json_str"), self.schema).alias("data"))
            .select("data.*")
            .withColumn("ts", col("timestamp").cast("timestamp"))
        )
        return dataframe_parsed