from prometheus_client import Histogram, Counter

# Time spent inside OCR processing (seconds)
OCR_TIME = Histogram(
    "ocr_duration_seconds",
    "Time spent in OCR",
    ["route"]
)

# Time spent inside VLM inference (seconds) 
VLM_TIME = Histogram(
    "vlm_duration_seconds",
    "Time spent in VLM inference",
    ["route"]
)

# Total time for end-to-end extraction (seconds)
TOTAL_TIME = Histogram(
    "total_extraction_seconds", 
    "Total time for extraction",
    ["route"]
)

# Number of post-processing corrections applied
CORRECTION_COUNT = Counter(
    "post_processing_corrections_total",
    "Number of fields corrected in post-processing",
    ["route"]
)
