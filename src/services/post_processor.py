"""
Post-processing layer to reconcile VLM extraction with OCR output.
Validates extracted values, corrects hallucinations, and improves consistency.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from datetime import datetime
from pydantic import BaseModel
from src.core.logger import logger


class CorrectionMetadata:
    """Track corrections made during post-processing."""
    def __init__(self):
        self.corrections: List[Dict[str, Any]] = []
        self.validations_passed: int = 0
        self.validations_failed: int = 0

    def add_correction(self, field_path: str, reason: str, original: Any, corrected: Any, ocr_match: Optional[str] = None):
        self.corrections.append({
            "field": field_path,
            "reason": reason,
            "original": original,
            "corrected": corrected,
            "ocr_match": ocr_match,
        })

    def to_dict(self):
        return {
            "total_corrections": len(self.corrections),
            "validations_passed": self.validations_passed,
            "validations_failed": self.validations_failed,
            "corrections": self.corrections,
        }


import json

def extract_ocr_text(ocr_context: str) -> List[str]:
    """Parse OCR context into list of text strings."""
    lines = ocr_context.strip().split('\n')
    texts = []
    for line in lines:
        try:
            # Format: {"t": "text", "b": [x1, y1, x2, y2]}
            data = json.loads(line)
            if 't' in data:
                text = data['t'].strip()
                if text:
                    texts.append(text)
        except Exception:
            pass
    return texts


def fuzzy_match(value: str, candidates: List[str], threshold: float = 0.85) -> Optional[Tuple[str, float]]:
    """
    Find best fuzzy match in OCR text candidates.
    Returns (matched_text, confidence) or None.

    Uses NFC normalization instead of lowercasing to preserve Vietnamese
    diacritics (e.g. "Hà" vs "Ha" are not equivalent).
    """
    if not value or not candidates:
        return None

    value_norm = unicodedata.normalize("NFC", value.strip())
    best_match = None
    best_ratio = 0.0

    for candidate in candidates:
        candidate_norm = unicodedata.normalize("NFC", candidate.strip())
        if value_norm == candidate_norm:
            return (candidate, 1.0)
        if value_norm in candidate_norm or candidate_norm in value_norm:
            ratio = SequenceMatcher(None, value_norm, candidate_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = candidate

    if best_ratio >= threshold:
        return (best_match, best_ratio)
    return None


def normalize_date(value: str) -> Optional[str]:
    """Attempt to normalize date to consistent format (DD/MM/YYYY)."""
    if not value or len(value.strip()) < 5:
        return None

    value = value.strip()
    # Already in DD/MM/YYYY format
    if re.match(r'^\d{2}/\d{2}/\d{4}$', value):
        return value

    # Try common formats
    formats = [
        '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y',
        '%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d',
        '%d %m %Y', '%Y %m %d',
        '%d%m%Y', '%Y%m%d',
        '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime('%d/%m/%Y')
        except ValueError:
            pass
    return None


def normalize_number(value: str) -> Optional[str]:
    """Normalize numbers: remove extra spaces, standardize separators."""
    if not value:
        return None

    value = value.strip()
    # Remove spaces within number
    value = re.sub(r'\s+', '', value)
    return value if value else None


def is_vietnamese_id_number(value: str) -> bool:
    """Check if value looks like a Vietnamese ID number."""
    value = re.sub(r'\D', '', value)  # Keep only digits
    return 12 <= len(value) <= 13


def is_tax_code(value: str) -> bool:
    """Check if value looks like a tax code (10-13 digits)."""
    value = re.sub(r'\D', '', value)
    return 10 <= len(value) <= 13


def validate_field_value(field_name: str, value: Any, ocr_texts: List[str]) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """
    Validate and correct a single field value against OCR.
    Returns (corrected_value, correction_info or None).
    """
    if value is None:
        return None, None

    # Handle BBoxField objects (value + bounding_box structure)
    if isinstance(value, dict) and 'value' in value:
        field_value = value['value']
        field_bbox = value.get('bounding_box')
    else:
        field_value = value
        field_bbox = None

    if field_value is None:
        return value, None

    correction_info = None
    corrected_value = field_value

    # Convert to string for comparison
    value_str = str(field_value).strip()

    # ID number validation
    if 'id' in field_name.lower() or 'number' in field_name.lower():
        if is_vietnamese_id_number(value_str):
            match = fuzzy_match(value_str, ocr_texts, threshold=0.95)
            if match:
                if match[1] < 1.0:
                    logger.debug(f"ID field '{field_name}': VLM value {value_str!r} has weak OCR match {match[0]!r} ({match[1]:.2f}), keeping VLM value")
            else:
                # Value absent from all OCR lines — likely hallucination
                logger.warning(f"ID field '{field_name}': VLM value {value_str!r} not found in OCR, flagging")

    # Tax code validation
    elif 'tax' in field_name.lower() or 'mst' in field_name.lower():
        normalized = normalize_number(value_str)
        if is_tax_code(normalized):
            match = fuzzy_match(normalized, ocr_texts, threshold=0.8)
            if match:
                corrected_value = match[0]
                correction_info = {"type": "tax_code_match", "original": value_str, "ocr_match": match[0]}

    # Currency/amount normalization
    elif any(x in field_name.lower() for x in ['amount', 'price', 'total', 'currency']):
        normalized = normalize_number(value_str)
        if normalized != value_str:
            correction_info = {"type": "number_normalization", "original": value_str, "normalized": normalized}
            corrected_value = normalized

    # Generic fuzzy matching for other fields
    else:
        if len(value_str) > 2:
            match = fuzzy_match(value_str, ocr_texts, threshold=0.95)
            if match and match[1] >= 0.95:
                # Near-exact OCR match — safe to adopt the OCR spelling
                if match[0] != value_str:
                    corrected_value = match[0]
                    correction_info = {"type": "fuzzy_correction", "original": value_str, "ocr_match": match[0], "confidence": match[1]}
            elif not match:
                logger.debug(f"Field '{field_name}': VLM value {value_str!r} not found in OCR")

    # Return corrected value in original format
    if isinstance(value, dict) and 'value' in value:
        return {**value, 'value': corrected_value}, correction_info
    return corrected_value, correction_info


def post_process_extraction(
    extraction_dict: Dict[str, Any],
    ocr_context: str,
    schema_class: Optional[type[BaseModel]] = None,
    route_key: str = "general",
) -> Tuple[Dict[str, Any], CorrectionMetadata]:
    """
    Post-process VLM extraction to reconcile with OCR.

    Args:
        extraction_dict: VLM extraction output (as dict)
        ocr_context: OCR context string
        schema_class: Pydantic schema (optional, for type info)
        route_key: Document type ("invoice", "id_card", "general")

    Returns:
        (corrected_extraction_dict, correction_metadata)
    """
    if not extraction_dict:
        return extraction_dict, CorrectionMetadata()

    ocr_texts = extract_ocr_text(ocr_context)
    metadata = CorrectionMetadata()
    corrected = {}

    def process_value(key: str, value: Any, path: str = "") -> Any:
        """Recursively process and validate field values."""
        full_path = f"{path}.{key}" if path else key

        if value is None:
            metadata.validations_passed += 1
            return None

        # Handle nested objects (vendor, items, etc.)
        if isinstance(value, dict) and 'value' not in value and 'bounding_box' not in value:
            return {k: process_value(k, v, full_path) for k, v in value.items()}

        # Handle lists (items, recipients, etc.)
        if isinstance(value, list):
            return [process_value(str(i), item, full_path) for i, item in enumerate(value)]

        # Validate and correct field
        corrected_value, correction = validate_field_value(full_path, value, ocr_texts)

        if correction:
            metadata.add_correction(full_path, correction.get("type", "unknown"), value, corrected_value, correction.get("ocr_match"))
            logger.debug(f"Correction: {full_path} → {correction}")
            metadata.validations_failed += 1
        else:
            metadata.validations_passed += 1

        return corrected_value

    # Process all fields
    for key, value in extraction_dict.items():
        corrected[key] = process_value(key, value)

    return corrected, metadata
