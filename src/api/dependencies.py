from functools import lru_cache
from src.core.config import settings
from src.services.ocr_engine import init_ocr_engine
from src.services.vlm_processor import VLLMDocumentProcessor

@lru_cache()
def get_ocr_engine():
    return init_ocr_engine()

@lru_cache()
def get_vlm_processor():
    ocr_engine = get_ocr_engine()
    return VLLMDocumentProcessor(
        base_url=settings.VLLM_BASE_URL,
        model_name=settings.VLLM_MODEL_NAME,
        api_key=settings.VLLM_API_KEY,
        ocr_engine=ocr_engine
    )
