from __future__ import annotations

"""Verify and set up the ChromaDB RAG index for this project.

The chroma_index (~4.7 GB) is pre-built and must already exist at:
  workspace/chroma_index/chroma.sqlite3

This script:
  1. Locates the chroma.sqlite3 file.
  2. Verifies the required collection is present.
  3. Updates CREWAI_STORAGE_DIR in .env so the crew files can locate it.
  4. Optionally runs inspect_rag.py to show full collection stats.

Usage:
  uv run python scripts/setup_rag.py [--storage-dir PATH]
  uv run python scripts/setup_rag.py --check-only
"""

import argparse
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT_DIR.parent

TARGET_COLLECTION = "benchmark_true_fresh_index_Filtered_Review_1"
DEFAULT_INDEX_PATH = WORKSPACE_ROOT / "chroma_index"
ENV_FILE = ROOT_DIR / ".env"


def _find_db(storage_dir: Path) -> Path | None:
    candidate = storage_dir / "chroma.sqlite3"
    return candidate if candidate.exists() and candidate.stat().st_size > 1_000_000 else None


def _collection_exists(db_file: Path, collection: str) -> bool:
    try:
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        cur.execute("SELECT id FROM collections WHERE name = ?", (collection,))
        found = cur.fetchone() is not None
        conn.close()
        return found
    except Exception:
        return False


def _update_env_storage_dir(storage_dir: Path) -> None:
    """Write/replace CREWAI_STORAGE_DIR in .env."""
    line = f"CREWAI_STORAGE_DIR={storage_dir.as_posix()}"
    if ENV_FILE.exists():
        text = ENV_FILE.read_text(encoding="utf-8")
        if re.search(r"^CREWAI_STORAGE_DIR\s*=", text, re.MULTILINE):
            text = re.sub(
                r"^CREWAI_STORAGE_DIR\s*=.*$",
                line,
                text,
                flags=re.MULTILINE,
            )
        else:
            text = text.rstrip("\n") + "\n" + line + "\n"
        ENV_FILE.write_text(text, encoding="utf-8")
    else:
        ENV_FILE.write_text(line + "\n", encoding="utf-8")
    print(f"Updated .env: {line}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify and configure the ChromaDB RAG index for item_analyst."
    )
    parser.add_argument(
        "--storage-dir",
        default=str(DEFAULT_INDEX_PATH),
        help=f"Path to folder containing chroma.sqlite3 (default: {DEFAULT_INDEX_PATH}).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only verify the index; do not modify .env.",
    )
    parser.add_argument(
        "--skip-env-update",
        action="store_true",
        help="Skip updating CREWAI_STORAGE_DIR in .env.",
    )
    args = parser.parse_args()

    storage_dir = Path(args.storage_dir).expanduser().resolve()
    print(f"Looking for chroma.sqlite3 in: {storage_dir}")

    db_file = _find_db(storage_dir)
    if db_file is None:
        print(
            "\nERROR: chroma.sqlite3 not found or too small.\n"
            f"  Expected: {storage_dir / 'chroma.sqlite3'}\n\n"
            "The RAG index (~4.7 GB) must be pre-built. It is NOT included in this repo.\n"
            "  - If you have it from a previous session, copy it here.\n"
            "  - Otherwise, run with RAG_ENABLED=0 (the default) and no RAG is used.\n"
        )
        return 1

    print(f"Found: {db_file} ({db_file.stat().st_size:,} bytes)")

    if not _collection_exists(db_file, TARGET_COLLECTION):
        print(
            f"\nWARNING: collection {TARGET_COLLECTION!r} not present in {db_file.name}.\n"
            "RAG will be disabled at runtime even if RAG_ENABLED=1."
        )
        return 1

    print(f"Collection OK : {TARGET_COLLECTION}")

    if not args.check_only and not args.skip_env_update:
        _update_env_storage_dir(storage_dir)
        print("Set RAG_ENABLED=1 in .env to activate RAG for item_analyst.")

    # Run inspect_rag for full stats
    check_script = ROOT_DIR / "scripts" / "inspect_rag.py"
    if check_script.exists():
        print("\n--- Full index report ---")
        subprocess.run(
            [sys.executable, str(check_script), "--storage-dir", str(storage_dir)],
            check=False,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
