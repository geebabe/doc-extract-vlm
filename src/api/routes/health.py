from fastapi import APIRouter
from src.services.ocr_engine import get_device

router = APIRouter()

@router.get("/")
def health_check():
    return {"status": "ok", "device": get_device()}
