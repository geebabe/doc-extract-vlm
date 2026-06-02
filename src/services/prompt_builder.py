"""
Dynamic prompt builder for structured document extraction.
Supports invoice, ID card, and general document routes with shared rules and route-specific field definitions.
"""

import json
from dataclasses import dataclass


BBOX_FIELD_FORMAT = """\
Every field MUST be returned as an object with this exact structure, never as a
bare null at the top level:
  {
    "value": "<exact text from document, or null if absent>",
    "bounding_box": [xmin, ymin, xmax, ymax]   (integers, normalized to [0, 1000] scale, or null)
  }

CORRECT for an absent field:    "issue_place": {"value": null, "bounding_box": null}
WRONG for an absent field:      "issue_place": null

Wrapping null inside the object preserves the schema; emitting top-level null is
not allowed even if the schema technically accepts it."""


SHARED_RULES = """\
=== STRICT RULES ===

1. NULL VALUES: If a field is not present anywhere in the document — not visually, not in OCR —
   output: {"value": null, "bounding_box": null}

2. NO HALLUCINATION: Do not infer, guess, or fabricate values. If uncertain, output null.

3. EXACT PRESERVATION: Copy the value exactly as it appears on the document, including:
   - Spacing, punctuation, and capitalization
   - Numeric separators (e.g., "1.234.567" not "1234567")
   - Date formats (e.g., "15/03/2024" not "2024-03-15")
   - Vietnamese diacritics (e.g., "Công ty TNHH", not "Cong ty TNHH")

4. BOUNDING BOX: Report the bounding box as [xmin, ymin, xmax, ymax] normalized to [0, 1000].
   Use the OCR context below as a reference for coordinates. If you cannot determine a bbox,
   set it to null — do NOT fabricate coordinates.

5. MULTI-LINE VALUES: If a field spans multiple lines (e.g., a long address), concatenate
   with a single space and compute a bbox that covers all lines.

6. JSON-ONLY OUTPUT: Return strictly valid JSON matching the provided schema.
   No markdown, no conversational fillers, and no explanations."""


INVOICE_FIELD_DEFS = """\
=== SCHEMA FIELD DEFINITIONS ===

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

SPECIAL RULES FOR ITEMS LIST: Extract ALL line items from the invoice table. If there are no items,
output an empty list []. Each item must have at minimum a "description". Set missing sub-fields to
{"value": null, "bounding_box": null}. Do not merge rows — one object per invoice line item."""


CCCD_FRONT_FIELD_DEFS = """\
=== THIS IS THE FRONT SIDE OF A VIETNAMESE CCCD CARD ===

Extract every field that is readable from this front-side image. Fields that are
only on the back side (issue_date, issue_place) should be set to null.

=== SCHEMA FIELD DEFINITIONS ===

- id_number             : ID number (Số căn cước công dân / Số/No.) printed near
                          the top or below the portrait. Extract the exact digits.
- full_name             : Full name (Họ và tên / Full name). Printed in plain text.
- date_of_birth         : Date of birth (Ngày sinh / Date of birth).
                          Preserve exact format (e.g. "01/01/1990").
- gender                : Gender (Giới tính / Sex). Values: "Nam" or "Nữ".
- nationality           : Nationality (Quốc tịch / Nationality). Usually "Việt Nam".
- place_of_origin       : Place of origin (Quê quán / Place of origin).
- place_of_residence    : Place of residence (Nơi thường trú / Place of residence).
                          May span multiple lines — concatenate with a single space.
- expiry_date           : Expiry date (Có giá trị đến / Date of expiry).
                          Printed on newer cards on the front.

- issue_date            : Set to {"value": null, "bounding_box": null} — back side only.
- issue_place           : Set to {"value": null, "bounding_box": null} — back side only.

=== HARD RULES ===

1. Extract every field that appears on this front-side image.
2. Do NOT null out a field that is visually readable or appears in the OCR hints.
3. issue_date and issue_place are always null for front-side images."""


