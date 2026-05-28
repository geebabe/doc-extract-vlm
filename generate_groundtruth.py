"""
Ground-truth generation pipeline using Together.ai (Qwen3-VL-235B-A22B-Instruct-FP8).
Supports:
- Invoices: data/invoices/
- Vietnamese CCCD cards: data/cccd/valid/ (both front and back sides)

Runs PaddleOCR, then calls the VLM to produce structured JSON ground-truth.
"""

import asyncio
import base64
import io
import json
import os
import sys
from pathlib import Path
from enum import Enum

import numpy as np
from dotenv import load_dotenv
from openai import AsyncOpenAI
from PIL import Image

# Allow importing src/ from project root
sys.path.insert(0, str(Path(__file__).parent))
from src.schemas.invoice import InvoiceExtraction
from src.schemas.id_card import IDCardExtraction

load_dotenv()

# ---------------------------------------------------------------------------
# Together.ai client setup
# ---------------------------------------------------------------------------
TOGETHER_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TOGETHER_BASE_URL = "https://api.together.xyz/v1"
MODEL_NAME = "Qwen/Qwen3.5-397B-A17B"


class DocumentType(Enum):
    INVOICE = "invoice"
    CCCD = "cccd"

# ---------------------------------------------------------------------------
# Document-specific prompts
# ---------------------------------------------------------------------------

INVOICE_SYSTEM_PROMPT = """\
You are a strict invoice data extraction engine used to build ground-truth datasets.
Your output will be used to train and evaluate other models, so accuracy is critical.

=== SCHEMA FIELD DEFINITIONS ===

The invoice schema has the following fields. Every field follows this structure:
  {{
    "value": "<exact text from invoice, or null if absent>",
    "bounding_box":  [xmin, ymin, xmax, ymax]   (integers, normalized to [0, 1000] scale, or null)
  }}

Fields:
- invoice_number        : The unique identifier of this invoice (e.g. "0001234", "INV-2024-001").
                          Often labelled: "Số hóa đơn", "Số:", "Invoice No.", "No.".
- invoice_date          : The date the invoice was issued.
                          Often labelled: "Ngày", "Date", "Ngày lập", "Ngày phát hành".
                          Preserve exact formatting from the invoice (e.g. "15/03/2024", "March 15, 2024").
- vendor.name           : Full legal name of the issuing company/vendor.
                          Often labelled: "Đơn vị bán hàng", "Công ty", "Seller", "Vendor".
- vendor.address        : Full address of the vendor.
                          Often labelled: "Địa chỉ:", "Address:". Include street, district, city.
- vendor.tax_code       : Tax identification number of the vendor.
                          Often labelled: "Mã số thuế:", "MST:", "Tax Code:", "Tax ID:".
                          Typically a 10 or 13-digit number.
- vendor.phone          : Phone or fax number of the vendor.
                          Often labelled: "Điện thoại:", "ĐT:", "Tel:", "Phone:".
- items                 : List of line items in the invoice. Each item has:
    - description       : Name or description of the product/service.
                          Often in the "Tên hàng hóa, dịch vụ", "Description", "Diễn giải" column.
    - quantity          : Number of units. Often in the "Số lượng", "Qty", "SL" column.
                          Preserve exact value (e.g. "2", "1.5").
    - unit_price        : Price per unit. Often in the "Đơn giá", "Unit Price" column.
                          Preserve exact numeric formatting.
    - total_amount      : Line total for this item (quantity × unit_price).
                          Often in the "Thành tiền", "Amount", "Tổng" column.
                          Preserve exact numeric formatting.
- total_amount          : Final invoice amount due including all taxes and fees.
                          Often labelled: "Tổng cộng", "Total", "Số tiền thanh toán",
                          "Tổng tiền thanh toán", "Amount Due".
                          Preserve exact numeric formatting.
- currency              : Currency code or symbol used in the invoice (e.g. "VND", "USD", "đ").
                          If no explicit currency is stated, output null.

=== STRICT RULES ===

1. NULL VALUES: If a field is not present anywhere in the invoice — not visually, not in OCR —
   output: {{"value": null, "bounding_box": null}}

2. NO HALLUCINATION: Do not infer, guess, or fabricate values. If uncertain, output null.

3. EXACT PRESERVATION: Copy the value exactly as it appears on the invoice, including:
   - Spacing, punctuation, and capitalization
   - Numeric separators (e.g., "1.234.567" not "1234567")
   - Date formats (e.g., "15/03/2024" not "2024-03-15")
   - Vietnamese diacritics (e.g., "Công ty TNHH", not "Cong ty TNHH")

4. BOUNDING BOX: Report the bounding box as [xmin, ymin, xmax, ymax] normalized to [0, 1000].
   Use the OCR context below as a reference for coordinates. If you cannot determine a bbox,
   set it to null — do NOT fabricate coordinates.

5. MULTI-LINE VALUES: If a field spans multiple lines (e.g., a long address), concatenate
   with a single space and compute a bbox that covers all lines.

6. ITEMS LIST: Extract ALL line items from the invoice table. If there are no items, output an
   empty list []. Each item must have at minimum a "description". Set missing sub-fields to
   {{"value": null, "bounding_box": null}}. Do not merge rows — one object per invoice line item.

=== OCR CONTEXT (preliminary extraction, normalized to [0, 1000]) ===
{ocr_context}
"""

