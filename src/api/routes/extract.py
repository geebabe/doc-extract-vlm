import os
import shutil
import uuid
import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Type

from src.schemas.request import ExtractURLRequest
from src.schemas.invoice import InvoiceExtraction, InvoiceResponse
from src.schemas.id_card import IDCardExtraction, IDCardResponse
from src.schemas.general import GeneralDocumentExtraction, GeneralDocumentResponse
from src.services.vlm_processor import VLLMDocumentProcessor
from src.api.dependencies import get_vlm_processor
from src.core.logger import logger

router = APIRouter()

# Global semaphore to limit concurrent extraction executions
CONCURRENCY_LIMITER = asyncio.Semaphore(4)

async def _process_file(file: UploadFile, processor: VLLMDocumentProcessor, schema_class: Type[BaseModel]):
    safe_filename = os.path.basename(file.filename)
    temp_filename = f"temp_{uuid.uuid4()}_{safe_filename}"
    
    try:
        # Offload blocking file writing to a thread
        def write_file():
            with open(temp_filename, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        
        await asyncio.to_thread(write_file)
        
        logger.info(f"Processing uploaded file: {file.filename} with schema {schema_class.__name__}")
        result = await processor.process(temp_filename, schema_class)
        if result is None:
            raise HTTPException(status_code=500, detail="Extraction failed")
        return result
    finally:
        # Release uploaded file resources
        await file.close()
        # Offload file removal to thread to keep event loop non-blocking
        if os.path.exists(temp_filename):
            await asyncio.to_thread(os.remove, temp_filename)

async def _process_url(request: ExtractURLRequest, processor: VLLMDocumentProcessor, schema_class: Type[BaseModel]):
    logger.info(f"Processing URL: {request.url} with schema {schema_class.__name__}")
    result = await processor.process(request.url, schema_class)
    if result is None:
        raise HTTPException(status_code=500, detail="Extraction failed")
    return result

# --- Invoice Endpoints ---

@router.post("/invoice/file", response_model=InvoiceResponse)
async def extract_invoice_file(
    file: UploadFile = File(...),
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from uploaded invoice image file."""
    async with CONCURRENCY_LIMITER:
        data = await _process_file(file, processor, InvoiceExtraction)
        return InvoiceResponse(success=True, data=data)

@router.post("/invoice/url", response_model=InvoiceResponse)
async def extract_invoice_url(
    request: ExtractURLRequest,
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from invoice image URL."""
    async with CONCURRENCY_LIMITER:
        data = await _process_url(request, processor, InvoiceExtraction)
        return InvoiceResponse(success=True, data=data)

# --- ID Card Endpoints ---

@router.post("/id_card/file", response_model=IDCardResponse)
async def extract_id_card_file(
    file: UploadFile = File(...),
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from uploaded ID card image file."""
    async with CONCURRENCY_LIMITER:
        data = await _process_file(file, processor, IDCardExtraction)
        return IDCardResponse(success=True, data=data)

@router.post("/id_card/url", response_model=IDCardResponse)
async def extract_id_card_url(
    request: ExtractURLRequest,
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from ID card image URL."""
    async with CONCURRENCY_LIMITER:
        data = await _process_url(request, processor, IDCardExtraction)
        return IDCardResponse(success=True, data=data)

# --- General Document Endpoints ---

@router.post("/others/file", response_model=GeneralDocumentResponse)
async def extract_general_file(
    file: UploadFile = File(...),
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from general document image file."""
    async with CONCURRENCY_LIMITER:
        data = await _process_file(file, processor, GeneralDocumentExtraction)
        return GeneralDocumentResponse(success=True, data=data)

@router.post("/others/url", response_model=GeneralDocumentResponse)
async def extract_general_url(
    request: ExtractURLRequest,
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from general document image URL."""
    async with CONCURRENCY_LIMITER:
        data = await _process_url(request, processor, GeneralDocumentExtraction)
        return GeneralDocumentResponse(success=True, data=data)
