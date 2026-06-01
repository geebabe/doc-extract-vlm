#!/usr/bin/env python3
"""
compare_results.py — Compare batch inference results with groundtruth.

Usage:
    python compare_results.py --results data/output/results.json --groundtruth data/groundtruth
"""

import argparse
import json
import os
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


FIELDS_TO_COMPARE = [
    ("Invoice Number", ["invoice_number"]),
    ("Invoice Date", ["invoice_date"]),
    ("Vendor Name", ["vendor", "name"]),
    ("Vendor Address", ["vendor", "address"]),
    ("Vendor Tax Code", ["vendor", "tax_code"]),
    ("Vendor Phone", ["vendor", "phone"]),
    ("Total Amount", ["total_amount"]),
    ("Currency", ["currency"]),
]


def get_nested_val(d: Any, path: List[str]) -> Any:
    curr = d
    for step in path:
        if isinstance(curr, dict):
            curr = curr.get(step)
        else:
            return None
    return curr


def normalize_val(val: Any) -> str:
    """Normalize string values for robust comparison (unicode NFC, strip, lowercase)."""
    if val is None:
        return ""
    # Extract value from dictionary if wrapped (e.g. {"value": "..."})
    if isinstance(val, dict) and "value" in val:
        val = val["value"]
    if val is None:
        return ""
    
    s = str(val).strip().lower()
    s = unicodedata.normalize("NFKC", s)
    return " ".join(s.split())


def compare_boxes(pred_box: Optional[List[int]], gt_box: Optional[List[int]], tolerance: int = 50) -> bool:
    """Check if bounding boxes are roughly similar (optional metric)."""
    if not pred_box and not gt_box:
        return True
    if not pred_box or not gt_box:
        return False
    if len(pred_box) != 4 or len(gt_box) != 4:
        return False
    
    # Check if coords are within tolerance limit
    return all(abs(p - g) <= tolerance for p, g in zip(pred_box, gt_box))


