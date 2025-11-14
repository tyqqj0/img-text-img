# -*- coding: utf-8 -*-
"""
@File    :   image_to_text.py
@Time    :   2025/03/22 20:50:02
@Author  :   tyqqj
@Version :   1.0
@Contact :   tyqqj0@163.com
@Desc    :   None
"""

from volcenginesdkarkruntime import Ark



class ImageToTextGenerator:
    def __init__(self, api_key=None):
        if api_key is None:
            from . import default_ark_api_key
            self.api_key = default_ark_api_key
        else:
            self.api_key = api_key
        self.client = Ark(api_key=self.api_key)

    def generate(self, image_url: str, text_prompt=None) -> str:
        if text_prompt is None:
            text_prompt = "图片主要讲了什么?"
        resp = self.client.chat.completions.create(
            model="doubao-seed-1-6-flash-250828",
            messages=[
                {
                    "content": [
                        {"text": text_prompt, "type": "text"},
                        {
                            "image_url": {
                                "url": image_url
                            },
                            "type": "image_url",
                        },
                    ],
                    "role": "user",
                }
            ],
        )
        return resp.choices[0].message.content
