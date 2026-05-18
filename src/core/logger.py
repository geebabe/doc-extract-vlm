import logging
import os

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("ocr-api")
    
    # Disable verbose logs for PaddleOCR
    os.environ["PADDLEOCR_LOG_LEVEL"] = "WARNING"
    logging.getLogger("ppocr").setLevel(logging.WARNING)
    
    return logger

logger = setup_logger()
