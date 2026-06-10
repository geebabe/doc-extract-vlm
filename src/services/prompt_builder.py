"""
Dynamic prompt builder for structured document extraction.
Supports invoice, ID card, and general document routes with shared rules and route-specific field definitions.
"""

import json
import textwrap
from dataclasses import dataclass
from typing import get_args, get_origin
from pydantic import BaseModel
from pydantic.fields import FieldInfo


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


# ── hard-rules blocks kept here because they are logic, not field descriptions ──

_INVOICE_SPECIAL_RULES = """\
SPECIAL RULES FOR ITEMS LIST: Extract ALL line items from the invoice table. If there are no items,
output an empty list []. Each item must have at minimum a "description". Set missing sub-fields to
{"value": null, "bounding_box": null}. Do not merge rows — one object per invoice line item."""

_CCCD_FRONT_CONTEXT = """\
=== THIS IS THE FRONT SIDE OF A VIETNAMESE CCCD CARD ===

Extract every field that is readable from this front-side image. Fields that are
only on the back side (issue_date, issue_place) should be set to null.

=== HARD RULES ===

1. Extract every field that appears on this front-side image.
2. Do NOT null out a field that is visually readable or appears in the OCR hints.
3. issue_date and issue_place are always null for front-side images."""

_CCCD_BACK_CONTEXT = """\
=== THIS IS THE BACK SIDE OF A VIETNAMESE CCCD CARD ===

The back side typically contains: MRZ lines, fingerprint area, issue date/place,
and sometimes place_of_residence. Extract every field visible. The MRZ is the
primary source for id_number, date_of_birth, gender, expiry_date, nationality,
and full_name when printed text is unclear.

=== HARD RULES ===

1. The MRZ is machine-readable ground truth — always decode it for id_number,
   date_of_birth, gender, expiry_date, nationality, and full_name.
2. For fields where both MRZ and printed text are visible, prefer the printed text.
3. place_of_origin is always null for back-side images.
4. Never return ALL fields as null if MRZ lines are visible.

=== MRZ DECODING NOTES ===

- id_number   : digits from the MRZ line starting with "IDVNM" (positions 6–17 after the prefix).
- full_name   : decoded from the MRZ name section (after "<<"). Replace "<" with spaces; restore
                obvious Vietnamese diacritics (e.g. "PHAM<<THI<NHAT<LE" → "PHẠM THỊ NHẬT LỆ").
                If printed plain text for full_name is visible, prefer that.
- date_of_birth: encoded as YYMMDD (e.g. "900101" → "01/01/1990").
- gender      : M → "Nam", F → "Nữ". If printed text visible, prefer that.
- nationality : "VNM" → "Việt Nam".
- expiry_date : encoded as YYMMDD in the MRZ second line (e.g. "350101" → "01/01/2035").
                Also may be printed as "Có giá trị đến: DD/MM/YYYY"."""

_GENERAL_SPECIAL_RULES = """\
SPECIAL RULES FOR ADDITIONAL_FIELDS: Extract any important information not covered by the standard fields.
If there are no additional fields, output an empty list []."""


