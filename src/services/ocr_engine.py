import paddle
from paddleocr import PaddleOCR
from src.core.config import settings
from src.core.logger import logger

def get_device() -> str:
    device = "gpu:0" if paddle.is_compiled_with_cuda() else "cpu"
    logger.info(f"PaddleOCR using device: {device}")
    return device

def init_ocr_engine() -> PaddleOCR:
    logger.info("Initializing PaddleOCR engine...")
    ocr = PaddleOCR(
        lang=settings.OCR_LANG,
        ocr_version=settings.OCR_VERSION,
        use_doc_orientation_classify=settings.OCR_USE_DOC_ORIENTATION_CLASSIFY,
        use_doc_unwarping=settings.OCR_USE_DOC_UNWARPING,
        use_textline_orientation=settings.OCR_USE_TEXTLINE_ORIENTATION,
        device=get_device(),
        text_rec_score_thresh=settings.OCR_TEXT_REC_SCORE_THRESH,
    )
    return ocr
