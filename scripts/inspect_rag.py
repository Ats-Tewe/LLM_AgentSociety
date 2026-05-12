from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT_DIR.parent


def _find_db(storage_dir_override: str | None) -> Path | None:
    """Return the first chroma.sqlite3 that exists and has meaningful content."""
    candidates = []
    if storage_dir_override:
        candidates.append(Path(storage_dir_override).expanduser().resolve() / "chroma.sqlite3")
    env_dir = os.environ.get("CREWAI_STORAGE_DIR", "").strip()
    if env_dir:
        candidates.append(Path(env_dir).expanduser().resolve() / "chroma.sqlite3")
    # Canonical workspace location
    candidates.append(WORKSPACE_ROOT / "chroma_index" / "chroma.sqlite3")

    for p in candidates:
        if p.exists() and p.stat().st_size > 100_000:
            return p
    return None


def _report(db_file: Path, target_collection: str) -> int:
    print(f"Database file : {db_file}")
    print(f"Size          : {db_file.stat().st_size:,} bytes")

    try:
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()

        cur.execute("SELECT name FROM collections ORDER BY name")
        collections = [row[0] for row in cur.fetchall()]

        if not collections:
            print("Collections   : (none found)")
            conn.close()
            return 0

        print(f"\nCollections ({len(collections)} total):")
        for col in collections:
            cur.execute(
                "SELECT COUNT(*) FROM embeddings WHERE collection_id = "
                "(SELECT id FROM collections WHERE name = ?)",
                (col,),
            )
            count = cur.fetchone()[0]
            marker = " <-- TARGET" if col == target_collection else ""
            print(f"  {col}: {count:,} documents{marker}")

        conn.close()

        if target_collection and target_collection not in collections:
            print(
                f"\nWARNING: target collection {target_collection!r} not found.\n"
                "RAG will be unavailable until the correct chroma_index is installed."
            )
            return 1

    except Exception as exc:
        print(f"ERROR: cannot read {db_file}: {exc}")
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the status of the ChromaDB RAG index used by item_analyst."
    )
    parser.add_argument(
        "--storage-dir",
        default=None,
        help="Override path to folder containing chroma.sqlite3.",
    )
    parser.add_argument(
        "--collection",
        default="benchmark_true_fresh_index_Filtered_Review_1",
        help="Target RAG collection name to verify.",
    )
    args = parser.parse_args()

    db_file = _find_db(args.storage_dir)
    if db_file is None:
        print("chroma.sqlite3 not found.")
        print(f"Expected at: {WORKSPACE_ROOT / 'chroma_index' / 'chroma.sqlite3'}")
        print("Set RAG_ENABLED=0 in .env (default) to run without RAG.")
        return 1

    return _report(db_file, args.collection)


if __name__ == "__main__":
    raise SystemExit(main())
