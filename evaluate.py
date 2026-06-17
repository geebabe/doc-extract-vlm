#!/usr/bin/env python3
"""
Evaluate OCR service against ground truth.

Compares extracted values (exact match) between API predictions and ground truth JSON files.
Ignores bounding boxes and null values.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import argparse
import requests
from collections import defaultdict


def flatten_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dict structure, handling lists and BBoxField objects."""
    flat = {}
    for key, val in d.items():
        if isinstance(val, dict):
            if "value" in val:  # BBoxField or similar
                field_key = f"{prefix}{key}" if prefix else key
                flat[field_key] = val.get("value")
            elif "name" in val:  # vendor.name case
                nested = flatten_dict(val, prefix=f"{prefix}{key}.")
                flat.update(nested)
            else:
                nested = flatten_dict(val, prefix=f"{prefix}{key}.")
                flat.update(nested)
        elif isinstance(val, list):
            # For items array: flatten each item with index
            for i, item in enumerate(val):
                if isinstance(item, dict):
                    nested = flatten_dict(item, prefix=f"{prefix}{key}[{i}].")
                    flat.update(nested)
        else:
            field_key = f"{prefix}{key}" if prefix else key
            flat[field_key] = val
    return flat


def extract_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only non-null values from nested structure."""
    flat = flatten_dict(data)
    return {k: v for k, v in flat.items() if v is not None}


def compare_predictions(
    gt_file: Path,
    pred_file: Path,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Compare ground truth vs prediction.

    Returns:
        (results_dict, errors_list)
    """
    with open(gt_file) as f:
        gt_data = json.load(f)
    with open(pred_file) as f:
        pred_data = json.load(f)

    gt_values = extract_values(gt_data)
    pred_values = extract_values(pred_data)

    results = {
        "gt_fields": len(gt_values),
        "pred_fields": len(pred_values),
        "common_fields": 0,
        "correct": 0,
        "incorrect": 0,
        "accuracy": 0.0,
        "missing_in_pred": [],
        "extra_in_pred": [],
        "mismatches": [],
    }

    # Fields in both
    common = set(gt_values.keys()) & set(pred_values.keys())
    results["common_fields"] = len(common)

    errors = []

    for field in common:
        gt_val = gt_values[field]
        pred_val = pred_values[field]
        if str(gt_val) == str(pred_val):
            results["correct"] += 1
        else:
            results["incorrect"] += 1
            results["mismatches"].append({
                "field": field,
                "expected": gt_val,
                "predicted": pred_val,
            })
            errors.append(f"  MISMATCH {field}: expected '{gt_val}' got '{pred_val}'")

    # Missing in prediction
    missing = set(gt_values.keys()) - set(pred_values.keys())
    results["missing_in_pred"] = list(missing)
    for field in missing:
        errors.append(f"  MISSING {field}: expected '{gt_values[field]}'")

    # Extra in prediction
    extra = set(pred_values.keys()) - set(gt_values.keys())
    results["extra_in_pred"] = list(extra)
    for field in extra:
        errors.append(f"  EXTRA {field}: got '{pred_values[field]}'")

    if results["common_fields"] > 0:
        results["accuracy"] = results["correct"] / results["common_fields"]

    return results, errors


