from pyspark.sql.functions import (
    window, col, count, avg, min, max, stddev, variance, expr, concat_ws, lit
)
import configparser
config = configparser.ConfigParser()
config.read('schema.conf')


class TumblingWindowAggregator:
    """For the metrics we  calculate the min, max, avg , the standard deviation, variaance ,
    the median and the percentile from which the data fall in, like 90%, 95 % and 99% """
    def __init__(self, window_duration="15 minutes"):
        self.window_duration = window_duration
        self.duration_label = f"{window_duration.split(' ')[0]}m"
    def aggregate(self, dataframe):
        dataframe_agg = (
            dataframe
            .groupBy(
                "sensor_id",
                "building",
                "floor",
                "room",
                "sensor_type",
                window("event_time", self.window_duration)
            )
            .agg(
                count("*").alias("count"),
                avg("value").alias("avg"),
                min("value").alias("min"),
                max("value").alias("max"),
                stddev("value").alias("stddev"),
                variance("value").alias("variance"),
                expr("percentile(value, 0.5)").alias("median"),
                expr("percentile(value, 0.90)").alias("p90"),
                expr("percentile(value, 0.95)").alias("p95"),
                expr("percentile(value, 0.99)").alias("p99")
            )
        )

        dataframe_agg = (
            dataframe_agg
            .withColumn("window_start", col("window.start"))
            .withColumn("window_end", col("window.end"))
            .drop("window")
        )

        dataframe_agg = dataframe_agg.withColumn(
            "_id",
            concat_ws("_", 
                #col("building"), 
                col("sensor_id"),
                lit("heatmap"),                
                lit(self.duration_label),
                col("window_start").cast("long")
            )
        )
        return dataframe_agg
