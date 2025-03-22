# -*- coding: utf-8 -*-
"""
@File    :   image_hosting_service.py
@Time    :   2025/03/22 20:00:58
@Author  :   tyqqj
@Version :   1.0
@Contact :   tyqqj0@163.com
@Desc    :   None
"""



import time

import numpy as np


import numpy as np
from PIL import Image
import io
import oss2

# Import default values from package initialization
from . import (
    default_access_key_id,
    default_access_key_secret,
    default_bucket_name,
    default_endpoint,
)


class AliyunOSSImageHost:
    def __init__(
        self,
        access_key_id=None,
        access_key_secret=None,
        bucket_name=None,
        endpoint=None,
    ):
        if access_key_id is None:
            access_key_id = default_access_key_id
        if access_key_secret is None:
            access_key_secret = default_access_key_secret
        if bucket_name is None:
            bucket_name = default_bucket_name
        if endpoint is None:
            endpoint = default_endpoint

        # 记录开始时间的文本
        self.start_time = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())

        self.auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(self.auth, endpoint, bucket_name)
        self.cache_url = None

    def upload_image(self, image_path, folder=None):
        print("Uploading image to Aliyun OSS...")
        file_key = image_path.split("/")[-1]
        if folder is not None:
            if isinstance(folder, str):
                if not folder.endswith("/"):
                    folder += "/"
                file_key = folder + file_key
            elif isinstance(folder, bool):
                if folder:
                    folder = self.start_time
                    file_key = folder + "/" + file_key
            else:
                raise ValueError(
                    "Invalid folder parameter. Expected a string or a boolean"
                )
        result = self.bucket.put_object_from_file(file_key, image_path)
        # 假设原始的endpoint可能包含'http://'
        if "http://" in self.bucket.endpoint:
            bucket_endpoint = self.bucket.endpoint.replace("http://", "")

        # 或者如果包含'https://'
        elif "https://" in self.bucket.endpoint:
            bucket_endpoint = self.bucket.endpoint.replace("https://", "")

        if result.status == 200:
            self.cache_url = f"http://{self.bucket.bucket_name}.{bucket_endpoint}/{file_key}"
            return self.cache_url
        else:
            return None

    def upload_numpy_array(self, array: np.array, file_name=None, folder=None):
        """
        将NumPy数组转换为图像并上传到OSS。
        :param array: NumPy二维数组
        :param file_name: 保存在OSS上的文件名
        :return: 图片在OSS上的URL或上传失败时返回None
        """
        print("Uploading image to Aliyun OSS...")
        if file_name is None:
            timett = str(int(time.time()))
            file_name = f"numpy_array_{timett}.png"
        elif ".png" not in file_name:
            file_name = file_name + ".png"
        # 确保数组是二维的
        if array.ndim != 2:
            raise ValueError("Only 2D arrays are supported.")

        if folder is not None:
            if isinstance(folder, str):
                if not folder.endswith("/"):
                    folder += "/"
                file_name = folder + file_name
            elif isinstance(folder, bool):
                if folder:
                    folder = self.start_time
                    file_name = folder + "/" + file_name
            else:
                raise ValueError(
                    "Invalid folder parameter. Expected a string or a boolean"
                )

        # 将NumPy数组转换为Pillow图像
        image = Image.fromarray(np.uint8(array))

        # 将图像保存到内存中的文件对象
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        img_byte_arr = img_byte_arr.getvalue()

        # 上传到OSS
        result = self.bucket.put_object(file_name, img_byte_arr)
        # 假设原始的endpoint可能包含'http://'
        if "http://" in self.bucket.endpoint:
            bucket_endpoint = self.bucket.endpoint.replace("http://", "")

        # 或者如果包含'https://'
        elif "https://" in self.bucket.endpoint:
            bucket_endpoint = self.bucket.endpoint.replace("https://", "")
        if result.status == 200:
            self.cache_url = f"http://{self.bucket.bucket_name}.{bucket_endpoint}/{file_name}"
            return self.cache_url
        else:
            return None

    def get_cache_url(self):
        return self.cache_url
