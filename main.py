# -*- coding: utf-8 -*-
"""
@File    :   main.py
@Time    :   2025/03/22 20:50:34
@Author  :   tyqqj
@Version :   1.0
@Contact :   tyqqj0@163.com
@Desc    :   None
"""


import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Sequence, Tuple

import utils
from utils.download_image import download_image

try:
    from tqdm import tqdm  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    tqdm = None

config: Dict[str, Any] = {
    "override_text_prompt": False,
    "override_output_image": False,
    "real_image_path": "./data/real",
    "text_image_path": "./data/text",
    "output_path": "./data/output",
    "width": 1920,
    "height": 1080,
    "text_prompt": "图片主要讲了什么?请生成一个详细的提示词以用来生成图像，请按照艺术风格+主体描述的格式生成描述，例如:艺术风格：采用写实且带有复古色调的摄影风格，画面整体色调偏暖棕色系，具有一定的颗粒感，营造出自然质朴的氛围。\n主体描述：画面主体是一只站立在地面上的鹿，鹿的毛色为棕色，带有一些深色斑纹，头部转向侧面，两只耳朵竖立，耳朵上有橙色标记。鹿拥有一对形态优美且粗壮的鹿角，向上弯曲伸展。它的四肢修长，蹄子呈蓝绿色。背景是一片开阔的土地，地面上散布着一些干枯的树枝和小石块，远处有一些低矮的绿色植被。",
    "max_workers": min(8, (os.cpu_count() or 4)),
    "enable_progress_bar": True,
}

SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
_THREAD_LOCAL = threading.local()


class _DummyProgress:
    def __init__(self, total=None, desc=None, unit=None):
        self.total = total
        self.desc = desc
        self.unit = unit
        if desc and total:
            print(f"{desc} - total tasks: {total}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def update(self, n=1):
        return None


def _get_image_host():
    host = getattr(_THREAD_LOCAL, "image_host", None)
    if host is None:
        host = utils.AliyunOSSImageHost()
        _THREAD_LOCAL.image_host = host
    return host


def _get_image_to_text_generator():
    generator = getattr(_THREAD_LOCAL, "image_to_text_generator", None)
    if generator is None:
        generator = utils.ImageToTextGenerator()
        _THREAD_LOCAL.image_to_text_generator = generator
    return generator


def _get_text_to_image_generator():
    generator = getattr(_THREAD_LOCAL, "text_to_image_generator", None)
    if generator is None:
        generator = utils.TextToImageGenerator(width=config["width"], height=config["height"])
        _THREAD_LOCAL.text_to_image_generator = generator
    return generator


def _normalize_relative_path(relative_path: str) -> str:
    return "" if relative_path == "." else relative_path


def _normalize_description(description) -> str:
    if isinstance(description, str):
        return description.strip()
    if isinstance(description, list):
        parts = []
        for chunk in description:
            if isinstance(chunk, dict) and "text" in chunk:
                parts.append(str(chunk["text"]))
            else:
                parts.append(str(chunk))
        return "\n".join(part.strip() for part in parts if part).strip()
    return "" if description is None else str(description)


def _get_progress_bar(total: int, desc: str):
    if config.get("enable_progress_bar", True) and tqdm is not None:
        return tqdm(total=total, desc=desc, unit="file")
    if config.get("enable_progress_bar", True) and tqdm is None:
        print("Install `tqdm` for richer progress display (pip install tqdm).")
    return _DummyProgress(total=total, desc=desc, unit="file")


def _run_tasks_concurrently(tasks, worker, desc: str):
    total = len(tasks)
    if total == 0:
        print(f"No pending tasks for {desc}.")
        return

    max_workers = max(1, int(config.get("max_workers", 1)))
    errors = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, task): task for task in tasks}
        with _get_progress_bar(total, desc) as progress:
            for future in as_completed(futures):
                success, identifier, message = future.result()
                if not success:
                    errors.append((identifier, message))
                progress.update(1)

    if errors:
        print(f"{len(errors)} task(s) failed during {desc}:")
        for identifier, message in errors:
            print(f" - {identifier}: {message}")
    else:
        print(f"All {desc} tasks completed successfully.")


