import os
# Configure PaddlePaddle memory allocation flags before importing paddle
os.environ["FLAGS_fraction_of_gpu_memory_to_use"] = "0.08"
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
# Disable oneDNN (MKL-DNN) to avoid its strict stride/alignment requirements
# that cause broadcast shape mismatches on arbitrary input sizes.
os.environ["FLAGS_use_mkldnn"] = "0"

import paddle
from paddleocr import PaddleOCR
from src.core.config import settings
from src.core.logger import logger


def get_device() -> str:
    device = "cpu"
    logger.info(f"PaddleOCR using device: {device}")
    return device


def init_ocr_engine() -> PaddleOCR:
    logger.info("Initializing PaddleOCR engine...")
    device = get_device()

    # NOTE: use_doc_orientation_classify and use_doc_unwarping are disabled on
    # CPU because their oneDNN sub-models require input dimensions to be strict
    # multiples of their stride and fail with a broadcast-dimension-mismatch
    # (or Tensor-not-initialized / segfault) on arbitrary image sizes.
    # The VLM downstream handles orientation correction well enough without them.
    ocr = PaddleOCR(
        lang=settings.OCR_LANG,
        ocr_version=settings.OCR_VERSION,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=settings.OCR_USE_TEXTLINE_ORIENTATION,
        device=device,
        text_rec_score_thresh=settings.OCR_TEXT_REC_SCORE_THRESH,
    )
    return ocr
