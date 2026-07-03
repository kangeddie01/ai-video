import base64
import io
import sys
from pathlib import Path
from PIL import Image

from config import getOpenAIClient


SUPPORTED_IMAGE_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}


def generate_image(image_prompt: str, out_path: str, size: tuple) -> None:
    size_x, size_y = size
    client = getOpenAIClient()

    requested_size = f"{size_x}x{size_y}"
    if requested_size in SUPPORTED_IMAGE_SIZES:
        api_size = requested_size
    else:
        aspect = float(size_x) / float(size_y) if size_y != 0 else 1.0
        if abs(aspect - 1.0) < 0.15:
            api_size = "1024x1024"
        elif aspect > 1.0:
            api_size = "1536x1024"
        else:
            api_size = "1024x1536"

    try:
        result = client.images.generate(
            model="gpt-image-1",
            prompt=image_prompt,
            size=api_size,
        )
    except Exception as e:
        print("API request failed:", e)
        sys.exit(1)

    b64 = result.data[0].b64_json
    try:
        image_bytes = base64.b64decode(b64)
    except Exception as e:
        print("Failed to decode image data:", e)
        sys.exit(1)

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    except Exception as e:
        print("Failed to load image data into PIL:", e)
        sys.exit(1)

    if img.size != (size_x, size_y):
        try:
            img = img.resize((size_x, size_y), resample=Image.LANCZOS)
        except Exception as e:
            print("Failed to resize image:", e)
            sys.exit(1)

    out_dir = Path(out_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        img.convert("RGB").save(out_path)
    except Exception as e:
        print("Failed to save image to disk:", e)
        sys.exit(1)

    print(f"Wrote image to {out_path}")


if __name__ == "__main__":
  #  generate_image("anime style, happy family eating dinner, warm lighting")
    generate_image("", "resources/images/box1.png", 1920, 1080)
