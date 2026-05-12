"""
run_pipeline.py — AgentSociety CrewAI Pipeline Runner

Usage:
  uv run python run_pipeline.py                        # Real LLM, sequential
  uv run python run_pipeline.py --mock                 # Mock mode (no token cost)
  uv run python run_pipeline.py --threads 2            # 2-worker threading
  uv run python run_pipeline.py --timeout 120          # 120s per-task timeout
  uv run python run_pipeline.py --tasks 1              # Smoke test (1 task only)
  uv run python run_pipeline.py --mock --threads 2 --tasks 5
"""
import sys
import os

if sys.prefix == sys.base_prefix:
    print("❌ Please run this script with uv: uv run python run_pipeline.py", file=sys.stderr)
    sys.exit(1)

import time
import json
import logging
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

# ======================================================================
# CLI Arguments
# ======================================================================
parser = argparse.ArgumentParser(description="AgentSociety CrewAI Pipeline Runner")
parser.add_argument("--mock",    action="store_true",    help="Use mock LLM (no token cost)")
parser.add_argument("--threads", type=int, default=1,    metavar="N",   help="Number of worker threads (default: 1 = sequential)")
parser.add_argument("--timeout", type=int, default=300,  metavar="SEC", help="Per-task timeout in seconds (default: 300, 0 = disabled)")
parser.add_argument("--tasks",   type=int, default=None, metavar="N",   help="Run only the first N tasks (default: all)")
args = parser.parse_args()

TIMEOUT_SEC = args.timeout if args.timeout > 0 else None

# ======================================================================
# Mock vs. Real LLM
# ======================================================================
if args.mock:
    from unittest.mock import patch
    import litellm

    def fake_completion(*a, **kw):
        resp = litellm.ModelResponse()
        resp.choices = [litellm.Choices(
            message=litellm.Message(
                content='{"stars": 4.0, "review": "[Mocked] Good place, friendly staff!"}',
                role="assistant",
            ),
            finish_reason="stop",
        )]
        resp.model = "gpt-4"
        return resp

    patch("litellm.completion", side_effect=fake_completion).start()
    os.environ["OPENAI_API_KEY"] = "sk-mock-key"
    print("⚙️  Mode: Mock LLM (no token cost)")
else:
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    api_base = os.environ.get("OPENAI_API_BASE", "")
    model    = os.environ.get("OPENAI_MODEL_NAME", "(not set)")
    print("⚙️  Mode: Real LLM")
    key_status = "✅ set" if api_key else "❌ not set"
    nvidia_warn = "  ⚠️  Warning: key does not look like an NVIDIA nvapi key" if api_key and not api_key.startswith("nvapi") else ""
    print(f"🔑 API Key : {key_status}{nvidia_warn}")
    print(f"🌐 Base URL: {api_base or '❌ not set'}")
    print(f"🤖 Model   : {model}")

# ======================================================================
# Load Framework
# ======================================================================
from websocietysimulator import Simulator
from crewai_simulation_agent import CrewAISimulationAgent

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

# ======================================================================
# Main
# ======================================================================
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH   = f"pipeline_report_{RUN_TIMESTAMP}.json"

print("\n" + "=" * 65)
print(f"🚀 AgentSociety Pipeline Run — {RUN_TIMESTAMP}")
print(f"   threads={args.threads}  timeout={TIMEOUT_SEC or '∞'}s  tasks={args.tasks or 'all'}")
print("=" * 65)

wall_start = time.time()

# ======================================================================
# Per-task runner (shared by sequential and threading modes)
# ======================================================================
def run_single_task(idx, task, interaction_tool):
    from crewai_simulation_agent import CrewAISimulationAgent as AgentCls
    agent = AgentCls()
    agent.set_interaction_tool(interaction_tool)
    agent.insert_task(task)
    return agent.workflow()

