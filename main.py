# -*- coding: utf-8 -*-
"""
@File    :   main.py
@Time    :   2025/03/22 20:50:34
@Author  :   tyqqj
@Version :   1.0
@Contact :   tyqqj0@163.com
@Desc    :   None
"""


import io
import json
import math
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional, Tuple

import utils
from utils.download_image import download_image

try:
    from tqdm import tqdm  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    tqdm = None

config: Dict[str, Any] = {
    "override_text_prompt": False,
    "override_output_image": False,
    "override_metadata": False,
    "real_image_path": "./data/real",
    "text_image_path": "./data/text",
    "output_path": "./data/output",
    "meta_path": "./data/meta",
    "width": 1920,
    "height": 1080,
    "image_size_mode": "fixed",  # options: "fixed", "match_metadata"
    "ark_fixed_size": "2K",
    "ark_model_name": "doubao-seedream-4-0-250828",
    "ark_base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "ark_sequential_mode": "auto",
    "ark_sequential_max_images": 1,
    "text_prompt": "图片主要讲了什么?请生成一个详细的提示词以用来生成图像，请按照艺术风格+主体描述的格式生成描述，例如:艺术风格：采用写实且带有复古色调的摄影风格，画面整体色调偏暖棕色系，具有一定的颗粒感，营造出自然质朴的氛围。\n主体描述：画面主体是一只站立在地面上的鹿，鹿的毛色为棕色，带有一些深色斑纹，头部转向侧面，两只耳朵竖立，耳朵上有橙色标记。鹿拥有一对形态优美且粗壮的鹿角，向上弯曲伸展。它的四肢修长，蹄子呈蓝绿色。背景是一片开阔的土地，地面上散布着一些干枯的树枝和小石块，远处有一些低矮的绿色植被。",
    "max_workers": min(8, (os.cpu_count() or 4)),
    "enable_progress_bar": True,
}

SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
MAX_IMAGE_TOTAL_PIXELS = 40_000_000
MAX_IMAGE_FILE_SIZE_BYTES = 10 * 1024 * 1024
ARK_MIN_LONG_SIDE = 1280
ARK_MIN_SHORT_SIDE = 720
ARK_MAX_SIDE = 4096
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
        generator = utils.TextToImageGenerator(
            base_url=config["ark_base_url"],
            model_name=config["ark_model_name"],
            default_size=config.get("ark_fixed_size") or f'{config["width"]}x{config["height"]}',
            sequential_mode=config.get("ark_sequential_mode", "auto"),
            sequential_max_images=config.get("ark_sequential_max_images", 1),
            watermark=config.get("ark_watermark", False),
        )
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


def _prepare_image_for_upload(image_path: str) -> Tuple[str, Optional[Callable[[], None]]]:
    file_size = os.path.getsize(image_path)
    try:
        from PIL import Image  # type: ignore[import]
    except ImportError:
        if file_size > MAX_IMAGE_FILE_SIZE_BYTES:
            print(
                "Install Pillow to automatically downscale oversized images for text generation "
                "(pip install pillow)."
            )
        return image_path, None

    with Image.open(image_path) as img:
        width, height = img.size
        total_pixels = width * height
        needs_resize = total_pixels > MAX_IMAGE_TOTAL_PIXELS
        needs_reencode = file_size > MAX_IMAGE_FILE_SIZE_BYTES

        if not needs_resize and not needs_reencode:
            return image_path, None

        scale_factor = 1.0
        if needs_resize:
            scale_factor = math.sqrt(MAX_IMAGE_TOTAL_PIXELS / float(total_pixels))
        new_width = max(1, int(width * min(1.0, scale_factor)))
        new_height = max(1, int(height * min(1.0, scale_factor)))

        resized = img.convert("RGB")
        if new_width != width or new_height != height:
            resample_filter = getattr(getattr(Image, "Resampling", Image), "LANCZOS", getattr(Image, "LANCZOS"))
            resized = resized.resize((new_width, new_height), resample_filter)

        buffer = io.BytesIO()
        quality = 95
        while True:
            buffer.seek(0)
            buffer.truncate(0)
            resized.save(buffer, format="JPEG", optimize=True, quality=quality)
            if buffer.tell() <= MAX_IMAGE_FILE_SIZE_BYTES or quality <= 50:
                break
            quality -= 5

        fd, temp_path = tempfile.mkstemp(prefix="img2txt_", suffix=".jpg")
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(buffer.getvalue())

    def cleanup():
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass

    return temp_path, cleanup


