from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "OCR API"
    VLLM_BASE_URL: str = "https://8000-01kqrdgejr2179p8rc37ev5p08.cloudspaces.litng.ai/v1"
    VLLM_MODEL_NAME: str = "5CD-AI/Vintern-1B-v3_5"
    VLLM_API_KEY: str = "none"
    
    OCR_LANG: str = "vi"
    OCR_VERSION: str = "PP-OCRv5"
    OCR_USE_DOC_ORIENTATION_CLASSIFY: bool = False
    OCR_USE_DOC_UNWARPING: bool = False
    OCR_USE_TEXTLINE_ORIENTATION: bool = False
    OCR_TEXT_REC_SCORE_THRESH: float = 0.5
    
    @field_validator("OCR_TEXT_REC_SCORE_THRESH", mode="before")
    @classmethod
    def clean_float(cls, v):
        if isinstance(v, str):
            return v.strip("'\"")
        return v
    
    class Config:
        env_file = ".env"

settings = Settings()
