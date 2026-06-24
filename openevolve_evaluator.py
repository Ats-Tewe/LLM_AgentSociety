"""
openevolve_evaluator.py

Module-level evaluate() function required by OpenEvolve.
OpenEvolve writes each mutated agents_evolving.yaml to a temp file
and calls evaluate(program_path) to get the fitness score.

Architecture:
  EvolvingSimulationAgent pre-fetches all Yelp data (same logic as
  crewai_simulation_agent.py), then runs the 4-agent evolving crew
  (user_profiler -> item_analyst -> prediction_modeler -> rating_critic)
  loaded from the YAML file OpenEvolve mutated.

Returns: {"combined_score": float}
  combined_score = (preference_estimation + review_generation) / 2
"""
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

# ---------------------------------------------------------------------------
# Circular fallback patch for OpenEvolve's LLMEnsemble.
# Default behaviour: randomly pick one model per call — if it times out,
# that iteration is wasted.
# Patched behaviour: try Model 0 (NVIDIA) first; if it fails after its own
# retries, immediately try Model 1 (Groq key 1); if that also fails, try
# Model 2 (Groq key 2); if all fail raise the last exception.
# _last_success_idx remembers which model last worked so the next call
# starts there, creating the circular rotation the user requested.
# ---------------------------------------------------------------------------
def _patch_llm_ensemble_circular_fallback():
    from openevolve.llm.ensemble import LLMEnsemble
    import asyncio

    async def _circular_generate_with_context(self, system_message, messages, **kwargs):
        n = len(self.models)
        start = getattr(self, "_last_success_idx", 0)
        last_exc = None
        for i in range(n):
            idx = (start + i) % n
            model = self.models[idx]
            model_name = getattr(model, "model", f"model_{idx}")
            try:
                logging.getLogger(__name__).info(
                    f"[CircularFallback] Trying model {idx}/{n-1}: {model_name}"
                )
                result = await model.generate_with_context(system_message, messages, **kwargs)
                self._last_success_idx = idx
                return result
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    f"[CircularFallback] Model {idx} ({model_name}) failed: {exc}. "
                    + ("Trying next." if i < n - 1 else "All models exhausted.")
                )
                last_exc = exc
        raise last_exc

    async def _circular_generate(self, prompt, **kwargs):
        return await _circular_generate_with_context(
            self, "", [{"role": "user", "content": prompt}], **kwargs
        )

    LLMEnsemble.generate_with_context = _circular_generate_with_context
    LLMEnsemble.generate = _circular_generate
    logging.getLogger(__name__).info(
        "[CircularFallback] LLMEnsemble patched: NVIDIA -> Groq1 -> Groq2 -> NVIDIA ..."
    )

_patch_llm_ensemble_circular_fallback()

project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.append(project_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_dir, ".env"))

from websocietysimulator import Simulator
from websocietysimulator.agent import SimulationAgent

# Import data pre-fetch helpers from the existing agent module
from crewai_simulation_agent import (
    _summarize_user,
    _summarize_item,
    _summarize_peer_item_reviews,
    _peer_avg_stars,
    _summarize_history,
    _parse_item_avg_stars,
    _star_prior,
    _calibration_block,
    _snap_star_bucket,
    _safe_get,
)
from src.tools.interaction_tool_wrapper import inject_simulator_tool
from src.crews.evolving_crew import build_evolving_crew, extract_json_from_crew_output

# Hard timeout for one full simulation run (seconds)
SIM_TIMEOUT_SEC = int(os.environ.get("OPENEVOLVE_SIM_TIMEOUT", 900))

# ---------------------------------------------------------------------------
# Lazy simulator singleton — expensive to initialize (loads LMDB dataset).
# Reused across all evaluate() calls in one OpenEvolve run.
# ---------------------------------------------------------------------------
_simulator: Simulator = None


