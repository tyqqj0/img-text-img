# coding:utf-8
# -*- coding: utf-8 -*-
"""
@File    :   text_to_image.py
@Time    :   2025/03/22 21:35:19
@Author  :   tyqqj
@Version :   1.0
@Contact :   tyqqj0@163.com
@Desc    :   None
"""


from __future__ import print_function

import time

from volcengine.visual.VisualService import VisualService


class TextToImageGenerator:
    def __init__(self, width=512, height=512, ak=None, sk=None, max_retries=3):
        self.visual_service = VisualService()
        if ak is None:
            from . import default_volc_ak

            ak = default_volc_ak
        if sk is None:
            from . import default_volc_sk

            sk = default_volc_sk
        # print(ak, sk)
        self.visual_service.set_ak(ak)
        self.visual_service.set_sk(sk)
        self.width = width
        self.height = height
    
    def _generate(self, text):
        form = {
            "req_key": "high_aes_general_v21_L",
            "prompt": text,
            "model_version": "general_v2.1_L",
            "req_schedule_conf": "general_v20_9B_pe",
            "llm_seed": -1,
            "seed": -1,
            "scale": 3.5,
            "ddim_steps": 25,
            "width": self.width,
            "height": self.height,
            "use_sr": True,
            "sr_seed": -1,
            "sr_strength": 0.4,
            "sr_scale": 3.5,
            "sr_steps": 20,
            "is_only_sr": False,
            "return_url": True,
        }

        resp = self.visual_service.cv_process(form)

        if resp.get("code") == 10000:
            # print(resp)
            image_urls = resp.get("data").get("image_urls")
            if len(image_urls) > 0:
                return image_urls[0]
            else:
                raise Exception("No image url returned")
        else:
            print(resp)
            raise Exception(resp.get("message"))

    def generate(self, text):
        for _ in range(self.max_retries):
            try:
                return self._generate(text)
            except Exception as e:
                print(e)
                p
                time.sleep(1)
        raise Exception("Failed to generate image")
