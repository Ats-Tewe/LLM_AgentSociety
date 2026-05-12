"""
check_compatibility.py — Pre-test self-check for students.

Run this before the test day to confirm your CrewAISimulationAgent:
  1. Can be imported without errors
  2. Implements all 4 required methods
  3. Can be instantiated with llm=None
  4. Returns correct output format ({"stars": float, "review": str}) — mock LLM
  5. Connects to your real LLM API and completes 1 task end-to-end — real LLM

Usage:
  uv run python scripts/check_compatibility.py
"""
import sys
import os

if sys.prefix == sys.base_prefix:
    print("❌ Please run with uv: uv run python scripts/check_compatibility.py", file=sys.stderr)
    sys.exit(1)

import json
import re
import glob
import subprocess

# ======================================================================
# Helpers
# ======================================================================
PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "
SKIP = "⏭️ "

errors   = []   # (step_label, error_msg, fix_hint)
warnings = []

def _fail(step, msg, hint=""):
    errors.append((step, msg, hint))
    print(f"  {FAIL} {msg}")
    if hint:
        for line in hint.strip().splitlines():
            print(f"       💡 {line}")

def _warn(msg, hint=""):
    warnings.append((msg, hint))
    print(f"  {WARN} {msg}")
    if hint:
        for line in hint.strip().splitlines():
            print(f"       💡 {line}")

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("=" * 62)
print("  AgentSociety — Pre-test Compatibility Check")
print("=" * 62)
print()

# ======================================================================
# [1/5] Import
# ======================================================================
STEP = "1/5"
print(f"[{STEP}] Importing CrewAISimulationAgent ...")
CrewAISimulationAgent = None
try:
    # Ensure project root is on sys.path so relative imports work
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)
    from crewai_simulation_agent import CrewAISimulationAgent
    print(f"  {PASS} Import successful")
except SyntaxError as e:
    _fail(STEP, f"SyntaxError in crewai_simulation_agent.py: {e}",
          "Open crewai_simulation_agent.py and fix the syntax error on the indicated line.\n"
          "Run `python -m py_compile crewai_simulation_agent.py` to pinpoint the issue.")
    print()
    print(f"{FAIL} Import failed — cannot continue. Fix the error above and re-run.")
    sys.exit(1)
except ImportError as e:
    _fail(STEP, f"ImportError: {e}",
          "A required package is missing. Run `uv sync` to restore all dependencies.\n"
          "If you added a new package, make sure it is listed in pyproject.toml.")
    print()
    print(f"{FAIL} Import failed — cannot continue. Fix the error above and re-run.")
    sys.exit(1)
except Exception as e:
    _fail(STEP, f"{type(e).__name__}: {e}",
          "Check crewai_simulation_agent.py for errors that occur at import time\n"
          "(e.g. code running at module level that raises an exception).")
    print()
    print(f"{FAIL} Import failed — cannot continue. Fix the error above and re-run.")
    sys.exit(1)

# ======================================================================
# [2/5] Required methods
# ======================================================================
STEP = "2/5"
print()
print(f"[{STEP}] Checking required methods ...")

REQUIRED_METHODS = {
    "__init__":              "Constructor — must accept llm=None without errors",
    "workflow":              "Main inference logic — must return {\"stars\": float, \"review\": str}",
    "insert_task":           "Called by Simulator to pass the current task to your agent",
    "set_interaction_tool":  "Called by Simulator to inject the InteractionTool (data query API)",
}

for method, desc in REQUIRED_METHODS.items():
    if hasattr(CrewAISimulationAgent, method) and callable(getattr(CrewAISimulationAgent, method)):
        print(f"  {PASS} {method}")
    else:
        _fail(STEP, f"{method} — not found or not callable",
              f"Add `def {method}(self, ...)` to your CrewAISimulationAgent class.\n"
              f"Purpose: {desc}")

# ======================================================================
# [3/5] Instantiation with llm=None
# ======================================================================
STEP = "3/5"
print()
print(f"[{STEP}] Instantiating agent with llm=None ...")
agent = None
try:
    agent = CrewAISimulationAgent(llm=None)
    print(f"  {PASS} CrewAISimulationAgent(llm=None) succeeded")
except TypeError as e:
    _fail(STEP, f"TypeError: {e}",
          "Your __init__ does not accept llm=None.\n"
          "Change the signature to:  def __init__(self, llm=None, *args, **kwargs)\n"
          "The Simulator calls your agent without passing any llm argument.")
except Exception as e:
    _fail(STEP, f"{type(e).__name__}: {e}",
          "An error occurred inside __init__. Check for any setup code\n"
          "(e.g. loading files, connecting to services) that might fail at init time.")

# ======================================================================
# [4/5] Mock end-to-end pipeline
# ======================================================================
STEP = "4/5"
print()
print(f"[{STEP}] Mock pipeline — run_pipeline.py --mock --tasks 1 ...")

