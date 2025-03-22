# -*- coding: utf-8 -*-
"""
@File    :   download_image.py
@Time    :   2025/03/22 22:25:59
@Author  :   tyqqj
@Version :   1.0
@Contact :   tyqqj0@163.com
@Desc    :   None
"""

import os
import requests
from urllib.parse import urlparse

code = {
    "success": 0,
    "error": 1,
}


def download_image(image_url, save_path):
    """
    Download an image from a URL and save it to the specified path.
    
    Args:
        image_url (str): The URL of the image to download
        save_path (str): The path where the image should be saved
    
    Returns:
        str: The path where the image was saved
    
    Raises:
        Exception: If the download fails or the image cannot be saved
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Send a GET request to the image URL
        response = requests.get(image_url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Save the image to the specified path
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return code["success"]
    
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to download image from {image_url}: {str(e)}")
    except IOError as e:
        raise Exception(f"Failed to save image to {save_path}: {str(e)}")


def download_image_auto_filename(image_url, save_dir):
    """
    Download an image from a URL and save it to the specified directory,
    automatically generating a filename from the URL.
    
    Args:
        image_url (str): The URL of the image to download
        save_dir (str): The directory where the image should be saved
    
    Returns:
        str: The path where the image was saved
    """
    # Extract filename from URL
    parsed_url = urlparse(image_url)
    filename = os.path.basename(parsed_url.path)
    
    # If no filename could be extracted or it has no extension, use a default
    if not filename or '.' not in filename:
        filename = 'downloaded_image.jpg'
    
    # Create the full save path
    save_path = os.path.join(save_dir, filename)
    
    # Download the image
    return download_image(image_url, save_path)