def _record_image_metadata(image_path: str, meta_output_path: str) -> None:
    try:
        from PIL import Image  # type: ignore[import]
    except ImportError:
        print("Install Pillow to record image dimensions (pip install pillow).")
        return

    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except Exception as exc:
        raise RuntimeError(f"Failed to read image metadata for {image_path}: {exc}") from exc

    os.makedirs(os.path.dirname(meta_output_path), exist_ok=True)
    metadata = {"width": width, "height": height}
    with open(meta_output_path, "w", encoding="utf-8") as meta_file:
        json.dump(metadata, meta_file, ensure_ascii=False)


def _load_metadata_dimensions(meta_path: Optional[str]) -> Optional[Tuple[int, int]]:
    if not meta_path or not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as meta_file:
            metadata = json.load(meta_file)
        width = int(metadata.get("width", 0))
        height = int(metadata.get("height", 0))
        if width > 0 and height > 0:
            return width, height
    except Exception as exc:
        print(f"Failed to read metadata from {meta_path}: {exc}")
    return None


def _normalize_metadata_dimensions(width: int, height: int) -> Tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Metadata width/height must be positive integers.")

    w = float(width)
    h = float(height)

    def scale_dimensions(scale_factor: float):
        nonlocal w, h
        w *= scale_factor
        h *= scale_factor

    longest = max(w, h)
    if longest > ARK_MAX_SIDE:
        scale_dimensions(ARK_MAX_SIDE / longest)

    longest = max(w, h)
    if longest < ARK_MIN_LONG_SIDE:
        scale_dimensions(ARK_MIN_LONG_SIDE / longest)

    shortest = min(w, h)
    if shortest < ARK_MIN_SHORT_SIDE:
        scale_dimensions(ARK_MIN_SHORT_SIDE / shortest)

    longest = max(w, h)
    if longest > ARK_MAX_SIDE:
        scale_dimensions(ARK_MAX_SIDE / longest)

    normalized_width = int(round(w))
    normalized_height = int(round(h))
    normalized_width = min(max(normalized_width, ARK_MIN_SHORT_SIDE), ARK_MAX_SIDE)
    normalized_height = min(max(normalized_height, ARK_MIN_SHORT_SIDE), ARK_MAX_SIDE)

    return normalized_width, normalized_height


def _resolve_generation_size(meta_path: Optional[str]) -> str:
    fallback_size = config.get("ark_fixed_size") or f'{config["width"]}x{config["height"]}'
    mode = config.get("image_size_mode", "fixed")
    if mode != "match_metadata":
        return fallback_size

    metadata_dimensions = _load_metadata_dimensions(meta_path)
    if not metadata_dimensions:
        print(f"Metadata not found or invalid for {meta_path}, fallback to fixed size.")
        return fallback_size

    try:
        width, height = _normalize_metadata_dimensions(*metadata_dimensions)
    except ValueError as exc:
        print(f"Metadata invalid for {meta_path}: {exc}, fallback to fixed size.")
        return fallback_size

    return f"{width}x{height}"


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
    prepared_path, cleanup = _prepare_image_for_upload(image_path)
    try:
        image_host = _get_image_host()
        image_url = image_host.upload_image(prepared_path, folder=True)
        if not image_url:
            raise RuntimeError(f"Failed to upload image: {image_path}")
        image_to_text = _get_image_to_text_generator()
        return image_to_text.generate(image_url, config["text_prompt"])
    finally:
        if cleanup is not None:
            cleanup()


def _collect_metadata_tasks(base_real_path: str):
    tasks = []
    for root, _, files in os.walk(base_real_path):
        for file in files:
            if not file.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS):
                continue
            real_image_path = os.path.join(root, file)
            relative_path = _normalize_relative_path(os.path.relpath(root, base_real_path))
            meta_dir = os.path.join(config["meta_path"], relative_path)
            meta_filename = os.path.splitext(file)[0] + ".json"
            meta_path = os.path.join(meta_dir, meta_filename)
            if os.path.exists(meta_path) and not config["override_metadata"]:
                continue
            tasks.append((real_image_path, meta_path))
    return tasks


def _process_metadata_task(task):
    real_image_path, meta_path = task
    try:
        _record_image_metadata(real_image_path, meta_path)
        return True, meta_path, None
    except Exception as exc:
        return False, real_image_path, str(exc)


