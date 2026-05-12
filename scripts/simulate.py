from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from litellm import ModelResponse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crewai_simulation_agent import CrewAISimulationAgent
from websocietysimulator import Simulator


def _start_mock_if_needed(use_mock: bool):
    if not use_mock:
        return None

    def fake_completion(*args, **kwargs):
        return ModelResponse(
            id="mock-id",
            model="gpt-4",
            choices=[
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": (
                            '{"stars": 4.0, "review": '
                            '"[Mocked] Yelp smoke-test review output."}'
                        ),
                    },
                }
            ],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    patcher = patch("litellm.completion", side_effect=fake_completion)
    patcher.start()
    return patcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run AgentSociety + CrewAI simulation. "
            "Supports sequential/collaborative/hierarchical crew modes."
        )
    )
    parser.add_argument(
        "--data-dir",
        default="dummy_dataset",
        help="Dataset directory containing item.json, review.json, user.json.",
    )
    parser.add_argument(
        "--task-dir",
        default="dummy_tasks",
        help="Task directory (run scripts/sample_dummy_data.py to generate).",
    )
    parser.add_argument(
        "--groundtruth-dir",
        default="dummy_groundtruth",
        help="Groundtruth directory matching --task-dir.",
    )
    parser.add_argument(
        "--mode",
        choices=["sequential", "collaborative", "hierarchical"],
        default=os.getenv("CREWAI_PROCESS_MODE", "sequential").strip().lower(),
        help="Crew process mode (overrides CREWAI_PROCESS_MODE env var).",
    )
    parser.add_argument(
        "--tasks",
        type=int,
        default=2,
        help="How many tasks to run.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Max workers when --threading is enabled.",
    )
    parser.add_argument(
        "--threading",
        action="store_true",
        help="Enable threaded simulation.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device passed to Simulator (e.g. cpu, auto).",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        default=True,
        help="Use lazy-loading cache in Simulator (recommended for large data).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_false",
        dest="cache",
        help="Disable cache and load full dataset into memory.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mocked LLM responses (zero token cost, structural test only).",
    )
    return parser.parse_args()


def _validate_inputs(args: argparse.Namespace) -> None:
    for path in (args.data_dir, args.task_dir, args.groundtruth_dir):
        if not Path(path).exists():
            raise FileNotFoundError(
                f"Path not found: {path}\n"
                "  Tip: run `uv run python scripts/sample_dummy_data.py` "
                "to generate dummy_tasks/ and dummy_groundtruth/"
            )


def main() -> int:
    args = parse_args()
    load_dotenv()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    _validate_inputs(args)
    os.environ["CREWAI_PROCESS_MODE"] = args.mode
    logging.basicConfig(level=logging.INFO)

    print(f"Mode            : {args.mode}")
    print(f"Data dir        : {args.data_dir}")
    print(f"Task dir        : {args.task_dir}")
    print(f"Groundtruth dir : {args.groundtruth_dir}")
    print(f"Tasks to run    : {args.tasks}")
    print(f"Threading       : {args.threading}, workers={args.workers}")
    print(f"Cache           : {args.cache}, device={args.device}")
    if args.mock:
        print("LLM mode        : mock (no API calls)")

    patcher = _start_mock_if_needed(args.mock)
    try:
        simulator = Simulator(data_dir=args.data_dir, device=args.device, cache=args.cache)
        simulator.set_task_and_groundtruth(
            task_dir=args.task_dir,
            groundtruth_dir=args.groundtruth_dir,
        )
        simulator.set_agent(CrewAISimulationAgent)

        outputs = simulator.run_simulation(
            number_of_tasks=args.tasks,
            enable_threading=args.threading,
            max_workers=args.workers,
        )

        print("\n=== Outputs ===")
        print(json.dumps(outputs, indent=2, ensure_ascii=False))
        print("\n=== Evaluation ===")
        print(json.dumps(simulator.evaluate(), indent=2, ensure_ascii=False))
        return 0
    finally:
        if patcher:
            patcher.stop()


if __name__ == "__main__":
    raise SystemExit(main())