CCCD_SYSTEM_PROMPT = """\
You are a strict Vietnamese CCCD (Căn Cước Công Dân) ID card data extraction engine.
Your output will be used to train and evaluate other models, so accuracy is critical.

=== CARD SIDES AND FIELD LOCATIONS ===

Vietnamese CCCD cards have TWO sides:
- FRONT SIDE: Contains name, date of birth, gender, nationality, place of origin.
- BACK SIDE: Contains ID number, expiry date, issue date, issue place, place of residence.

=== SCHEMA FIELD DEFINITIONS ===

Every field follows this structure:
  {{
    "value": "<exact text from card, or null if not visible on this side>",
    "bounding_box":  [xmin, ymin, xmax, ymax]   (integers, normalized to [0, 1000] scale, or null)
  }}

FRONT SIDE FIELDS (primary):
- id_number             : ID number (Số căn cước công dân). Usually on the BACK side only.
                          SET TO NULL if not visible on front.
- full_name             : Full name (Họ và tên). Always on FRONT.
- date_of_birth         : Date of birth (Ngày sinh). Always on FRONT.
- gender                : Gender (Giới tính). Often on FRONT.
- nationality           : Nationality (Quốc tịch). Often on FRONT.
- place_of_origin       : Place of origin (Quê quán). Often on FRONT.
- place_of_residence    : Place of residence (Nơi thường trú). Usually on BACK side only.
                          SET TO NULL if not visible on front.
- expiry_date           : Expiry date (Có giá trị đến). Usually on BACK side only.
                          SET TO NULL if not visible on front.
- issue_date            : Date of issue (Ngày cấp). Usually on BACK side only.
                          SET TO NULL if not visible on front.
- issue_place           : Place of issue (Nơi cấp). Usually on BACK side only.
                          SET TO NULL if not visible on front.

=== STRICT RULES ===

1. FIELD VISIBILITY: Different fields appear on different sides.
   - If a field is not visible on the current card side, output: {{"value": null, "bounding_box": null}}
   - Do NOT hallucinate or assume field values from the other side.

2. NULL VALUES: If a field is not present anywhere on this card side — not visually, not in OCR —
   output: {{"value": null, "bounding_box": null}}

3. NO HALLUCINATION: Do not infer, guess, or fabricate values. If uncertain, output null.

4. EXACT PRESERVATION: Copy the value exactly as it appears on the card, including:
   - Spacing, punctuation, and capitalization
   - Date formats (e.g., "15/03/2024" not "2024-03-15")
   - Vietnamese diacritics (e.g., "Hà Nội", not "Ha Noi")

5. BOUNDING BOX: Report the bounding box as [xmin, ymin, xmax, ymax] normalized to [0, 1000].
   Use the OCR context below as a reference for coordinates. If you cannot determine a bbox,
   set it to null — do NOT fabricate coordinates.

6. MULTI-LINE VALUES: If a field spans multiple lines (e.g., a long address), concatenate
   with a single space and compute a bbox that covers all lines.

=== OCR CONTEXT (preliminary extraction, normalized to [0, 1000]) ===
{ocr_context}
"""

INVOICE_USER_PROMPT = "Extract structured invoice data from this image following the schema and rules above."
CCCD_USER_PROMPT = "Extract structured CCCD card data from this image. Carefully handle field visibility based on which side of the card this is."


