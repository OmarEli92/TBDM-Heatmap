
"""This class actually print the data in the console, used for testing execution of spark jobs"""
class ConsoleWriter:
    def write(self, dataframe):
        return (
            dataframe.writeStream
            .outputMode("append")
            .format("console")
            .option("truncate", False)
            .start()
        )
        
"""This class is responsible for writing the incoming data from the spark cluster inside MongoDB"""
class MongoWriter:
    def __init__(self, database, collection):
        self.database = database
        self.collection = collection

    def write(self, dataframe, output_mode="append"):
        return (
            dataframe.writeStream
            .format("mongodb")
            .option("database", self.database)
            .option("collection", self.collection)
            .option("checkpointLocation", f"/tmp/mongo-checkpoint-{self.database}-{self.collection}") 
            .outputMode(output_mode) 
            .start()
        )