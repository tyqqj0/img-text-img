# -*- coding: utf-8 -*-
"""
@File    :   main.py
@Time    :   2025/03/22 20:50:34
@Author  :   tyqqj
@Version :   1.0
@Contact :   tyqqj0@163.com
@Desc    :   None
"""


import utils
import os

config = {
    "override_text_prompt": False,
    "override_output_image": False,
    "real_image_path": "./data/real",
    "text_image_path": "./data/text",
    "output_path": "./data/output",
    "text_prompt": "图片主要讲了什么?请生成一个详细的提示词以用来生成图像，请按照艺术风格+主体描述的格式生成描述，例如:艺术风格：采用写实且带有复古色调的摄影风格，画面整体色调偏暖棕色系，具有一定的颗粒感，营造出自然质朴的氛围。\n主体描述：画面主体是一只站立在地面上的鹿，鹿的毛色为棕色，带有一些深色斑纹，头部转向侧面，两只耳朵竖立，耳朵上有橙色标记。鹿拥有一对形态优美且粗壮的鹿角，向上弯曲伸展。它的四肢修长，蹄子呈蓝绿色。背景是一片开阔的土地，地面上散布着一些干枯的树枝和小石块，远处有一些低矮的绿色植被。",
}


def generate_text_from_image(image_path: str) -> str:
    image_host = utils.AliyunOSSImageHost()
    image_url = image_host.upload_image(image_path, folder=True)
    image_to_text = utils.ImageToTextGenerator()
    return image_to_text.generate(image_url, config["text_prompt"])


def generate_text_from_images(base_real_path: str):
    for root, dirs, files in os.walk(base_real_path):
        for file in files:
            print(f"Processing {file}")
            if file.lower().endswith((".png", ".jpg", ".jpeg")):
                real_image_path = os.path.join(root, file)

                # Generate relative path
                relative_path = os.path.relpath(root, base_real_path)

                # Create corresponding text directory
                text_dir = os.path.join(config["text_image_path"], relative_path)
                os.makedirs(text_dir, exist_ok=True)

                # Create text file path (same name with .txt extension)
                text_filename = os.path.splitext(file)[0] + ".txt"
                text_path = os.path.join(text_dir, text_filename)

                # Check if the text file already exists
                if os.path.exists(text_path) and not config["override_text_prompt"]:
                    print(f"Skipping existing text file: {text_filename}")
                    continue

                try:
                    # Generate text description
                    description = generate_text_from_image(real_image_path)

                    # Save description to file
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write(description)

                    print(f"Generated text: {text_path}\n")

                except Exception as e:
                    print(f"Error processing {real_image_path}: {str(e)}")


def generate_images_from_text(base_text_path: str):
    """
    Process all text files in the text directory, generate images from them,
    and save the images to the output directory with matching structure.

    Args:
        base_text_path (str): Base path to the text files directory
    """
    from utils.download_image import download_image

    text_to_image = utils.TextToImageGenerator()

    for root, dirs, files in os.walk(base_text_path):
        for file in files:
            print(f"Processing {file}")
            if file.lower().endswith(".txt"):
                text_file_path = os.path.join(root, file)

                # Generate relative path
                relative_path = os.path.relpath(root, base_text_path)

                # Create corresponding output directory
                output_dir = os.path.join(config["output_path"], relative_path)
                os.makedirs(output_dir, exist_ok=True)

                # Create image file path (change extension from .txt to .jpg)
                image_filename = os.path.splitext(file)[0] + ".jpg"
                image_path = os.path.join(output_dir, image_filename)

                # Check if the image file already exists
                if os.path.exists(image_path) and not config["override_output_image"]:
                    print(f"Skipping existing image file: {image_filename}")
                    continue

                try:
                    # Read text content
                    with open(text_file_path, "r", encoding="utf-8") as f:
                        text_content = f.read()

                    # Generate image from text
                    image_url = text_to_image.generate(text_content)

                    # Download and save the image
                    if download_image(image_url, image_path) == 0:
                        print(f"Generated and saved image: {image_path}\n")
                    else:
                        print(f"Failed to download image from {image_url}")

                except Exception as e:
                    print(f"Error processing {text_file_path}: {str(e)}")


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