def _get_simulator() -> Simulator:
    global _simulator
    if _simulator is None:
        logging.getLogger().setLevel(logging.WARNING)
        print("[Evaluator] Initializing Simulator (one-time)...")
        _simulator = Simulator(data_dir="dummy_dataset", device="cpu", cache=True)
        _simulator.set_task_and_groundtruth(
            task_dir="dummy_tasks",
            groundtruth_dir="dummy_groundtruth",
        )
        _simulator.set_agent(EvolvingSimulationAgent)
        print("[Evaluator] Simulator ready.")
    return _simulator


# ---------------------------------------------------------------------------
# EvolvingSimulationAgent
# ---------------------------------------------------------------------------
class EvolvingSimulationAgent(SimulationAgent):
    """
    Adapter that pre-fetches Yelp data exactly like CrewAISimulationAgent,
    then delegates to the 4-agent evolving crew instead of serving_flow.py.
    The evolving crew is loaded fresh each workflow() call from
    OPENEVOLVE_AGENTS_YAML, so each OpenEvolve iteration uses its own YAML.
    """

    def workflow(self) -> dict:
        # 1. Resolve task IDs
        if isinstance(self.task, dict):
            user_id = str(self.task.get("user_id", "") or "")
            item_id = str(self.task.get("item_id", "") or "")
        else:
            user_id = str(getattr(self.task, "user_id", "") or "")
            item_id = str(getattr(self.task, "item_id", "") or "")

        # 2. Inject the simulator's interaction tool into the global wrapper
        inject_simulator_tool(getattr(self, "interaction_tool", None))

        # 3. Pre-fetch all Yelp data
        tool = getattr(self, "interaction_tool", None)

        def safe_call(method_name, **kwargs):
            fn = getattr(tool, method_name, None)
            if fn is None:
                return None
            try:
                return fn(**kwargs)
            except Exception:
                return None

        user         = safe_call("get_user",    user_id=user_id)
        item         = safe_call("get_item",    item_id=item_id)
        reviews      = safe_call("get_reviews", user_id=user_id) or []
        peer_reviews = safe_call("get_reviews", item_id=item_id) or []

        # 4. Build context strings (same logic as crewai_simulation_agent.py)
        user_summary = _summarize_user(user)
        item_summary = _summarize_item(item)

        peer_blob = _summarize_peer_item_reviews(peer_reviews, exclude_user_id=user_id)
        peer_avg  = _peer_avg_stars(peer_reviews, exclude_user_id=user_id)
        if peer_avg is not None:
            item_summary += (
                f"\nPEER_AVG_STARS: {peer_avg} "
                f"(mean star rating from other reviewers of this business)"
            )
        if peer_blob:
            item_summary += (
                "\n\n=== OTHER REVIEWERS ABOUT THIS BUSINESS ===\n" + peer_blob
            )

        item_categories = str(_safe_get(item, "categories", default="") or "")
        history_summary, user_avg = _summarize_history(
            reviews, item_categories=item_categories
        )

        # 5. Compute data-driven star prior (blends user history + item avg)
        fallback = max(
            1.0,
            min(
                5.0,
                float(user_avg)
                if user_avg is not None
                else float(
                    _safe_get(user, "average_stars", "avg_stars", default=4.0) or 4.0
                ),
            ),
        )
        item_avg_stars = _parse_item_avg_stars(item_summary)
        prior = _star_prior(user_avg, item_avg_stars, fallback, review_count=len(reviews))
        history_with_prior = history_summary + _calibration_block(prior)

        # 6. Assemble inputs for the crew
        inputs = {
            "user_id":         user_id,
            "item_id":         item_id,
            "user_summary":    user_summary,
            "item_summary":    item_summary,
            "history_summary": history_with_prior,
            "fallback_rating": f"{prior:.2f}",
        }

        # 7. Build and run the evolving crew
        try:
            crew   = build_evolving_crew(inputs)
            result = crew.kickoff(inputs=inputs)
            raw    = getattr(result, "raw", str(result))
            data   = extract_json_from_crew_output(raw)
            stars  = _snap_star_bucket(data.get("stars", prior))
            review = str(data.get("review", "")).strip() or "No review generated."
        except Exception as exc:
            print(f"[EvolvingAgent] Crew failed: {exc}")
            stars  = _snap_star_bucket(prior)
            review = "Crew execution failed."

        return {"stars": stars, "review": review}


