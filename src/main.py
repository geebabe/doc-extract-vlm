from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import uuid
from src.core.config import settings
from src.core.logger import logger
from src.api.routes import extract, health
from src.api.dependencies import get_ocr_engine, get_preprocessing_ocr_engine, get_vlm_processor


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing models on startup...")
    get_ocr_engine()
    get_preprocessing_ocr_engine()
    processor = get_vlm_processor()
    logger.info("Initialization complete.")
    yield
    await processor.close()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    # Add request ID to headers so it can be extracted later if needed
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(extract.router, prefix="/extract", tags=["Extraction"])
