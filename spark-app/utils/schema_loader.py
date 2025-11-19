from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType
from utils.config_loader import load_config

"""Utility method used to load the IoT schema from the configuration file"""
def load_iot_schema(configuration_path):
    config = load_config(configuration_path)
    fields = config.get("SCHEMA", "message_fields").split(",")
    #the mapping is necessary in order for spark to recognize the iot schema data that it  receives
    type_mapping = {"string": StringType(), "double": DoubleType(), "long": LongType()}
    schema = StructType([
        StructField(name.strip(), type_mapping[field_type.strip()], True)
        for name, field_type in (f.split(":") for f in fields)
    ])
    return schema