# ---------------------------------------------------------------------------
# evaluate() — called by OpenEvolve for each candidate program
# ---------------------------------------------------------------------------
def evaluate(program_path: str) -> dict:
    """
    OpenEvolve calls this with the path to the mutated YAML.
    Sets OPENEVOLVE_AGENTS_YAML so EvolvingSimulationAgent loads it.
    Returns {"combined_score": float}.
    """
    simulator = _get_simulator()
    try:
        os.environ["OPENEVOLVE_AGENTS_YAML"] = program_path
        num_tasks = int(os.environ.get("OPENEVOLVE_NUM_TASKS", 1))
        print(f"\n[Evaluator] program={os.path.basename(program_path)}  tasks={num_tasks}")

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    simulator.run_simulation,
                    number_of_tasks=num_tasks,
                    enable_threading=True,
                    max_workers=2,
                )
                future.result(timeout=SIM_TIMEOUT_SEC)
        except FuturesTimeout:
            print(f"[Evaluator] Timed out after {SIM_TIMEOUT_SEC}s — returning 0.0")
            return {"combined_score": 0.0}

        print("[Evaluator] Calculating metrics...")
        eval_results = simulator.evaluate()

        metrics  = eval_results.get("metrics", {}) if isinstance(eval_results, dict) else {}
        overall  = metrics.get("overall_quality",   0.0)
        pref     = metrics.get("preference_estimation", 0.0)
        rev_gen  = metrics.get("review_generation", 0.0)

        print(
            f"[Evaluator] preference_estimation={pref:.4f}  "
            f"review_generation={rev_gen:.4f}  "
            f"combined_score={overall:.4f}"
        )
        # Return all three scores. OpenEvolve only reads "combined_score";
        # extra keys are ignored by OpenEvolve but available to __main__.
        return {
            "combined_score":        float(overall),
            "preference_estimation": float(pref),
            "review_generation":     float(rev_gen),
        }

    except Exception as exc:
        print(f"[Evaluator] Error: {exc}")
        import traceback
        traceback.print_exc()
        return {"combined_score": 0.0}


# ---------------------------------------------------------------------------
# Smoke test: run as __main__ to validate end-to-end pipeline
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json, datetime

    default_yaml = os.path.join(project_dir, "config", "agents_evolving.yaml")
    yaml_path = os.environ.get("OPENEVOLVE_AGENTS_YAML", default_yaml)
    if not os.path.exists(yaml_path):
        print(f"[SmokeTest] ERROR: {yaml_path} not found")
        sys.exit(1)

    os.environ.setdefault("OPENEVOLVE_NUM_TASKS", "1")
    num_tasks = os.environ["OPENEVOLVE_NUM_TASKS"]
    print(f"[SmokeTest] Running {num_tasks}-task evaluation with: {os.path.basename(yaml_path)}")
    result = evaluate(yaml_path)
    print(f"[SmokeTest] Result: {result}")

    # Save detailed scores to a file the professor can inspect.
    report = {
        "yaml_file":             os.path.basename(yaml_path),
        "num_tasks":             int(num_tasks),
        "preference_estimation": result.get("preference_estimation", 0.0),
        "review_generation":     result.get("review_generation",     0.0),
        "combined_score":        result.get("combined_score",        0.0),
        "evaluated_at":          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_dir  = os.path.join(project_dir, "config", "openevolve_output", "best")
    save_path = os.path.join(save_dir, "evaluation_scores.json")
    os.makedirs(save_dir, exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[SmokeTest] Detailed scores saved → {save_path}")