def main():
    parser = argparse.ArgumentParser(
        description="Compare batch inference results with ground truth invoices"
    )
    parser.add_argument(
        "--results", "-r",
        required=True,
        help="Path to results file (JSON array or JSONL).",
    )
    parser.add_argument(
        "--groundtruth", "-g",
        default="data/groundtruth",
        help="Directory containing groundtruth JSON files.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed file-by-file mismatches.",
    )
    args = parser.parse_args()

    results_path = Path(args.results)
    gt_dir = Path(args.groundtruth)

    if not results_path.exists():
        print(f"❌ Results file not found: {results_path}")
        return
    if not gt_dir.is_dir():
        print(f"❌ Groundtruth directory not found: {gt_dir}")
        return

    # Load results
    print(f"📖 Loading results from {results_path}...")
    try:
        with open(results_path) as f:
            content = f.read().strip()
            if content.startswith("["):
                # JSON array
                predictions = json.loads(content)
            else:
                # JSONL
                predictions = [json.loads(line) for line in content.splitlines() if line.strip()]
    except Exception as e:
        print(f"❌ Failed to parse results file: {e}")
        return

    print(f"Loaded {len(predictions)} prediction(s).")

    # Metrics trackers
    total_matched_files = 0
    metrics = {
        name: {"matched": 0, "total": 0, "correct": 0}
        for name, _ in FIELDS_TO_COMPARE
    }
    # Add metrics for line items
    metrics["Item Count"] = {"matched": 0, "total": 0, "correct": 0}
    metrics["Item Descriptions"] = {"matched": 0, "total": 0, "correct": 0}

    mismatches = []

    for pred in predictions:
        if not pred.get("success", False):
            continue

        # Get source filename stem
        source_path = pred.get("source")
        if not source_path:
            continue
        
        stem = Path(source_path).stem
        # Look for corresponding groundtruth file
        gt_file = gt_dir / f"{stem}.json"
        
        if not gt_file.exists():
            if args.verbose:
                print(f"⚠️  No groundtruth file found for {stem} ({gt_file})")
            continue

        total_matched_files += 1

        with open(gt_file) as f:
            gt_data = json.load(f)

        pred_data = pred.get("data") or {}

        # 1. Compare standard fields
        for field_name, path in FIELDS_TO_COMPARE:
            gt_field_node = get_nested_val(gt_data, path)
            pred_field_node = get_nested_val(pred_data, path)

            # Both groundtruth and predictions have {"value": ..., "bbox"/"bounding_box": ...}
            # Or they might be None
            gt_val = gt_field_node.get("value") if isinstance(gt_field_node, dict) else None
            pred_val = pred_field_node.get("value") if isinstance(pred_field_node, dict) else None

            # Only count as part of evaluation if the field exists in groundtruth (i.e. is not null)
            # or if predicted is non-null when gt is null.
            if gt_val is not None or pred_val is not None:
                metrics[field_name]["total"] += 1
                
                norm_gt = normalize_val(gt_val)
                norm_pred = normalize_val(pred_val)
                
                is_correct = (norm_gt == norm_pred)
                if is_correct:
                    metrics[field_name]["correct"] += 1
                else:
                    mismatches.append({
                        "file": stem,
                        "field": field_name,
                        "expected": gt_val,
                        "actual": pred_val
                    })

        # 2. Compare line items
        gt_items = gt_data.get("items") or []
        pred_items = pred_data.get("items") or []

        # Item count metric
        metrics["Item Count"]["total"] += 1
        if len(gt_items) == len(pred_items):
            metrics["Item Count"]["correct"] += 1
        else:
            mismatches.append({
                "file": stem,
                "field": "Item Count",
                "expected": f"{len(gt_items)} items",
                "actual": f"{len(pred_items)} items"
            })

        # Item descriptions comparison
        for i, gt_item in enumerate(gt_items):
            metrics["Item Descriptions"]["total"] += 1
            gt_desc_node = gt_item.get("description")
            gt_desc = gt_desc_node.get("value") if isinstance(gt_desc_node, dict) else None
            
            if i < len(pred_items):
                pred_item = pred_items[i]
                pred_desc_node = pred_item.get("description")
                pred_desc = pred_desc_node.get("value") if isinstance(pred_desc_node, dict) else None
                
                if normalize_val(gt_desc) == normalize_val(pred_desc):
                    metrics["Item Descriptions"]["correct"] += 1
                else:
                    mismatches.append({
                        "file": stem,
                        "field": f"Item Description [{i}]",
                        "expected": gt_desc,
                        "actual": pred_desc
                    })
            else:
                mismatches.append({
                    "file": stem,
                    "field": f"Item Description [{i}]",
                    "expected": gt_desc,
                    "actual": "<missing>"
                })

    # Summary
    print(f"\n{'═'*65}")
    print(f" 📊  Evaluation Results (Matched Files: {total_matched_files})")
    print(f"{'─'*65}")
    print(f"  {'Field Name':<25} | {'Correct':<8} / {'Total':<6} | {'Accuracy':<10}")
    print(f"{'─'*65}")
    
    total_correct = 0
    total_evals = 0
    
    for field_name, stats in metrics.items():
        corr = stats["correct"]
        tot = stats["total"]
        acc_str = f"{(corr/tot*100):.1f}%" if tot > 0 else "N/A"
        print(f"  {field_name:<25} | {corr:<8} / {tot:<6} | {acc_str:<10}")
        
        total_correct += corr
        total_evals += tot

    overall_acc = f"{(total_correct/total_evals*100):.1f}%" if total_evals > 0 else "N/A"
    print(f"{'─'*65}")
    print(f"  {'OVERALL FIELD ACCURACY':<25} | {total_correct:<8} / {total_evals:<6} | {overall_acc:<10}")
    print(f"{'═'*65}\n")

    # Mismatches printout
    if args.verbose and mismatches:
        print(f"🔍 Detailed Mismatches:")
        print(f"{'─'*100}")
        print(f" {'File':<30} | {'Field':<22} | {'Expected (Groundtruth)':<20} | {'Actual (Predicted)':<20}")
        print(f"{'─'*100}")
        for m in mismatches[:40]:  # Limit to first 40 to avoid terminal flooding
            exp = str(m['expected']) if m['expected'] is not None else "None"
            act = str(m['actual']) if m['actual'] is not None else "None"
            print(f" {m['file'][:30]:<30} | {m['field'][:22]:<22} | {exp[:20]:<20} | {act[:20]:<20}")
        if len(mismatches) > 40:
            print(f" ... and {len(mismatches) - 40} more mismatches.")
        print(f"{'─'*100}\n")


if __name__ == "__main__":
    main()
