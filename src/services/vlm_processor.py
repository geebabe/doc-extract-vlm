import json
import base64
import requests
import io
import numpy as np
from PIL import Image
from typing import Optional, Any
from openai import OpenAI
from src.schemas.invoice import InvoiceExtraction
from src.core.logger import logger

SYSTEM_PROMPT = """You are an advanced OCR and document understanding system. Your goal is to extract structured information from the provided document image with high precision.

### KEY INSTRUCTIONS:
1. **NATIVE GROUNDING**: For every field, you must provide the extracted text (value) and its precise coordinates (bounding_box).
2. **COORDINATE SYSTEM**: All bounding boxes MUST be normalized to a scale of [0, 1000]. The format is [xmin, ymin, xmax, ymax].
3. **OUTPUT FORMAT**: Return strictly valid JSON matching the provided schema. No markdown, no conversational fillers, and no explanations.

### CONTEXTUAL HINTS:
- **Language**: The document is primarily in Vietnamese. Pay close attention to diacritics and specialized terms.
- **Preliminary OCR**: Below is a draft OCR extraction (already normalized to [0, 1000]) to help you identify characters and locations. Use these as hints, but rely on your visual perception if the image contradicts these hints:
{ocr_context}

### SCHEMA DEFINITION:
{schema_str}"""

class VLLMDocumentProcessor:
    def __init__(self, base_url: str, model_name: str, api_key: str, ocr_engine: Any):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name
        self.ocr_engine = ocr_engine

    def encode_image_base64(self, image: Image.Image) -> str:
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def run_paddle_ocr_normalized(self, image: Image.Image) -> str:
        if self.ocr_engine is None:
            return "OCR engine not initialized."
            
        img_w, img_h = image.size
        img_np = np.array(image)
        
        results = self.ocr_engine.predict(img_np)
        
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
                ocr_rows.append(str((text, [xmin, ymin, xmax, ymax])))
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
                ocr_rows.append(str((text, [xmin, ymin, xmax, ymax])))

        return "\n".join(ocr_rows)

    def process(self, image_source: str) -> Optional[dict]:
        try:
            if image_source.startswith("http"):
                img = Image.open(requests.get(image_source, stream=True, timeout=10).raw).convert("RGB")
            else:
                img = Image.open(image_source).convert("RGB")
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            return None
        
        logger.info("Running PaddleOCR...")
        ocr_context = self.run_paddle_ocr_normalized(img)
        
        invoice_schema = InvoiceExtraction.model_json_schema()
        schema_str = json.dumps(invoice_schema, indent=2)
        full_system_prompt = SYSTEM_PROMPT.format(
            ocr_context=ocr_context, 
            schema_str=schema_str
        )
        
        logger.info(f"Calling VLLM ({self.model_name})...")
        image_b64 = self.encode_image_base64(img)
        
        try:
            combined_prompt = f"{full_system_prompt}\n\nAnalyze the attached document and perform structured extraction according to the schema."
            
            response = self.client.beta.chat.completions.parse(
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
                response_format=InvoiceExtraction,
            )
            
            extraction = response.choices[0].message.parsed
            
            if not extraction:
                logger.error("Model failed to parse output into schema")
                return None
                
            return extraction.model_dump()
        
        except Exception as e:
            logger.error(f"Error during VLLM parse: {e}")
            return None
