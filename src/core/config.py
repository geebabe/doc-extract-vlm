from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "OCR API"
    VLLM_BASE_URL: str = "https://8000-01kqrdgejr2179p8rc37ev5p08.cloudspaces.litng.ai/v1"
    VLLM_MODEL_NAME: str = "Qwen/Qwen3-VL-2B-Instruct"
    VLLM_API_KEY: str = "none"
    
    OCR_LANG: str = "vi"
    OCR_VERSION: str = "PP-OCRv5"
    OCR_USE_DOC_ORIENTATION_CLASSIFY: bool = False
    OCR_USE_DOC_UNWARPING: bool = False
    OCR_USE_TEXTLINE_ORIENTATION: bool = False
    OCR_TEXT_REC_SCORE_THRESH: float = 0.5
    
    class Config:
        env_file = ".env"

settings = Settings()