def generate_text_from_image(image_path: str) -> str:
    image_host = _get_image_host()
    image_url = image_host.upload_image(image_path, folder=True)
    if not image_url:
        raise RuntimeError(f"Failed to upload image: {image_path}")
    image_to_text = _get_image_to_text_generator()
    return image_to_text.generate(image_url, config["text_prompt"])


def _collect_image_tasks(base_real_path: str):
    tasks = []
    for root, _, files in os.walk(base_real_path):
        for file in files:
            if not file.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS):
                continue
            real_image_path = os.path.join(root, file)
            relative_path = _normalize_relative_path(os.path.relpath(root, base_real_path))
            text_dir = os.path.join(config["text_image_path"], relative_path)
            text_filename = os.path.splitext(file)[0] + ".txt"
            text_path = os.path.join(text_dir, text_filename)
            if os.path.exists(text_path) and not config["override_text_prompt"]:
                continue
            tasks.append((real_image_path, text_path))
    return tasks


def _process_image_to_text_task(task):
    real_image_path, text_path = task
    try:
        description = generate_text_from_image(real_image_path)
        normalized_description = _normalize_description(description)
        os.makedirs(os.path.dirname(text_path), exist_ok=True)
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(normalized_description)
        return True, text_path, None
    except Exception as exc:
        return False, text_path, str(exc)


def generate_text_from_images(base_real_path: str):
    if not os.path.isdir(base_real_path):
        print(f"Directory does not exist: {base_real_path}")
        return
    tasks = _collect_image_tasks(base_real_path)
    print(f"Images requiring text prompts: {len(tasks)}")
    _run_tasks_concurrently(tasks, _process_image_to_text_task, "Images -> Text")


def _collect_text_tasks(base_text_path: str):
    tasks = []
    for root, _, files in os.walk(base_text_path):
        for file in files:
            if not file.lower().endswith(".txt"):
                continue
            text_file_path = os.path.join(root, file)
            relative_path = _normalize_relative_path(os.path.relpath(root, base_text_path))
            output_dir = os.path.join(config["output_path"], relative_path)
            image_filename = os.path.splitext(file)[0] + ".jpg"
            image_path = os.path.join(output_dir, image_filename)
            if os.path.exists(image_path) and not config["override_output_image"]:
                continue
            tasks.append((text_file_path, image_path))
    return tasks


def _process_text_to_image_task(task):
    text_file_path, image_path = task
    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            text_content = f.read().strip()
        if not text_content:
            raise ValueError("Text prompt is empty.")
        text_to_image = _get_text_to_image_generator()
        image_url = text_to_image.generate(text_content)
        if download_image(image_url, image_path) != 0:
            raise RuntimeError(f"Failed to download generated image from {image_url}")
        return True, image_path, None
    except Exception as exc:
        return False, text_file_path, str(exc)


def generate_images_from_text(base_text_path: str):
    if not os.path.isdir(base_text_path):
        print(f"Directory does not exist: {base_text_path}")
        return
    tasks = _collect_text_tasks(base_text_path)
    print(f"Text files requiring image generation: {len(tasks)}")
    _run_tasks_concurrently(tasks, _process_text_to_image_task, "Text -> Images")


if __name__ == "__main__":
    action = input(
        "Please input the action you want to perform: \n(1): generate_text_from_images\n(2): generate_images_from_text\n"
    )
    if action == "1":
        print("Generating text from images...")
        generate_text_from_images(config["real_image_path"])
    elif action == "2":
        print("Generating images from text...")
        generate_images_from_text(config["text_image_path"])
    else:
        print("Invalid action")
