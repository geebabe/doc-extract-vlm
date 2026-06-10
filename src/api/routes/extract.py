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


async def _process_file(file: UploadFile, processor: VLLMDocumentProcessor, schema_class: Type[BaseModel], route_key: str = "general"):
    try:
        data = await file.read()
        logger.info(f"Processing uploaded file: {file.filename} with schema {schema_class.__name__}")
        result, cache_hit = await processor.process(data, schema_class, route_key)
        if result is None:
            raise HTTPException(status_code=500, detail="Extraction failed")
        return result, cache_hit
    finally:
        await file.close()

async def _process_url(request: ExtractURLRequest, processor: VLLMDocumentProcessor, schema_class: Type[BaseModel], route_key: str = "general"):
    logger.info(f"Processing URL: {request.url} with schema {schema_class.__name__}")
    result, cache_hit = await processor.process(request.url, schema_class, route_key)
    if result is None:
        raise HTTPException(status_code=500, detail="Extraction failed")
    return result, cache_hit

# --- Invoice Endpoints ---

@router.post("/invoice/file", response_model=InvoiceResponse)
async def extract_invoice_file(
    file: UploadFile = File(...),
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from uploaded invoice image file."""
    data, cache_hit = await _process_file(file, processor, InvoiceExtraction, route_key="invoice")
    return InvoiceResponse(success=True, data=data, metadata={"cache_hit": cache_hit})

@router.post("/invoice/url", response_model=InvoiceResponse)
async def extract_invoice_url(
    request: ExtractURLRequest,
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from invoice image URL."""
    data, cache_hit = await _process_url(request, processor, InvoiceExtraction, route_key="invoice")
    return InvoiceResponse(success=True, data=data, metadata={"cache_hit": cache_hit})

# --- ID Card Endpoints ---

@router.post("/id_card/file", response_model=IDCardResponse)
async def extract_id_card_file(
    file: UploadFile = File(...),
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from uploaded ID card image file."""
    data, cache_hit = await _process_file(file, processor, IDCardExtraction, route_key="id_card")
    return IDCardResponse(success=True, data=data, metadata={"cache_hit": cache_hit})

@router.post("/id_card/url", response_model=IDCardResponse)
async def extract_id_card_url(
    request: ExtractURLRequest,
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from ID card image URL."""
    data, cache_hit = await _process_url(request, processor, IDCardExtraction, route_key="id_card")
    return IDCardResponse(success=True, data=data, metadata={"cache_hit": cache_hit})

# --- General Document Endpoints ---

@router.post("/others/file", response_model=GeneralDocumentResponse)
async def extract_general_file(
    file: UploadFile = File(...),
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from general document image file."""
    data, cache_hit = await _process_file(file, processor, GeneralDocumentExtraction, route_key="general")
    return GeneralDocumentResponse(success=True, data=data, metadata={"cache_hit": cache_hit})

@router.post("/others/url", response_model=GeneralDocumentResponse)
async def extract_general_url(
    request: ExtractURLRequest,
    processor: VLLMDocumentProcessor = Depends(get_vlm_processor)
):
    """Extract information from general document image URL."""
    data, cache_hit = await _process_url(request, processor, GeneralDocumentExtraction, route_key="general")
    return GeneralDocumentResponse(success=True, data=data, metadata={"cache_hit": cache_hit})