try:
    # 1. Initialize Simulator
    print("\n>>> [1/3] Loading toy dataset (dummy_dataset) + cache ...")
    init_start = time.time()
    simulator = Simulator(data_dir="dummy_dataset", device="cpu", cache=True)
    simulator.set_task_and_groundtruth(task_dir="dummy_tasks", groundtruth_dir="dummy_groundtruth")
    simulator.set_agent(CrewAISimulationAgent)
    init_elapsed = time.time() - init_start

    tasks_to_run = simulator.tasks[:args.tasks] if args.tasks else simulator.tasks
    print(f"    ✅ Initialized ({init_elapsed:.1f}s) — running {len(tasks_to_run)}/{len(simulator.tasks)} tasks")

    # 2. Run Inference
    mode_label = f"threading (workers={args.threads})" if args.threads > 1 else "sequential"
    print(f"\n>>> [2/3] Starting inference ({mode_label}) ...")
    infer_start = time.time()

    per_task_times = []
    simulator.simulation_outputs = []

    if args.threads > 1:
        # --- Threading mode ---
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures_map = {
                executor.submit(run_single_task, idx, task, simulator.interaction_tool): (idx, task)
                for idx, task in enumerate(tasks_to_run)
            }
            for future in as_completed(futures_map):
                idx, task = futures_map[future]
                task_label = f"Task {idx+1:02d}/{len(tasks_to_run)}"
                t0 = time.time()
                try:
                    output = future.result(timeout=TIMEOUT_SEC)
                    result = {"task": task.to_dict(), "output": output}
                    stars  = output.get("stars", "N/A")
                except FuturesTimeout:
                    output = None
                    result = {"task": task.to_dict(), "output": {"stars": 4.0, "review": "Timeout — using fallback rating."}, "error": f"Timeout after {TIMEOUT_SEC}s"}
                    stars  = "TIMEOUT"
                except Exception as e:
                    output = None
                    result = {"task": task.to_dict(), "output": {"stars": 4.0, "review": "Error — using fallback rating."}, "error": str(e)}
                    stars  = "ERR"
                elapsed = time.time() - t0
                per_task_times.append(elapsed)
                simulator.simulation_outputs.append(result)
                print(f"  ✓ {task_label} — stars={stars}  ({elapsed:.1f}s)")
    else:
        # --- Sequential mode (with per-task timeout) ---
        for idx, task in enumerate(tasks_to_run):
            task_label = f"Task {idx+1:02d}/{len(tasks_to_run)}"
            print(f"  ⏳ {task_label} — user={task.user_id[:8]}... item={task.item_id[:8]}...", end="", flush=True)
            t0 = time.time()
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    output = executor.submit(run_single_task, idx, task, simulator.interaction_tool).result(timeout=TIMEOUT_SEC)
                result = {"task": task.to_dict(), "output": output}
                stars  = output.get("stars", "N/A")
            except FuturesTimeout:
                output = None
                result = {"task": task.to_dict(), "output": {"stars": 4.0, "review": "Timeout — using fallback rating."}, "error": f"Timeout after {TIMEOUT_SEC}s"}
                stars  = "TIMEOUT"
            except Exception as e:
                output = None
                result = {"task": task.to_dict(), "output": {"stars": 4.0, "review": "Error — using fallback rating."}, "error": str(e)}
                stars  = "ERR"
            elapsed = time.time() - t0
            per_task_times.append(elapsed)
            simulator.simulation_outputs.append(result)
            print(f" → stars={stars}  ({elapsed:.1f}s)")

    infer_elapsed = time.time() - infer_start
    total_elapsed = time.time() - wall_start

    # 3. Official Evaluation
    print("\n>>> [3/3] Running official evaluation ...")
    eval_results = simulator.evaluate()

    # ======================================================================
    # Report
    # ======================================================================
    avg_task_time = sum(per_task_times) / len(per_task_times) if per_task_times else 0
    error_count   = sum(1 for r in simulator.simulation_outputs if "error" in r)

    report = {
        "run_timestamp": RUN_TIMESTAMP,
        "mode":  "mock" if args.mock else "real_llm",
        "model": os.environ.get("OPENAI_MODEL_NAME", "mock"),
        "config": {
            "threads":          args.threads,
            "timeout_seconds":  TIMEOUT_SEC,
            "tasks_run":        len(tasks_to_run),
            "tasks_total":      len(simulator.tasks),
        },
        "timing": {
            "init_seconds":      round(init_elapsed, 2),
            "inference_seconds": round(infer_elapsed, 2),
            "total_seconds":     round(total_elapsed, 2),
            "avg_task_seconds":  round(avg_task_time, 2),
            "min_task_seconds":  round(min(per_task_times), 2) if per_task_times else 0,
            "max_task_seconds":  round(max(per_task_times), 2) if per_task_times else 0,
        },
        "errors":           error_count,
        "evaluation":       eval_results,
        "per_task_outputs": simulator.simulation_outputs,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # ======================================================================
    # Summary
    # ======================================================================
    print("\n" + "=" * 65)
    print("📊  PIPELINE RESULT SUMMARY")
    print("=" * 65)
    for k, v in eval_results.get("metrics", {}).items():
        print(f"  {k:30s}: {v}")
    print("-" * 65)
    print(f"  ⏱  Init time      : {init_elapsed:.1f}s")
    print(f"  ⏱  Inference time : {infer_elapsed:.1f}s  (avg {avg_task_time:.1f}s/task)")
    print(f"  ⏱  Wall clock     : {total_elapsed:.1f}s  ({total_elapsed/60:.1f} min)")
    print(f"  ❌  Errors/timeouts: {error_count}")
    print(f"  📁  Report        : {REPORT_PATH}")
    print("=" * 65)
    print("✅  Pipeline run complete!")

except Exception as e:
    print(f"\n❌ Run failed: {e}")
    import traceback
    traceback.print_exc()
