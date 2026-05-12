"""
build_test_set.py — Package a curated review JSON into a test-set zip.

The zip contains:
  tasks/task_1.json ... task_N.json
  groundtruth/groundtruth_1.json ... groundtruth_N.json

Usage:
  uv run python scripts/build_test_set.py \
      --input data/test_review_subset_new35.json \
      --output test_set.zip

The input file must be JSONL (one JSON object per line), matching the
structure produced by data_process.py / sample_dummy_data.py.
"""
import sys
import os

if sys.prefix == sys.base_prefix:
    print("❌ Please run with uv: uv run python scripts/build_test_set.py", file=sys.stderr)
    sys.exit(1)

import json
import zipfile
import argparse
from pathlib import Path


def build_test_set(input_path: str, output_path: str) -> int:
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"❌ Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    if not lines:
        print("❌ Input file is empty.", file=sys.stderr)
        sys.exit(1)

    print(f"📂 Input  : {input_path}  ({len(lines)} reviews)")
    print(f"📦 Output : {output_path}")
    print()

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, line in enumerate(lines, 1):
            data = json.loads(line)

            # Normalise 'text' → 'review' for consistency with dummy dataset
            if "text" in data and "review" not in data:
                data["review"] = data["text"]

            # --- groundtruth: full record ---
            gt = json.dumps(data, indent=2, ensure_ascii=False)
            zf.writestr(f"groundtruth/groundtruth_{i}.json", gt)

            # --- task: identifiers only, no answer fields ---
            task_data = {
                "type": "user_behavior_simulation",
                "review_id": data.get("review_id"),
                "user_id":   data.get("user_id"),
                "item_id":   data.get("item_id"),
                "date":      data.get("date"),
            }
            task = json.dumps(task_data, indent=2, ensure_ascii=False)
            zf.writestr(f"tasks/task_{i}.json", task)

    size_kb = Path(output_path).stat().st_size / 1024
    print(f"✅ Packed {len(lines)} tasks + {len(lines)} groundtruth files")
    print(f"   → {output_path}  ({size_kb:.1f} KB)")
    return len(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Package curated review JSONL into a test-set zip for run_test.py"
    )
    parser.add_argument(
        "--input",  required=True,
        help="Path to JSONL review file (e.g. data/test_review_subset_new35.json)"
    )
    parser.add_argument(
        "--output", default="test_set.zip",
        help="Output zip filename (default: test_set.zip)"
    )
    args = parser.parse_args()
    build_test_set(args.input, args.output)


if __name__ == "__main__":
    main()
