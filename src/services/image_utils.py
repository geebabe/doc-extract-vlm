from PIL import Image, ImageOps

def pad_to_stride(image: Image.Image, stride: int = 32) -> Image.Image:
    """
    Pad image dimensions to the nearest multiple of `stride`.

    PaddleOCR's oneDNN kernels (used by PP-OCRv5 with doc unwarping /
    orientation classify) require spatial dimensions divisible by 32.
    Arbitrary sizes such as 144 or 216 cause a broadcast shape mismatch
    inside the C++ runtime, which surfaces as either a FatalError /
    segfault or an InvalidArgumentError.
    """
    w, h = image.size
    pad_w = (stride - w % stride) % stride
    pad_h = (stride - h % stride) % stride
    if pad_w == 0 and pad_h == 0:
        return image
    # Pad right + bottom with black (0) so the image content is unaffected
    return ImageOps.expand(image, border=(0, 0, pad_w, pad_h), fill=0)


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image before OCR and VLM.
    - Upscales low-res images to ~1024px on the long side.
    - Downscales very large images (>2048px) to ~2048px on the long side.
    - Pads dimensions to the nearest multiple of 32 for PaddleOCR compatibility.
    """
    width, height = image.size
    longest_side = max(width, height)

    if longest_side < 1024:
        scale = 1024.0 / longest_side
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    elif longest_side > 2048:
        scale = 2048.0 / longest_side
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    image = pad_to_stride(image, stride=32)

    return image
