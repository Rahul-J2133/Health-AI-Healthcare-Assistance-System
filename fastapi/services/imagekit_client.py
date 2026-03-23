"""
services/imagekit_client.py — Single ImageKit instance shared across the app.

The SDK had a major breaking change in v5.0.0:
  - Old (< v5): ImageKit(private_key=..., public_key=..., url_endpoint=...)
  - New (>= v5): ImageKit(private_key=...) only — public_key and url_endpoint
                 are no longer constructor arguments.
  - Upload method also changed:
      Old: imagekit.upload_file(file=..., file_name=..., options={...})
      New: imagekit.files.upload(file=..., file_name=..., folder=..., tags=...)

This module auto-detects which version is installed and initialises correctly.
Set IMAGEKIT_PRIVATE_KEY in your .env file.
"""
from functools import lru_cache
from imagekitio import ImageKit
from config import get_settings
import inspect


@lru_cache()
def get_imagekit() -> ImageKit:
    s = get_settings()

    # Detect SDK version by inspecting constructor signature
    init_params = inspect.signature(ImageKit.__init__).parameters

    if "public_key" in init_params:
        # Old SDK (< v5): requires all three keys
        return ImageKit(
            private_key=s.imagekit_private_key,
            public_key=s.imagekit_public_key,
            url_endpoint=s.imagekit_url_endpoint,
        )
    else:
        # New SDK (>= v5): only private_key, reads from env automatically
        return ImageKit(private_key=s.imagekit_private_key)


def upload_file(imagekit: ImageKit, file_data, file_name: str, folder: str, tags: list):
    """
    Version-agnostic upload wrapper.
    Handles the method rename between SDK v4 (upload_file) and v5 (files.upload).
    Returns the response object — access .url on it for the CDN URL.
    """
    if hasattr(imagekit, "files"):
        # SDK >= v5
        return imagekit.files.upload(
            file=file_data,
            file_name=file_name,
            folder=folder,
            tags=tags,
        )
    else:
        # SDK < v5
        return imagekit.upload_file(
            file=file_data,
            file_name=file_name,
            options={
                "folder": folder,
                "is_private_file": False,
                "tags": tags,
            },
        )