pipeline_script = os.path.join(SCRIPT_DIR, "run_pipeline.py")

if not os.path.exists(pipeline_script):
    _warn("run_pipeline.py not found — skipped",
          "Make sure you are running this script from the repo root\n"
          "or that run_pipeline.py exists in the project root.")
else:
    try:
        proc = subprocess.run(
            [sys.executable, pipeline_script, "--mock", "--tasks", "1"],
            capture_output=True, text=True, timeout=120, cwd=SCRIPT_DIR,
        )
        combined = proc.stdout + proc.stderr

        if proc.returncode == 0 and "Pipeline run complete" in combined:
            stars_match = re.search(r"stars=(\S+)", combined)
            stars_val = stars_match.group(1) if stars_match else "N/A"
            print(f"  {PASS} Pipeline completed (stars={stars_val})")

            # Verify output format from the generated report
            reports = sorted(glob.glob(os.path.join(SCRIPT_DIR, "pipeline_report_*.json")))
            if reports:
                with open(reports[-1], encoding="utf-8") as rf:
                    report = json.load(rf)
                out = (report.get("per_task_outputs") or [{}])[0].get("output", {})
                ok_type   = isinstance(out, dict)
                ok_stars  = isinstance(out.get("stars"),  (int, float)) if ok_type else False
                ok_review = isinstance(out.get("review"), str)          if ok_type else False

                if ok_type and ok_stars and ok_review:
                    print(f"  {PASS} Output format: stars={out['stars']!r}  review={str(out['review'])[:40]!r}...")
                else:
                    _fail(STEP, f"Output format invalid: {out}",
                          "Your workflow() must return a dict with exactly these keys:\n"
                          "  {\"stars\": <float>, \"review\": <str>}\n"
                          "Example:  return {\"stars\": 4.0, \"review\": \"Great place!\"}")
        else:
            # Extract the most informative part of the error output
            snippet = combined[-800:] if len(combined) > 800 else combined
            # Try to find a specific error line
            err_lines = [l for l in combined.splitlines()
                         if any(kw in l for kw in ("Error", "error", "Exception", "Traceback", "❌"))]
            err_summary = "\n".join(err_lines[-5:]) if err_lines else snippet[-300:]

            _fail(STEP, "Mock pipeline did not complete successfully",
                  f"Last relevant output:\n{err_summary}\n\n"
                  "Common causes:\n"
                  "  • workflow() raised an unhandled exception\n"
                  "  • Output format is wrong (must return dict with 'stars' and 'review')\n"
                  "  • Import of a module inside workflow() failed\n"
                  "Run manually to see full output:\n"
                  "  uv run python run_pipeline.py --mock --tasks 1")

    except subprocess.TimeoutExpired:
        _fail(STEP, "Mock pipeline timed out after 120s",
              "Something is hanging inside workflow() even with a mock LLM.\n"
              "Check for infinite loops, blocking I/O, or sleep() calls.")

# ======================================================================
# [5/5] Real LLM end-to-end pipeline
# ======================================================================
STEP = "5/5"
print()
print(f"[{STEP}] Real LLM pipeline — run_pipeline.py --tasks 1 ...")

# --- Check .env and required keys first ---
env_path = os.path.join(SCRIPT_DIR, ".env")
env_ok = True

if not os.path.exists(env_path):
    _fail(STEP, ".env file not found",
          "Create a .env file in the project root with:\n"
          "  OPENAI_API_KEY=your_api_key\n"
          "  OPENAI_API_BASE=https://integrate.api.nvidia.com/v1\n"
          "  OPENAI_MODEL_NAME=your_model_name\n"
          "  OPENAI_EMBEDDING_MODEL_NAME=nvidia/nv-embedqa-e5-v5  # if using NVIDIA")
    env_ok = False
else:
    # Read .env manually (without dotenv) to check keys
    env_vars = {}
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip().strip('"').strip("'")

    api_key  = env_vars.get("OPENAI_API_KEY",  "")
    api_base = env_vars.get("OPENAI_API_BASE", "")
    model    = env_vars.get("OPENAI_MODEL_NAME", "")

    if not api_key:
        _fail(STEP, "OPENAI_API_KEY is missing or empty in .env",
              "Add your API key to .env:\n"
              "  OPENAI_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx  # NVIDIA\n"
              "  OPENAI_API_KEY=your-key                    # other providers")
        env_ok = False
    elif api_base and "nvidia" in api_base.lower() and not api_key.startswith("nvapi-"):
        _warn("OPENAI_API_KEY does not look like an NVIDIA key (expected nvapi-...)",
              "If you are using NVIDIA NIM, the key should start with 'nvapi-'.\n"
              "Get your key from: https://build.nvidia.com  → API Keys")

    if not api_base:
        _fail(STEP, "OPENAI_API_BASE is missing or empty in .env",
              "Add the API base URL for your provider, e.g.:\n"
              "  OPENAI_API_BASE=https://integrate.api.nvidia.com/v1  # NVIDIA NIM\n"
              "  OPENAI_API_BASE=https://api.minimax.chat/v1          # Minimax")
        env_ok = False

    if not model:
        _warn("OPENAI_MODEL_NAME is not set in .env",
              "Set the model name matching your provider and key, e.g.:\n"
              "  OPENAI_MODEL_NAME=nvidia/llama-3.3-nemotron-super-49b-v1  # NVIDIA\n"
              "  OPENAI_MODEL_NAME=MiniMax-Text-01                          # Minimax")
    else:
        print(f"  ℹ️  Model   : {model}")
        print(f"  ℹ️  API base: {api_base or '(default OpenAI)'}")

