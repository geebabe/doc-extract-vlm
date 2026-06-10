import hashlib
import json
import base64
import io
import os
import re
import threading
import uuid
from datetime import datetime
import numpy as np
from PIL import Image, UnidentifiedImageError
from typing import Optional, Any
from pydantic import BaseModel
from openai import AsyncOpenAI
import httpx
import asyncio
from cachetools import TTLCache
from fastapi import HTTPException
import time
from src.core.config import settings
from src.core.logger import logger
from src.services.prompt_builder import build_system_prompt, get_user_prompt
from src.services.post_processor import post_process_extraction
from src.services.image_utils import preprocess_image
from src.core.metrics import OCR_TIME, VLM_TIME, TOTAL_TIME, CORRECTION_COUNT


# Sentinel strings returned from run_paddle_ocr_normalized when OCR cannot be
# used. The prompt builder inspects these to switch into a vision-only mode.
OCR_UNAVAILABLE_SENTINEL = "OCR_UNAVAILABLE"
OCR_EMPTY_SENTINEL = "OCR_EMPTY"

_ROW_TOLERANCE = 15  # normalized units (~1.5% of height) to group same-row elements


def _sort_ocr_reading_order(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["b"][1] // _ROW_TOLERANCE, r["b"][0]))


def _safe_stem(image_source: str) -> str:
    base = os.path.basename(image_source) or "request"
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return base[:120]


def _write_debug_dump(
    image_source: str,
    route_key: str,
    ocr_context: str,
    system_prompt: str,
    user_prompt: str,
    raw_response: Optional[str] = None,
    parsed: Optional[dict] = None,
) -> None:
    """Best-effort write of OCR text, prompt, and VLM raw output for offline triage."""
    if not settings.DEBUG_DUMP_ENABLED:
        return
    try:
        os.makedirs(settings.DEBUG_DUMP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"{ts}_{route_key}_{_safe_stem(image_source)}_{uuid.uuid4().hex[:6]}"
        base_path = os.path.join(settings.DEBUG_DUMP_DIR, stem)

        with open(f"{base_path}_ocr.txt", "w", encoding="utf-8") as f:
            f.write(f"# source: {image_source}\n# route: {route_key}\n\n")
            f.write(ocr_context or "")

        with open(f"{base_path}_prompt.txt", "w", encoding="utf-8") as f:
            f.write(f"# source: {image_source}\n# route: {route_key}\n\n")
            f.write("===== SYSTEM PROMPT =====\n")
            f.write(system_prompt or "")
            f.write("\n\n===== USER PROMPT =====\n")
            f.write(user_prompt or "")

        if raw_response is not None:
            with open(f"{base_path}_vlm_raw.txt", "w", encoding="utf-8") as f:
                f.write(f"# source: {image_source}\n# route: {route_key}\n\n")
                f.write(raw_response)

        if parsed is not None:
            with open(f"{base_path}_parsed.json", "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)

        logger.info(f"Debug dump written: {base_path}_*")
    except Exception as e:
        logger.warning(f"Failed to write debug dump: {e}")

class VLLMDocumentProcessor:
    def __init__(
        self,
        base_url: str,
        model_name: str,
        api_key: str,
        ocr_engine: Any,
        preprocessing_ocr_engine: Any = None,
        preprocessing_routes: set = None,
    ):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name
        self.ocr_engine = ocr_engine
        self.preprocessing_ocr_engine = preprocessing_ocr_engine
        self.preprocessing_routes = preprocessing_routes or set()
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
        )
        self.ocr_lock = threading.Lock()
        self.preprocessing_ocr_lock = threading.Lock()
        self._cache: TTLCache = TTLCache(maxsize=100, ttl=300)
        self._cache_lock = threading.Lock()
        self._ocr_semaphore = asyncio.Semaphore(settings.OCR_CONCURRENCY)
        self._vlm_semaphore = asyncio.Semaphore(settings.VLM_CONCURRENCY)

    async def close(self) -> None:
        await self.http_client.aclose()
        await self.client.close()

    def encode_image_base64(self, image: Image.Image) -> str:
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    async def run_paddle_ocr_normalized(self, image: Image.Image, route_key: str = "general") -> str:
        use_preprocessing = (
            route_key in self.preprocessing_routes
            and self.preprocessing_ocr_engine is not None
        )
        engine = self.preprocessing_ocr_engine if use_preprocessing else self.ocr_engine
        lock = self.preprocessing_ocr_lock if use_preprocessing else self.ocr_lock

        if engine is None:
            return OCR_UNAVAILABLE_SENTINEL

        img_w, img_h = image.size

        def _predict(arr: np.ndarray):
            with lock:
                return engine.predict(arr)

        # PaddleOCR's CPU static predictor can raise a generic std::exception on
        # certain input sizes (e.g. exactly 1024x1024 with PP-OCRv5 + textline
        # orientation). Retry once at a different size before giving up so the
        # VLM still gets useful OCR hints.
        async def _try(arr: np.ndarray) -> Optional[list]:
            try:
                return await asyncio.to_thread(_predict, arr)
            except Exception as exc:
                logger.error(
                    f"PaddleOCR predict failed (shape={arr.shape}, dtype={arr.dtype}): "
                    f"{type(exc).__name__}: {exc}"
                )
                return None

        img_np = np.array(image)
        results = await _try(img_np)

        if results is None:
            # Retry at a non-square stride-32 size. The known CPU PP-OCRv5
            # crash repro is square inputs at H==W==1024 (and likely other
            # square sizes) interacting with the textline orientation model,
            # so the retry MUST break the square aspect, not just shrink.
            try:
                safe_long = 960  # multiple of 32, well clear of 1024
                safe_short = 768  # multiple of 32, breaks square aspect
                if img_w >= img_h:
                    new_w, new_h = safe_long, safe_short
                else:
                    new_w, new_h = safe_short, safe_long
                if (new_w, new_h) != (img_w, img_h):
                    logger.warning(
                        f"Retrying PaddleOCR at {new_w}x{new_h} (was {img_w}x{img_h}, "
                        f"breaking square aspect)"
                    )
                    retry_img = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    retry_np = np.array(retry_img)
                    # Rescale OCR coords using the resized dims so normalized
                    # boxes still map to [0, 1000] correctly.
                    img_w, img_h = new_w, new_h
                    results = await _try(retry_np)
            except Exception as exc:
                logger.error(f"OCR retry preparation failed: {type(exc).__name__}: {exc}")
                results = None

        if results is None:
            return OCR_UNAVAILABLE_SENTINEL

        if not results or not results[0]:
            return OCR_EMPTY_SENTINEL

        ocr_rows = []
        page = results[0]

        if isinstance(page, dict):
            texts = page.get("rec_texts", [])
            boxes = page.get("rec_boxes", [])
            for i, text in enumerate(texts):
                box = boxes[i]
                xmin = int(max(0, min(1000, (box[0] / img_w) * 1000)))
                ymin = int(max(0, min(1000, (box[1] / img_h) * 1000)))
                xmax = int(max(0, min(1000, (box[2] / img_w) * 1000)))
                ymax = int(max(0, min(1000, (box[3] / img_h) * 1000)))
                ocr_rows.append({"t": text, "b": [xmin, ymin, xmax, ymax]})
        else:
            for line in page:
                box = line[0]
                text, _ = line[1]
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                xmin = int(max(0, min(1000, (min(xs) / img_w) * 1000)))
                ymin = int(max(0, min(1000, (min(ys) / img_h) * 1000)))
                xmax = int(max(0, min(1000, (max(xs) / img_w) * 1000)))
                ymax = int(max(0, min(1000, (max(ys) / img_h) * 1000)))
                ocr_rows.append({"t": text, "b": [xmin, ymin, xmax, ymax]})

        ocr_rows = _sort_ocr_reading_order(ocr_rows)
        return "\n".join(json.dumps(row, ensure_ascii=False) for row in ocr_rows)

    _MAX_URL_BYTES = 20 * 1024 * 1024  # 20 MB

    def _cache_key(self, image_bytes: bytes, route_key: str) -> str:
        return hashlib.sha256(image_bytes).hexdigest()[:16] + ":" + route_key

    async def process(
        self,
        image_source: str | bytes,
        schema_class: type[BaseModel],
        route_key: str = "general",
    ) -> tuple[Optional[dict], bool]:
        # Resolve to raw bytes so we can compute a cache key regardless of source.
        image_bytes: Optional[bytes] = None
        img = None
        try:
            if isinstance(image_source, bytes):
                image_bytes = image_source
                img = Image.open(io.BytesIO(image_bytes))
                img = img.convert("RGB")
            elif image_source.startswith("http"):
                response = await self.http_client.get(image_source)
                response.raise_for_status()
                content_length = int(response.headers.get("content-length", 0))
                if content_length > self._MAX_URL_BYTES:
                    raise HTTPException(status_code=400, detail=f"Image exceeds 20 MB limit.")
                image_bytes = response.content
                if len(image_bytes) > self._MAX_URL_BYTES:
                    raise HTTPException(status_code=400, detail=f"Image exceeds 20 MB limit.")
                img = Image.open(io.BytesIO(image_bytes))
                img = img.convert("RGB")
            else:
                image_bytes = await asyncio.to_thread(lambda: open(image_source, "rb").read())
                img = Image.open(io.BytesIO(image_bytes))
                img = img.convert("RGB")

            # Preprocess image
            img = preprocess_image(img)

            # Cache check — must happen after image bytes are available.
            cache_key = self._cache_key(image_bytes, route_key)
            with self._cache_lock:
                cached = self._cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit — skipping OCR + VLM.")
                return cached, True

            logger.info("Running PaddleOCR...")
            start_ocr = time.time()
            async with self._ocr_semaphore:
                ocr_context = await self.run_paddle_ocr_normalized(img, route_key=route_key)
            ocr_duration = time.time() - start_ocr
            OCR_TIME.labels(route=route_key).observe(ocr_duration)

            system_prompt = build_system_prompt(route_key, ocr_context)
            user_prompt = get_user_prompt(route_key)

            logger.info(f"Calling VLLM ({self.model_name})...")
            image_b64 = await asyncio.to_thread(self.encode_image_base64, img)
        except UnidentifiedImageError as e:
            logger.error(f"Invalid image format: {e}")
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid image format.")
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch image from URL: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to fetch image from URL: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to load image: {e}", exc_info=True)
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Failed to load image: {str(e)}")
        finally:
            if img:
                img.close()

        raw_response_text: Optional[str] = None
        extraction_dict: Optional[dict] = None
        try:
            total_start = time.time()
            start_vlm = time.time()
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"

            async with self._vlm_semaphore:
                response = await self.client.beta.chat.completions.parse(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                                },
                                {
                                    "type": "text",
                                    "text": combined_prompt
                                }
                            ]
                        }
                    ],
                    response_format=schema_class,
                    temperature=0.0,
                    max_completion_tokens=4096,
                )
            vlm_duration = time.time() - start_vlm
            VLM_TIME.labels(route=route_key).observe(vlm_duration)

            # Capture the model's raw textual output for debugging.
            try:
                raw_response_text = response.choices[0].message.content
            except Exception:
                raw_response_text = None

            extraction = response.choices[0].message.parsed

            if not extraction:
                logger.error("Model failed to parse output into schema")
                _write_debug_dump(
                    image_source, route_key, ocr_context, system_prompt, user_prompt,
                    raw_response=raw_response_text, parsed=None,
                )
                raise HTTPException(status_code=500, detail="VLLM failed to parse structured output.")

            extraction_dict = extraction.model_dump()

            # Post-process: reconcile VLM output with OCR
            corrected_extraction, correction_metadata = post_process_extraction(
                extraction_dict, ocr_context, schema_class, route_key
            )

            if correction_metadata.corrections:
                logger.info(f"Post-processing corrections: {len(correction_metadata.corrections)} fields adjusted")
                logger.debug(f"Correction details: {correction_metadata.to_dict()}")
                CORRECTION_COUNT.labels(route=route_key).inc(len(correction_metadata.corrections))

            total_duration = time.time() - total_start
            TOTAL_TIME.labels(route=route_key).observe(total_duration)

            # Always dump when enabled, or only when every extracted field is null
            # (the "success=true but no data" failure mode the user is debugging).
            should_dump = settings.DEBUG_DUMP_ENABLED and (
                not corrected_extraction
                or all(v is None for v in corrected_extraction.values())
            )
            if should_dump:
                _write_debug_dump(
                    image_source, route_key, ocr_context, system_prompt, user_prompt,
                    raw_response=raw_response_text, parsed=corrected_extraction,
                )

            with self._cache_lock:
                self._cache[cache_key] = corrected_extraction
            return corrected_extraction, False

        except Exception as e:
            logger.error(f"Error during VLLM parse: {e}")
            _write_debug_dump(
                image_source, route_key, ocr_context, system_prompt, user_prompt,
                raw_response=raw_response_text, parsed=extraction_dict,
            )
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"VLLM inference error: {str(e)}")