def infer_batch(
    image_dir: Path,
    api_url: str,
    doc_type: str,
    output_dir: Path,
) -> None:
    """Infer all images in directory and save results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    image_files = sorted([f for f in image_dir.rglob("*") if f.suffix.lower() in {".jpg", ".jpeg", ".png"}])

    print(f"Found {len(image_files)} images in {image_dir}")

    for i, img_path in enumerate(image_files, 1):
        pred_file = output_dir / f"{img_path.stem}.json"

        if pred_file.exists():
            print(f"[{i}/{len(image_files)}] {img_path.name} -> (cached)")
            continue

        print(f"[{i}/{len(image_files)}] {img_path.name} -> inferring...", end=" ", flush=True)

        try:
            with open(img_path, "rb") as f:
                files = {"file": f}
                resp = requests.post(f"{api_url}/{doc_type}/file", files=files, timeout=60)

            if resp.status_code != 200:
                print(f"ERROR {resp.status_code}")
                continue

            data = resp.json()
            if not data.get("success"):
                print(f"FAILED: {data.get('error', 'unknown error')}")
                continue

            with open(pred_file, "w") as f:
                json.dump(data.get("data", {}), f, indent=2)
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")


def evaluate(
    gt_dir: Path,
    pred_dir: Path,
) -> None:
    """Evaluate all predictions against ground truth."""

    gt_files = sorted(gt_dir.glob("*.json"))
    print(f"Found {len(gt_files)} ground truth files\n")

    stats = defaultdict(int)
    all_errors = []

    for gt_file in gt_files:
        pred_file = pred_dir / gt_file.name

        if not pred_file.exists():
            print(f"❌ {gt_file.name}: prediction file missing")
            all_errors.append(f"{gt_file.name}: missing prediction")
            continue

        results, errors = compare_predictions(gt_file, pred_file)

        # Summary
        common = results["common_fields"]
        correct = results["correct"]
        incorrect = results["incorrect"]
        missing = len(results["missing_in_pred"])
        extra = len(results["extra_in_pred"])
        acc = results["accuracy"]

        stats["total_files"] += 1
        stats["total_fields"] += common
        stats["total_correct"] += correct
        stats["total_incorrect"] += incorrect
        stats["total_missing"] += missing
        stats["total_extra"] += extra

        status = "✓" if acc == 1.0 else "✗"
        print(f"{status} {gt_file.name}")
        print(f"   Accuracy: {acc:.1%} ({correct}/{common} fields correct)", end="")

        if missing > 0 or extra > 0 or incorrect > 0:
            print(f" | Missing: {missing}, Extra: {extra}, Mismatches: {incorrect}")
            for err in errors:
                print(err)
        else:
            print()

        all_errors.extend([(gt_file.name, e) for e in errors])

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    if stats["total_files"] == 0:
        print("No files evaluated.")
        return

    total_acc = stats["total_correct"] / stats["total_fields"] if stats["total_fields"] > 0 else 0
    print(f"Files evaluated: {stats['total_files']}")
    print(f"Total fields: {stats['total_fields']}")
    print(f"Correct: {stats['total_correct']}")
    print(f"Incorrect: {stats['total_incorrect']}")
    print(f"Missing: {stats['total_missing']}")
    print(f"Extra: {stats['total_extra']}")
    print(f"Overall accuracy: {total_acc:.1%}")

    # Error breakdown
    if all_errors:
        print("\n" + "="*80)
        print("ERROR ANALYSIS")
        print("="*80)

        error_types = defaultdict(list)
        for filename, error in all_errors:
            if "MISMATCH" in error:
                error_types["mismatches"].append((filename, error))
            elif "MISSING" in error:
                error_types["missing"].append((filename, error))
            elif "EXTRA" in error:
                error_types["extra"].append((filename, error))

        for error_type in ["mismatches", "missing", "extra"]:
            if error_type in error_types:
                print(f"\n{error_type.upper()} ({len(error_types[error_type])} errors):")
                for filename, error in error_types[error_type][:20]:  # Show first 20
                    print(f"  {filename}: {error.strip()}")
                if len(error_types[error_type]) > 20:
                    print(f"  ... and {len(error_types[error_type]) - 20} more")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate OCR service predictions against ground truth"
    )
    parser.add_argument(
        "--api-url",
        default="https://8000-01ks1npneehwvsd7pscdgjwp3m.cloudspaces.litng.ai",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--doc-type",
        required=True,
        choices=["invoice", "id_card"],
        help="Document type",
    )
    parser.add_argument(
        "--infer",
        action="store_true",
        help="Run inference before evaluation",
    )

    args = parser.parse_args()

    base_dir = Path(__file__).parent / "data"

    if args.doc_type == "invoice":
        gt_dir = base_dir / "groundtruth"
        image_dir = base_dir / "invoices"
    else:  # id_card
        gt_dir = base_dir / "groundtruth_cccd"
        image_dir = base_dir / "cccd"

    pred_dir = base_dir / f"predictions_{args.doc_type}"

    if args.infer:
        print(f"Running inference on {image_dir}...\n")
        infer_batch(image_dir, args.api_url, args.doc_type, pred_dir)
        print()

    print(f"Evaluating {args.doc_type}...\n")
    evaluate(gt_dir, pred_dir)


if __name__ == "__main__":
    main()