CCCD_BACK_FIELD_DEFS = """\
=== THIS IS THE BACK SIDE OF A VIETNAMESE CCCD CARD ===

The back side typically contains: MRZ lines, fingerprint area, issue date/place,
and sometimes place_of_residence. Extract every field visible. The MRZ is the
primary source for id_number, date_of_birth, gender, expiry_date, nationality,
and full_name when printed text is unclear.

=== SCHEMA FIELD DEFINITIONS ===

- id_number             : Digits from the MRZ line starting with "IDVNM"
                          (positions 6–17 after the prefix). Also compare to any
                          printed "Số:" label on the card.
- full_name             : Decoded from the MRZ name section (after "<<").
                          Replace "<" with spaces; restore obvious Vietnamese
                          diacritics (e.g. "PHAM<<THI<NHAT<LE" → "PHẠM THỊ NHẬT LỆ").
                          If printed plain text for full_name is visible, prefer that.
- date_of_birth         : Encoded as YYMMDD in the MRZ (e.g. "900101" → "01/01/1990").
                          If printed text is visible, prefer that.
- gender                : M → "Nam", F → "Nữ" (from MRZ). If printed text visible, prefer that.
- nationality           : "VNM" in MRZ → "Việt Nam".
- expiry_date           : Encoded as YYMMDD in the MRZ second line (e.g. "350101" → "01/01/2035").
                          Also may be printed as "Có giá trị đến: DD/MM/YYYY".
- issue_date            : Date of issue (Ngày, tháng, năm / Date of issue).
                          Printed near the issuing officer's signature.
- issue_place           : Place of issue (Nơi cấp). Often
                          "CỤC TRƯỞNG CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI"
                          or "BỘ CÔNG AN".
- place_of_residence    : Printed residence address on the back (older CCCD generation).
                          If not visible on this back side, set to null.

- place_of_origin       : Set to {"value": null, "bounding_box": null} — front side only.

=== HARD RULES ===

1. The MRZ is machine-readable ground truth — always decode it for id_number,
   date_of_birth, gender, expiry_date, nationality, and full_name.
2. For fields where both MRZ and printed text are visible, prefer the printed text.
3. place_of_origin is always null for back-side images.
4. Never return ALL fields as null if MRZ lines are visible."""


def detect_cccd_side(ocr_context: str) -> str:
    """
    Detect which side of the CCCD is in the image using OCR text.
    Returns "front", "back", or "unknown".

    Detection logic:
    - "back"  : MRZ line found (starts with "IDVNM" or contains "IDVNM")
    - "front" : "CĂN CƯỚC" or "CAN CUOC" header found (no MRZ)
    - "unknown": neither signal found; treat as front to avoid over-nulling
    """
    from src.services.post_processor import extract_ocr_text  # local import avoids circular deps
    texts = extract_ocr_text(ocr_context)
    combined = " ".join(texts).upper()

    has_mrz = any("IDVNM" in t.upper() for t in texts)
    has_front_header = "CĂN CƯỚC" in combined or "CAN CUOC" in combined

    if has_mrz:
        return "back"
    if has_front_header:
        return "front"
    return "unknown"


GENERAL_FIELD_DEFS = """\
=== SCHEMA FIELD DEFINITIONS ===

- title                 : Document title or heading.
                          Often found at the top of the document.
- document_number       : Document reference number or ID (e.g., report number, case ID, serial number).
                          Often labelled: "Number", "Reference", "ID", "Số hiệu", "Mã số".
- date                  : Document date or issue date.
                          Often labelled: "Date", "Issued", "Ngày", "Ngày lập".
- issuer                : Organization, person, or entity that issued or authored the document.
                          Often labelled: "Issued by", "From", "Author", "Cơ quan cấp".
- recipients            : List of recipients or intended parties (one entry per recipient).
                          Often labelled: "To", "Recipient", "Gửi tới", "Người nhận".
- summary               : Brief summary, abstract, or main content of the document.
- additional_fields     : List of key-value pairs for any other specific data points found in the document.
                          Each entry has a "key" (field name) and "value" (extracted data).
- full_text             : Optional: complete raw text of the document if desired for further processing.

SPECIAL RULES FOR ADDITIONAL_FIELDS: Extract any important information not covered by the standard fields.
If there are no additional fields, output an empty list []."""


@dataclass
class PromptConfig:
    """Configuration for a specific document extraction route."""
    role_description: str
    field_definitions: str
    user_prompt: str


PROMPT_CONFIGS = {
    "invoice": PromptConfig(
        role_description="You are a strict invoice data extraction engine used to build structured datasets.\nYour output will be used to extract critical business information, so accuracy is essential.",
        field_definitions=INVOICE_FIELD_DEFS,
        user_prompt="Extract structured invoice data from this image following the schema and rules above.",
    ),
    "id_card_front": PromptConfig(
        role_description="You are a strict Vietnamese CCCD (Căn Cước Công Dân) ID card data extraction engine.\nYour output will be used to extract identity information with high precision, so accuracy is critical.",
        field_definitions=CCCD_FRONT_FIELD_DEFS,
        user_prompt="Extract structured CCCD card data from this FRONT-SIDE image following the schema and rules above.",
    ),
    "id_card_back": PromptConfig(
        role_description="You are a strict Vietnamese CCCD (Căn Cước Công Dân) ID card data extraction engine.\nYour output will be used to extract identity information with high precision, so accuracy is critical.",
        field_definitions=CCCD_BACK_FIELD_DEFS,
        user_prompt="Extract structured CCCD card data from this BACK-SIDE image. Decode the MRZ lines if present.",
    ),
    "general": PromptConfig(
        role_description="You are an advanced document understanding system. Your goal is to extract structured information from the provided document image with high precision.",
        field_definitions=GENERAL_FIELD_DEFS,
        user_prompt="Analyze the attached document and perform structured extraction according to the schema.",
    ),
}
# Alias: "id_card" resolves to front by default; build_system_prompt overrides
# this at runtime based on OCR-detected card side.
PROMPT_CONFIGS["id_card"] = PROMPT_CONFIGS["id_card_front"]


OCR_UNAVAILABLE_SENTINELS = {"OCR_UNAVAILABLE", "OCR_EMPTY"}


