from fastapi import FastAPI
from src.core.config import settings
from src.core.logger import logger
from src.api.routes import extract, health
from src.api.dependencies import get_ocr_engine, get_vlm_processor

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(extract.router, prefix="/extract", tags=["Extraction"])

@app.on_event("startup")
def startup_event():
    logger.info("Initializing models on startup...")
    # Initialize models so they are ready before the first request
    get_ocr_engine()
    get_vlm_processor()
    logger.info("Initialization complete.")
