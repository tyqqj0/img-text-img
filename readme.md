
# Image-Text-Image Conversion Tool

This tool provides functionality to process images and texts in a bidirectional manner:
- Generate text descriptions from images (image → text)
- Generate images from text descriptions (text → image)

The tool maintains directory structures throughout conversions, making it easy to process batches of images or texts while preserving their organization.

## Table of Contents
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Environment Setup](#environment-setup)
- [API Key Setup](#api-key-setup)
- [Usage](#usage)
- [Author](#author)

## Project Structure
```
.
├── data/
│   ├── real/      # Source images directory
│   ├── text/      # Generated text descriptions directory
│   └── output/    # Generated images directory
├── utils/
│   ├── download_image.py
│   ├── text_to_image.py
|   └── ...
├── main.py        # Main execution script
├── keys.json      # API keys configuration
└── README.md
```

## Configuration
The application uses a configuration dictionary in `main.py` with the following parameters:

```python
config = {
    "override_text_prompt": False,   # Whether to override existing text files
    "override_output_image": True,   # Whether to override existing image files
    "real_image_path": "./data/real", # Path to the source images
    "text_image_path": "./data/text", # Path to the generated text descriptions
    "output_path": "./data/output",   # Path to the generated images
    "text_prompt": "What is the main content of the image? Please generate a detailed prompt to create an image, following the format of artistic style + subject description, for example: ..."
}
```

You can modify these settings according to your needs:
- Set `override_text_prompt` to `True` to regenerate existing text descriptions
- Set `override_output_image` to `True` to regenerate existing images
- Customize the `text_prompt` to get different types of image descriptions

## Environment Setup

Install required packages using pip:

```bash
# Install the volcengine SDK for ARK runtime
pip install -U volcengine-python-sdk[ark]

# Install the volcengine Python SDK
pip install --user volcengine
```

## API Key Setup

You need three API keys for this application, corresponding to Volcengine, ARK, and Aliyun OSS. Create a `keys.json` file with the following structure:

```json
{
    "oss": {
        "access_key_id": "aliyun_access_key_id",
        "access_key_secret": "aliyun_access_key_secret",
        "bucket_name": "aliyun_bucket_name",
        "endpoint": "aliyun_endpoint"  // Example: oss-cn-beijing.aliyuncs.com
    },
    "ark": {
        "api_key": "volc_ark_api_key"
    },
    "volc": {
        "ak": "volc_ak",
        "sk": "volc_sk"
    }
}
```

### How to obtain the API keys:

#### ARK API Key
Get your API key for the doubao-1-5-vision-pro-32k model from [Volcengine ARK Console](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-1-5-vision-pro-32k&projectName=undefined).

#### Volcengine API Key
Get your API key from the [Volcengine IAM Console](https://console.volcengine.com/iam/identitymanage/user).

#### Aliyun OSS API Key
Get your API key from the [Aliyun OSS Console](https://oss.console.aliyun.com/overview).

## Usage

### Running the Application
1. Ensure your images are placed in the `./data/real` directory with any folder structure you want to maintain
2. Run the main script:
   ```
   python main.py
   ```
3. You'll be prompted to choose an action:
   - Option 1: Generate text descriptions from images
   - Option 2: Generate images from text descriptions

### Process Flow
**Image to Text Conversion:**
- Images from `./data/real` will be processed
- Text descriptions will be saved to `./data/text` with the same directory structure
- Files will be skipped if they exist and `override_text_prompt` is `False`

**Text to Image Conversion:**
- Text files from `./data/text` will be processed
- Generated images will be saved to `./data/output` with the same directory structure
- Files will be skipped if they exist and `override_output_image` is `False`

## Author
tyqqj0@gmail.com
