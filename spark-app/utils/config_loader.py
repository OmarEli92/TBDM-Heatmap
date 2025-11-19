import os
import configparser

"""Utility method used to read the variables and data associated inside configuration files"""

def load_config(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    return config