# ---------------------------------------------------------------------------
# OCR helpers (reused from vlm_processor.py logic)
# ---------------------------------------------------------------------------

def run_paddle_ocr_normalized(ocr_engine, image: Image.Image) -> str:
    img_w, img_h = image.size
    img_np = np.array(image)
    results = ocr_engine.predict(img_np)

    if not results or not results[0]:
        return "No text found."

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


def encode_image_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# ---------------------------------------------------------------------------
# VLM call — structured output via OpenAI SDK beta.parse
# ---------------------------------------------------------------------------

async def call_vlm(
    client: AsyncOpenAI,
    image_b64: str,
    ocr_context: str,
    doc_type: DocumentType,
) -> dict:
    if doc_type == DocumentType.INVOICE:
        system_prompt = INVOICE_SYSTEM_PROMPT.format(ocr_context=ocr_context)
        user_prompt = INVOICE_USER_PROMPT
        response_schema = InvoiceExtraction
    else:  # CCCD
        system_prompt = CCCD_SYSTEM_PROMPT.format(ocr_context=ocr_context)
        user_prompt = CCCD_USER_PROMPT
        response_schema = IDCardExtraction

    response = await client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                    {"type": "text", "text": f"{system_prompt}\n\n{user_prompt}"},
                ],
            }
        ],
        response_format=response_schema,
        temperature=0.0,
        max_tokens=4096,
        extra_body={
            "chat_template_kwargs": {"enable_thinking": False}
        }
    )
    extraction = response.choices[0].message.parsed
    if extraction is None:
        raise ValueError(f"Model failed to parse output into {response_schema.__name__} schema")
    return extraction.model_dump()


# ---------------------------------------------------------------------------
# Per-image pipeline
# ---------------------------------------------------------------------------

def detect_document_type(image_path: Path) -> DocumentType:
    """Detect document type from path."""
    if "cccd" in image_path.parts:
        return DocumentType.CCCD
    return DocumentType.INVOICE


async def process_image(
    client: AsyncOpenAI,
    ocr_engine,
    image_path: Path,
    output_dir: Path,
) -> None:
    stem = image_path.stem
    output_file = output_dir / f"{stem}.json"

    if output_file.exists():
        print(f"[SKIP] {image_path.name} — already processed")
        return

    print(f"[INFO] Processing {image_path.name} ...")

    image = Image.open(image_path).convert("RGB")
    doc_type = detect_document_type(image_path)

    print(f"  → Document type: {doc_type.value}")
    print(f"  → Running PaddleOCR...")
    ocr_context = run_paddle_ocr_normalized(ocr_engine, image)
    image_b64 = encode_image_base64(image)
    image.close()

    print(f"  → Calling {MODEL_NAME}...")
    try:
        result = await call_vlm(client, image_b64, ocr_context, doc_type)
    except Exception as e:
        print(f"  [ERROR] VLM call failed for {image_path.name}: {type(e).__name__}: {e}")
        return

    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"  → Saved: {output_file}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    # Process both invoices and CCCD cards
    docs_to_process = []

    # # Invoices
    # invoices_dir = Path("data/invoices")
    # if invoices_dir.exists():
    #     invoice_images = sorted(
    #         p for p in invoices_dir.glob("*.jpg")
    #         if "_annotated" not in p.name
    #     )
    #     docs_to_process.extend(invoice_images)

    # CCCD cards
    cccd_dir = Path("data/cccd/valid")
    if cccd_dir.exists():
        cccd_images = sorted(cccd_dir.glob("*.jpg"))
        docs_to_process.extend(cccd_images)

    if not docs_to_process:
        print("No images found to process")
        sys.exit(1)

    output_dir = Path("data/groundtruth_cccd")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(docs_to_process)} document(s) to process.")

    # Initialize PaddleOCR (CPU-friendly defaults)
    print("Initializing PaddleOCR...")
    from paddleocr import PaddleOCR
    ocr_engine = PaddleOCR(
        lang="vi",
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_rec_score_thresh=0.5,
    )

    client = AsyncOpenAI(
        api_key=TOGETHER_API_KEY,
        base_url=TOGETHER_BASE_URL,
    )

    for image_path in docs_to_process:
        await process_image(client, ocr_engine, image_path, output_dir)

    print(f"\nDone. Ground-truth files saved to: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