VISION_ONLY_RULES = """\
=== STRICT RULES ===

1. NULL VALUES: Only set {"value": null, "bounding_box": null} when the field is genuinely
   absent from the image (e.g., a back-side-only field on a front-side photo). If the value
   IS visible in the image, you MUST extract it.

2. NO HALLUCINATION: Do not infer, guess, or fabricate values. If uncertain, output null.
   But uncertainty about coordinates is NOT a reason to null out a clearly visible value —
   set the bounding_box to null in that case and still return the value.

3. EXACT PRESERVATION: Copy the value exactly as it appears on the document, including:
   - Spacing, punctuation, and capitalization
   - Numeric separators (e.g., "1.234.567" not "1234567")
   - Date formats (e.g., "15/03/2024" not "2024-03-15")
   - Vietnamese diacritics (e.g., "Công ty TNHH", not "Cong ty TNHH")

4. BOUNDING BOX: OCR text-line coordinates are unavailable for this image. Set
   "bounding_box": null for every field. Do NOT fabricate coordinates.

5. MULTI-LINE VALUES: If a field spans multiple lines (e.g., a long address), concatenate
   with a single space.

6. JSON-ONLY OUTPUT: Return strictly valid JSON matching the provided schema.
   No markdown, no conversational fillers, and no explanations."""


def build_system_prompt(route_key: str, ocr_context: str) -> str:
    """
    Build a complete system prompt for a specific document extraction route.

    Args:
        route_key: Document type ("invoice", "id_card", "general", or custom)
        ocr_context: Preliminary OCR extraction results (normalized to [0, 1000]),
                     or one of OCR_UNAVAILABLE_SENTINELS when OCR could not run.

    Returns:
        Complete system prompt including role, field definitions, rules, and OCR context
    """
    # Resolve id_card to a side-specific config using OCR-based detection.
    if route_key == "id_card":
        ocr_failed = (ocr_context or "").strip() in OCR_UNAVAILABLE_SENTINELS
        if not ocr_failed:
            side = detect_cccd_side(ocr_context)
            resolved_key = "id_card_back" if side == "back" else "id_card_front"
        else:
            resolved_key = "id_card_front"  # vision-only: assume front, safer default
    else:
        resolved_key = route_key

    config = PROMPT_CONFIGS.get(resolved_key) or PROMPT_CONFIGS["general"]

    ocr_failed = (ocr_context or "").strip() in OCR_UNAVAILABLE_SENTINELS

    if ocr_failed:
        # Vision-only path: drop the OCR hint section and relax bbox requirements
        # so the model still extracts fields from the image directly.
        prompt = f"""{config.role_description}

### KEY INSTRUCTIONS:
1. **VISION-ONLY MODE**: OCR text-line hints are unavailable for this image. Extract all
   fields by visually reading the document. Do not refuse to extract just because OCR is missing.
2. **OUTPUT FORMAT**: Return strictly valid JSON matching the provided schema.
3. **BOUNDING BOXES**: Without OCR text-line coordinates, set every "bounding_box" to null.
   Focus on extracting accurate VALUES.

{BBOX_FIELD_FORMAT}

### CONTEXTUAL HINTS:
- **Language**: The document is primarily in Vietnamese. Pay close attention to diacritics and specialized terms.
- **No OCR available**: Read the document directly from the image. Every visible field must be returned.

{config.field_definitions}

{VISION_ONLY_RULES}"""
        return prompt

    prompt = f"""{config.role_description}

### KEY INSTRUCTIONS:
1. **NATIVE GROUNDING**: For every field, you must provide the extracted text (value) and its precise coordinates (bounding_box).
2. **COORDINATE SYSTEM**: All bounding boxes MUST be normalized to a scale of [0, 1000]. The format is [xmin, ymin, xmax, ymax].
3. **OUTPUT FORMAT**: Return strictly valid JSON matching the provided schema.

{BBOX_FIELD_FORMAT}

### CONTEXTUAL HINTS:
- **Language**: The document is primarily in Vietnamese. Pay close attention to diacritics and specialized terms.
- **Preliminary OCR**: Below is a draft OCR extraction in JSON format ({{"t": text, "b": [xmin, ymin, xmax, ymax]}}, normalized to [0, 1000]) to help you identify characters and locations. Use these as hints, but rely on your visual perception if the image contradicts these hints:
{ocr_context}

{config.field_definitions}

{SHARED_RULES}"""

    return prompt


def get_user_prompt(route_key: str) -> str:
    """
    Get the user-facing prompt for a specific document extraction route.

    Args:
        route_key: Document type ("invoice", "id_card", "general", or custom)

    Returns:
        Route-specific user prompt (falls back to "general" if key not found)
    """
    # id_card falls back to the front config user prompt; the system prompt
    # already contains the authoritative side information from detect_cccd_side.
    lookup_key = "id_card_front" if route_key == "id_card" else route_key
    config = PROMPT_CONFIGS.get(lookup_key) or PROMPT_CONFIGS["general"]
    return config.user_prompt
