import cv2
import numpy as np
from PIL import Image, ImageOps

def deskew_id_card(image: Image.Image) -> Image.Image:
    """Deskews an ID card using text contours and minAreaRect."""
    img_np = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # Invert and threshold
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    
    # Dilate to connect text components into blocks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
    dilate = cv2.dilate(thresh, kernel, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(dilate, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    angles = []
    for c in contours:
        if cv2.contourArea(c) > 100:
            rect = cv2.minAreaRect(c)
            angle = rect[-1]
            # OpenCV minAreaRect returns angle in range [-90, 0)
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            angles.append(angle)
            
    if not angles:
        return image
        
    # Use median angle to avoid outliers
    median_angle = np.median(angles)
    
    if abs(median_angle) < 0.5:
        # Don't rotate if angle is very small
        return image
        
    (h, w) = img_np.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(img_np, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    return Image.fromarray(rotated)

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


def preprocess_image(image: Image.Image, route_key: str = "general") -> Image.Image:
    """
    Preprocess image before OCR and VLM.
    - Upscales low-res images to ~1024px on the long side.
    - Downscales very large images (>2048px) to ~2048px on the long side.
    - Pads dimensions to the nearest multiple of 32 for PaddleOCR compatibility.
    - Deskews ID cards.
    """
    width, height = image.size
    longest_side = max(width, height)

    if longest_side < 1024:
        # Upscale
        scale = 1024.0 / longest_side
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    elif longest_side > 2048:
        # Downscale
        scale = 2048.0 / longest_side
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    if route_key == "id_card":
        image = deskew_id_card(image)

    # Pad to stride-32 boundary required by PaddleOCR's oneDNN backend
    image = pad_to_stride(image, stride=32)

    return image
