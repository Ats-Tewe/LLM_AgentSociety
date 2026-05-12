from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from litellm import ModelResponse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crewai_simulation_agent import (
    _calibration_block,
    _parse_item_avg_stars,
    _star_prior,
    _summarize_history,
    _summarize_item,
    _summarize_peer_item_reviews,
    _summarize_user,
)
from src.crews.collaborative_crew import CollaborativeCrew


# ---------------------------------------------------------------------------
# Lightweight NDJSON data loader (mirrors the simulator's InteractionTool API)
# ---------------------------------------------------------------------------

class _DataLoader:
    """Load user/item/review NDJSON files and expose simple lookup methods."""

    def __init__(self, data_dir: Path):
        self._users   = self._load_jsonl(data_dir / "user.json",   "user_id")
        self._items   = self._load_jsonl(data_dir / "item.json",   "item_id")
        self._reviews = self._load_all(data_dir / "review.json")

    @staticmethod
    def _load_jsonl(path: Path, key: str) -> dict[str, dict]:
        records: dict[str, dict] = {}
        if not path.exists():
            return records
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    records[obj[key]] = obj
                except (json.JSONDecodeError, KeyError):
                    pass
        return records

    @staticmethod
    def _load_all(path: Path) -> list[dict]:
        reviews: list[dict] = []
        if not path.exists():
            return reviews
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    reviews.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return reviews

    def get_user(self, user_id: str) -> dict | None:
        return self._users.get(user_id)

    def get_item(self, item_id: str) -> dict | None:
        return self._items.get(item_id)

    def get_reviews_by_user(self, user_id: str) -> list[dict]:
        return [r for r in self._reviews if r.get("user_id") == user_id]

    def get_reviews_by_item(self, item_id: str) -> list[dict]:
        return [r for r in self._reviews if r.get("item_id") == item_id]


# ---------------------------------------------------------------------------
# Build the full 6-field inputs dict that the crew expects
# ---------------------------------------------------------------------------

def _build_inputs(user_id: str, item_id: str, loader: _DataLoader) -> dict:
    user         = loader.get_user(user_id)
    item         = loader.get_item(item_id)
    user_reviews = loader.get_reviews_by_user(user_id)
    item_reviews = loader.get_reviews_by_item(item_id)

    user_summary = _summarize_user(user)
    item_summary = _summarize_item(item)

    peer_blob = _summarize_peer_item_reviews(item_reviews, exclude_user_id=user_id)
    if peer_blob:
        item_summary = (
            item_summary
            + "\n\n=== OTHER REVIEWERS ABOUT THIS BUSINESS (snippets; topical context only) ===\n"
            + peer_blob
        )

    history_summary, user_avg = _summarize_history(user_reviews)

    fallback_rating = float(
        user_avg
        if user_avg is not None
        else (user.get("average_stars") or 4.0) if user else 4.0
    )
    fallback_rating = max(1.0, min(5.0, fallback_rating))

    item_avg_stars   = _parse_item_avg_stars(item_summary)
    prior            = _star_prior(user_avg, item_avg_stars, fallback_rating)
    history_with_prior = history_summary + _calibration_block(prior)

    return {
        "user_id":        user_id,
        "item_id":        item_id,
        "user_summary":   user_summary,
        "item_summary":   item_summary,
        "history_summary": history_with_prior,
        "fallback_rating": prior,
    }


# ---------------------------------------------------------------------------
# Mock helper
# ---------------------------------------------------------------------------

def _start_mock_if_needed(use_mock: bool):
    if not use_mock:
        return None

    def fake_completion(*args, **kwargs):
        return ModelResponse(
            id="mock-id",
            model="gpt-4",
            choices=[{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": '{"stars": 4.0, "review": "[Mocked] Collaborative crew review output."}',
                },
            }],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    patcher = patch("litellm.completion", side_effect=fake_completion)
    patcher.start()
    return patcher


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run CollaborativeCrew with pre-fetched data for one user/item pair. "
            "Generate real user/item IDs first with: "
            "uv run python scripts/sample_dummy_data.py"
        )
    )
    parser.add_argument("--user-id", default="u_demo", help="Yelp user_id.")
    parser.add_argument("--item-id", default="i_demo", help="Yelp item_id (business_id).")
    parser.add_argument(
        "--data-dir",
        default="dummy_dataset",
        help="Directory containing user.json, item.json, review.json.",
    )
    parser.add_argument("--mock", action="store_true", help="Use mocked LLM (no API calls).")
    args = parser.parse_args()

    load_dotenv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    os.environ["CREWAI_PROCESS_MODE"] = "collaborative"

    data_dir = Path(args.data_dir).expanduser().resolve()
    print(f"Loading data from {data_dir} ...")
    loader = _DataLoader(data_dir)

    print(f"Building inputs for user={args.user_id!r}, item={args.item_id!r} ...")
    inputs = _build_inputs(args.user_id, args.item_id, loader)

    patcher = _start_mock_if_needed(args.mock)
    try:
        result = CollaborativeCrew().crew().kickoff(inputs=inputs)
        print(result.raw)
        return 0
    finally:
        if patcher:
            patcher.stop()


if __name__ == "__main__":
    raise SystemExit(main())
