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


from __future__ import annotations

import os
import time
from typing import Any, Optional, Sequence

_ark_import_error: Optional[ImportError]
try:
    from volcenginesdkarkruntime import Ark  # type: ignore[import]
    from volcenginesdkarkruntime.types.images.images import SequentialImageGenerationOptions  # type: ignore[import]
except ImportError as exc:  # pragma: no cover - optional dependency
    Ark = None  # type: ignore[assignment]
    SequentialImageGenerationOptions = None  # type: ignore[assignment]
    _ark_import_error = exc
else:
    _ark_import_error = None


class TextToImageGenerator:
    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        default_size: str,
        sequential_mode: str = "auto",
        sequential_max_images: int = 1,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_interval_seconds: float = 1.5,
        watermark: bool = True,
        response_format: str = "url",
    ) -> None:
        if Ark is None or SequentialImageGenerationOptions is None:
            raise ImportError(
                "volcenginesdkarkruntime is required for TextToImageGenerator. "
                "Install it via `pip install volcenginesdkarkruntime`."
            ) from _ark_import_error

        from . import default_ark_api_key

        resolved_api_key = api_key or os.environ.get("ARK_API_KEY") or default_ark_api_key
        if not resolved_api_key:
            raise RuntimeError("Missing Ark API key. Set ARK_API_KEY or provide api_key explicitly.")

        assert Ark is not None  # narrow for type checkers
        self.client: Any = Ark(base_url=base_url, api_key=resolved_api_key)
        self.model_name = model_name
        self.default_size = default_size
        self.sequential_mode = sequential_mode
        self.sequential_max_images = sequential_max_images
        self.max_retries = max(1, max_retries)
        self.retry_interval_seconds = retry_interval_seconds
        self.response_format = response_format
        self.watermark = watermark

    def _prepare_payload(
        self,
        prompt: str,
        size: Optional[str],
        reference_images: Optional[Sequence[str]],
    ) -> dict:
        assert SequentialImageGenerationOptions is not None
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "size": size or self.default_size,
            "sequential_image_generation": self.sequential_mode,
            "sequential_image_generation_options": SequentialImageGenerationOptions(
                max_images=self.sequential_max_images
            ),
            "response_format": self.response_format,
            "watermark": self.watermark,
        }
        if reference_images:
            payload["image"] = list(reference_images)
        return payload

    @staticmethod
    def _extract_first_image_url(response) -> str:
        data = getattr(response, "data", None)
        if not data:
            raise RuntimeError("Ark response does not contain image data.")
        first_entry = data[0]
        url = getattr(first_entry, "url", None)
        if not url:
            raise RuntimeError("Ark response image entry is missing a URL.")
        return url

    def generate(
        self,
        prompt: str,
        *,
        size: Optional[str] = None,
        reference_images: Optional[Sequence[str]] = None,
    ) -> str:
        payload = self._prepare_payload(prompt, size, reference_images)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.images.generate(**payload)
                return self._extract_first_image_url(response)
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_interval_seconds)

        raise RuntimeError(f"Failed to generate image after {self.max_retries} attempts: {last_error}")
