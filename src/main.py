from fastapi import FastAPI, Request
import uuid
from prometheus_fastapi_instrumentator import Instrumentator

from src.core.config import settings
from src.core.logger import logger
from src.api.routes import extract, health
from src.api.dependencies import get_ocr_engine, get_vlm_processor

app = FastAPI(title=settings.PROJECT_NAME)

@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    # Add request ID to headers so it can be extracted later if needed
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Initialize Prometheus instrumentation
Instrumentator().instrument(app).expose(app)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(extract.router, prefix="/extract", tags=["Extraction"])

@app.on_event("startup")
def startup_event():
    logger.info("Initializing models on startup...")
    # Initialize models so they are ready before the first request
    get_ocr_engine()
    get_vlm_processor()
    logger.info("Initialization complete.")