def _build_metadata_index():
    meta_root = config.get("meta_path")
    if not meta_root or not os.path.isdir(meta_root):
        print(f"Metadata root directory does not exist: {meta_root}")
        return

    index = {}
    for root, _, files in os.walk(meta_root):
        for file in files:
            if not file.lower().endswith(".json"):
                continue
            if file == "all_metadata.json":
                continue

            meta_path = os.path.join(root, file)
            try:
                with open(meta_path, "r", encoding="utf-8") as meta_file:
                    data = json.load(meta_file)
            except Exception as exc:
                print(f"Failed to include metadata file {meta_path} in index: {exc}")
                continue

            relative_meta_path = os.path.relpath(meta_path, meta_root)
            relative_meta_path = _normalize_relative_path(relative_meta_path)
            index[relative_meta_path] = data

    index_path = os.path.join(meta_root, "all_metadata.json")
    try:
        with open(index_path, "w", encoding="utf-8") as index_file:
            json.dump(index, index_file, ensure_ascii=False, indent=2)
        print(f"Metadata index written to {index_path} ({len(index)} items).")
    except Exception as exc:
        print(f"Failed to write metadata index file {index_path}: {exc}")


def generate_metadata_for_images(base_real_path: str):
    if not os.path.isdir(base_real_path):
        print(f"Directory does not exist: {base_real_path}")
        return
    tasks = _collect_metadata_tasks(base_real_path)
    print(f"Images requiring metadata: {len(tasks)}")
    _run_tasks_concurrently(tasks, _process_metadata_task, "Images -> Metadata")
    _build_metadata_index()


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
            base_name = os.path.splitext(file)[0]
            image_filename = base_name + ".jpg"
            image_path = os.path.join(output_dir, image_filename)
            prefixed_image_filename = image_filename if image_filename.startswith("F_") else f"F_{image_filename}"
            prefixed_image_path = os.path.join(output_dir, prefixed_image_filename)
            meta_dir = os.path.join(config["meta_path"], relative_path)
            meta_filename = base_name + ".json"
            meta_path = os.path.join(meta_dir, meta_filename)
            if (
                (os.path.exists(image_path) or os.path.exists(prefixed_image_path))
                and not config["override_output_image"]
            ):
                continue
            tasks.append((text_file_path, image_path, meta_path))
    return tasks


def _process_text_to_image_task(task):
    text_file_path, image_path, meta_path = task
    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            text_content = f.read().strip()
        if not text_content:
            raise ValueError("Text prompt is empty.")
        text_to_image = _get_text_to_image_generator()
        generation_size = _resolve_generation_size(meta_path)
        image_url = text_to_image.generate(text_content, size=generation_size)
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


def prefix_output_images(base_output_path: str):
    if not os.path.isdir(base_output_path):
        print(f"Directory does not exist: {base_output_path}")
        return

    renamed = 0
    already_prefixed = 0
    collisions = 0
    for root, _, files in os.walk(base_output_path):
        for file in files:
            if not file.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS):
                continue
            if file.startswith("F_"):
                already_prefixed += 1
                continue
            source_path = os.path.join(root, file)
            target_filename = f"F_{file}"
            target_path = os.path.join(root, target_filename)
            if os.path.exists(target_path):
                collisions += 1
                print(f"Target already exists for {source_path}, skipping rename.")
                continue
            try:
                os.rename(source_path, target_path)
                renamed += 1
            except OSError as exc:
                collisions += 1
                print(f"Failed to rename {source_path}: {exc}")

    print(
        f"Prefixing completed. Renamed: {renamed}, already prefixed: {already_prefixed}, collisions/errors: {collisions}"
    )


if __name__ == "__main__":
    action = input(
        "Please input the action you want to perform: \n"
        "(1): generate_metadata_for_images\n"
        "(2): generate_text_from_images\n"
        "(3): generate_images_from_text\n"
        "(4): prefix_output_images\n"
        "(5): run_full_pipeline\n"
    )
    if action == "1":
        print("Generating metadata from images...")
        generate_metadata_for_images(config["real_image_path"])
    elif action == "2":
        print("Generating text from images...")
        generate_text_from_images(config["real_image_path"])
    elif action == "3":
        print("Generating images from text...")
        generate_images_from_text(config["text_image_path"])
    elif action == "4":
        print("Prefixing output images with F_ if needed...")
        prefix_output_images(config["output_path"])
    elif action == "5":
        print("Running full pipeline...")
        generate_metadata_for_images(config["real_image_path"])
        generate_text_from_images(config["real_image_path"])
        generate_images_from_text(config["text_image_path"])
    else:
        print("Invalid action")
