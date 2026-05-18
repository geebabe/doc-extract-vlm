import os
import shutil
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from src.schemas.request import ExtractURLRequest
from src.services.vlm_processor import VLLMDocumentProcessor
from src.api.dependencies import get_vlm_processor
from src.core.logger import logger

router = APIRouter()

@router.post("/file")
async def extract_file(
    file: UploadFile = File(...),
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from uploaded image file."""
    temp_filename = f"temp_{uuid.uuid4()}_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        logger.info(f"Processing uploaded file: {file.filename}")
        result = processor.process(temp_filename)
        if result is None:
            raise HTTPException(status_code=500, detail="Extraction failed")
        return result
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@router.post("/url")
async def extract_url(
    request: ExtractURLRequest,
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from image URL."""
    logger.info(f"Processing URL: {request.url}")
    result = processor.process(request.url)
    if result is None:
        raise HTTPException(status_code=500, detail="Extraction failed")
    return result
