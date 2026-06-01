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
from fastapi import HTTPException
import time
from src.core.config import settings
from src.core.logger import logger
from src.services.prompt_builder import build_system_prompt, get_user_prompt
from src.services.post_processor import post_process_extraction
from src.services.image_utils import preprocess_image
from src.core.metrics import OCR_TIME, VLM_TIME, TOTAL_TIME, CORRECTION_COUNT


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
    def __init__(self, base_url: str, model_name: str, api_key: str, ocr_engine: Any):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name
        self.ocr_engine = ocr_engine
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.ocr_lock = threading.Lock()

    def encode_image_base64(self, image: Image.Image) -> str:
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    async def run_paddle_ocr_normalized(self, image: Image.Image) -> str:
        if self.ocr_engine is None:
            return "OCR engine not initialized."

        img_w, img_h = image.size
        img_np = np.array(image)

        def _predict():
            with self.ocr_lock:
                return self.ocr_engine.predict(img_np)

        # Offload CPU-bound inference to thread pool.
        # PaddleOCR's CPU static predictor can raise a generic std::exception on
        # certain inputs. Degrade gracefully so the VLM can still process the
        # image without OCR hints rather than failing the whole request.
        try:
            results = await asyncio.to_thread(_predict)
        except Exception as e:
            logger.error(
                f"PaddleOCR predict failed (shape={img_np.shape}, dtype={img_np.dtype}, "
                f"size={img_w}x{img_h}): {type(e).__name__}: {e}"
            )
            return "OCR unavailable for this image."

        if not results or not results[0]:
            return "Không tìm thấy văn bản nào."

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
                ocr_rows.append(json.dumps({"t": text, "b": [xmin, ymin, xmax, ymax]}, ensure_ascii=False))
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
                ocr_rows.append(json.dumps({"t": text, "b": [xmin, ymin, xmax, ymax]}, ensure_ascii=False))

        return "\n".join(ocr_rows)

    async def process(
        self,
        image_source: str,
        schema_class: type[BaseModel],
        route_key: str = "general",
    ) -> Optional[dict]:
        img = None
        try:
            if image_source.startswith("http"):
                response = await self.http_client.get(image_source)
                response.raise_for_status()
                img = Image.open(io.BytesIO(response.content))
                img = img.convert("RGB")
            else:
                img = await asyncio.to_thread(Image.open, image_source)
                img = img.convert("RGB")

            # Preprocess image
            img = preprocess_image(img, route_key)

            logger.info("Running PaddleOCR...")
            start_ocr = time.time()
            ocr_context = await self.run_paddle_ocr_normalized(img)
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

            return corrected_extraction

        except Exception as e:
            logger.error(f"Error during VLLM parse: {e}")
            _write_debug_dump(
                image_source, route_key, ocr_context, system_prompt, user_prompt,
                raw_response=raw_response_text, parsed=extraction_dict,
            )
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"VLLM inference error: {str(e)}")