if env_ok:
    try:
        proc = subprocess.run(
            [sys.executable, pipeline_script, "--tasks", "1", "--timeout", "300"],
            capture_output=True, text=True, timeout=420, cwd=SCRIPT_DIR,
        )
        combined = proc.stdout + proc.stderr

        if proc.returncode == 0 and "Pipeline run complete" in combined:
            stars_match = re.search(r"stars=(\S+)", combined)
            stars_val = stars_match.group(1) if stars_match else "N/A"
            print(f"  {PASS} Real LLM pipeline completed (stars={stars_val})")
            print(f"  {PASS} API connection and model are working correctly")
        else:
            err_lines = [l for l in combined.splitlines()
                         if any(kw in l for kw in ("Error", "error", "Exception", "Traceback",
                                                    "❌", "AuthenticationError", "NotFound",
                                                    "Timeout", "ConnectionError", "stars=ERR",
                                                    "stars=TIMEOUT"))]
            err_summary = "\n".join(err_lines[-8:]) if err_lines else combined[-400:]

            # Categorise the error for a targeted hint
            hint_lines = [
                f"Last relevant output:\n{err_summary}",
                "",
                "Possible causes and fixes:",
            ]
            if any(kw in combined for kw in ("AuthenticationError", "401", "Unauthorized", "Invalid API")):
                hint_lines += [
                  "  • Invalid API key → double-check OPENAI_API_KEY in .env",
                  "    NVIDIA keys start with 'nvapi-'; regenerate at https://build.nvidia.com"]
            if any(kw in combined for kw in ("NotFound", "404", "model_not_found", "does not exist")):
                hint_lines += [
                  "  • Model not found → check OPENAI_MODEL_NAME in .env",
                  "    List available NVIDIA models: https://build.nvidia.com/explore/discover"]
            if any(kw in combined for kw in ("ConnectionError", "ConnectTimeout", "Name or service")):
                hint_lines += [
                  "  • Cannot reach the API → check network / VPN / firewall",
                  "    Verify OPENAI_API_BASE is correct in .env"]
            if "stars=TIMEOUT" in combined or "stars=ERR" in combined:
                hint_lines += [
                  "  • Task timed out or errored → try a faster/cheaper model",
                  "    Add --timeout 60 to limit per-task wait time"]
            if not any(kw in combined for kw in
                       ("AuthenticationError","401","NotFound","404",
                        "ConnectionError","ConnectTimeout","TIMEOUT","ERR")):
                hint_lines += [
                  "  • workflow() may have raised an exception with real data",
                  "    Run manually for full traceback:",
                  "    uv run python run_pipeline.py --tasks 1"]

            _fail(STEP, "Real LLM pipeline did not complete successfully",
                  "\n".join(hint_lines))

    except subprocess.TimeoutExpired:
        _fail(STEP, "Real LLM pipeline timed out after 420s (7 minutes)",
              "The API call took far too long. Possible causes:\n"
              "  • The model endpoint is severely overloaded — try again later\n"
              "  • Your network connection to the API is very poor\n"
              "  • The model name in .env is wrong and the call is hanging\n"
              "Try running manually to see live output:\n"
              "  uv run python run_pipeline.py --tasks 1 --timeout 300")

# ======================================================================
# Summary
# ======================================================================
print()
print("=" * 62)
if not errors:
    print(f"{PASS} All checks passed — your agent is ready for the test.")
    if warnings:
        print()
        print(f"  {WARN} {len(warnings)} warning(s) — not blocking, but worth reviewing:")
        for msg, hint in warnings:
            print(f"   • {msg}")
            if hint:
                for line in hint.strip().splitlines():
                    print(f"     💡 {line}")
    sys.exit(0)
else:
    print(f"{FAIL} {len(errors)} check(s) failed:\n")
    for step, msg, hint in errors:
        print(f"  [{step}] {msg}")
        if hint:
            for line in hint.strip().splitlines():
                print(f"         💡 {line}")
        print()
    print("Fix the issues above, then re-run this script.")
    sys.exit(1)