def generate_field_definitions(schema_class: type[BaseModel], _prefix: str = "", _indent: int = 0) -> str:
    """
    Build a FIELD_DEFINITIONS block by reflecting on a Pydantic schema.

    - Top-level BBoxField leaves: one bullet per field using Field(description=...).
    - Nested BaseModel (non-BBoxField): recurse with dot-prefix notation.
    - List[BaseModel]: show the sub-field indented with a sub-bullet.
    - List[BBoxField] / List[str]: single bullet noting it's a list.
    """
    from src.schemas.base import BBoxField  # local import avoids circular deps at module load

    lines: list[str] = []
    indent = "    " * _indent
    sub_indent = "    " * (_indent + 1)

    for field_name, field_info in schema_class.model_fields.items():
        full_name = f"{_prefix}{field_name}" if _prefix else field_name
        description = field_info.description or ""
        annotation = field_info.annotation

        # Unwrap Optional[X] → X
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin is type(None):
            continue
        # Optional[X] comes through as Union[X, None]
        import types
        if origin is types.UnionType or str(origin) == "typing.Union":
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                annotation = non_none[0]
                origin = get_origin(annotation)
                args = get_args(annotation)

        is_list = origin is list
        inner_type = args[0] if (is_list and args) else None

        if is_list and inner_type and isinstance(inner_type, type) and issubclass(inner_type, BaseModel) and inner_type is not BBoxField:
            # e.g. items: List[InvoiceItem]
            lines.append(f"{indent}- {full_name:<22}: {description}")
            sub_lines = generate_field_definitions(inner_type, _prefix=f"{full_name}[].", _indent=_indent + 1)
            if sub_lines:
                lines.append(sub_lines)
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation is not BBoxField:
            # e.g. vendor: VendorInfo
            lines.append(f"{indent}- {full_name:<22}: {description}")
            sub_lines = generate_field_definitions(annotation, _prefix=f"{full_name}.", _indent=_indent + 1)
            if sub_lines:
                lines.append(sub_lines)
        else:
            # Leaf field (BBoxField, str, Optional[str], List[BBoxField], …)
            lines.append(f"{indent}- {full_name:<22}: {description}")

    return "\n".join(lines)


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


def _build_field_defs_block(schema_class: type[BaseModel], extra_rules: str = "") -> str:
    body = generate_field_definitions(schema_class)
    block = f"=== SCHEMA FIELD DEFINITIONS ===\n\n{body}"
    if extra_rules:
        block += f"\n\n{extra_rules}"
    return block


@dataclass
class PromptConfig:
    """Configuration for a specific document extraction route."""
    role_description: str
    field_definitions: str
    user_prompt: str


def _make_prompt_configs() -> dict[str, "PromptConfig"]:
    from src.schemas.invoice import InvoiceExtraction
    from src.schemas.id_card import IDCardExtraction
    from src.schemas.general import GeneralDocumentExtraction

    return {
        "invoice": PromptConfig(
            role_description="You are a strict invoice data extraction engine used to build structured datasets.\nYour output will be used to extract critical business information, so accuracy is essential.",
            field_definitions=_build_field_defs_block(InvoiceExtraction, _INVOICE_SPECIAL_RULES),
            user_prompt="Extract structured invoice data from this image following the schema and rules above.",
        ),
        "id_card_front": PromptConfig(
            role_description="You are a strict Vietnamese CCCD (Căn Cước Công Dân) ID card data extraction engine.\nYour output will be used to extract identity information with high precision, so accuracy is critical.",
            field_definitions=f"{_CCCD_FRONT_CONTEXT}\n\n{_build_field_defs_block(IDCardExtraction)}",
            user_prompt="Extract structured CCCD card data from this FRONT-SIDE image following the schema and rules above.",
        ),
        "id_card_back": PromptConfig(
            role_description="You are a strict Vietnamese CCCD (Căn Cước Công Dân) ID card data extraction engine.\nYour output will be used to extract identity information with high precision, so accuracy is critical.",
            field_definitions=f"{_CCCD_BACK_CONTEXT}\n\n{_build_field_defs_block(IDCardExtraction)}",
            user_prompt="Extract structured CCCD card data from this BACK-SIDE image. Decode the MRZ lines if present.",
        ),
        "general": PromptConfig(
            role_description="You are an advanced document understanding system. Your goal is to extract structured information from the provided document image with high precision.",
            field_definitions=_build_field_defs_block(GeneralDocumentExtraction, _GENERAL_SPECIAL_RULES),
            user_prompt="Analyze the attached document and perform structured extraction according to the schema.",
        ),
    }


# Built once at import time; adding a new doc type only requires a schema + entry here.
PROMPT_CONFIGS: dict[str, PromptConfig] = _make_prompt_configs()
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
