# -*- coding: utf-8 -*-
"""
@File    :   __init__.py
@Time    :   2025/03/22 20:50:25
@Author  :   tyqqj
@Version :   1.0
@Contact :   tyqqj0@163.com
@Desc    :   None
"""


import json
import os

# Load OSS credentials from configuration file
file_path = os.path.abspath(__file__)
# Get the directory of the current file, then go up one level to the parent directory
parent_dir = os.path.dirname(os.path.dirname(file_path))
# Load the keys.json file from the parent directory
oss_dict = json.load(open(os.path.join(parent_dir, "keys.json"), "r"))

# Default OSS parameters with clearer names
default_access_key_id = oss_dict["oss"]["access_key_id"]
default_access_key_secret = oss_dict["oss"]["access_key_secret"]
default_bucket_name = oss_dict["oss"]["bucket_name"]
default_endpoint = oss_dict["oss"]["endpoint"]

default_ark_api_key = oss_dict["ark"]["api_key"]

default_volc_ak = oss_dict["volc"]["ak"]
default_volc_sk = oss_dict["volc"]["sk"]

# Import at the end to avoid circular imports
from .image_hosting_service import AliyunOSSImageHost
from .image_to_text import ImageToTextGenerator
from .text_to_image import TextToImageGenerator
