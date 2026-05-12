"""
run_test.py — Official Test-Day Evaluation Runner

This script is run by students (with the instructor present) on test day.
It:
  1. Asks for team member names and student IDs (variable count)
  2. Prompts for the instructor-provided App Password (entered at runtime)
  3. Downloads the test set zip from Google Drive (or uses a local path)
  4. Runs inference on all test tasks
  5. Evaluates results with the official simulator
  6. Emails report.json + env.json to the instructor
  7. Saves a local copy of the report

Prerequisites:
  - .env must contain OPENAI_API_KEY and OPENAI_API_BASE
  - GDRIVE_URL below must be filled in by the instructor before distributing
  - The instructor will provide the App Password verbally / via slides on test day

Usage:
  uv run python run_test.py                          # download from Google Drive
  uv run python run_test.py --test-set local.zip     # use local zip (overrides GDRIVE_URL)
  uv run python run_test.py --threads 2              # parallel inference
  uv run python run_test.py --mock                   # dry-run, no API cost
"""
import sys
import os

if sys.prefix == sys.base_prefix:
    print("❌ Please run with uv: uv run python run_test.py", file=sys.stderr)
    sys.exit(1)

import json
import time
import smtplib
import logging
import argparse
import zipfile
import tempfile
import platform
import subprocess
from datetime import datetime
from email.message import EmailMessage
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

# ======================================================================
# Instructor-configured constants — fill in before distributing to students
# ======================================================================
INSTRUCTOR_EMAIL = "yc.ho@gms.ndhu.edu.tw"
# App Password is NOT stored here — it is entered by the student at runtime
# (prompted in Step 2 of the interactive flow).

# Google Drive sharing URL for the test set zip.
# Paste the "Anyone with the link" share URL here.
# Leave empty ("") to disable auto-download and use --test-set instead.
GDRIVE_URL = "https://drive.google.com/file/d/110h8DGAm1IEoAGl6Oqqg7fZMN4HM0dUv/view?usp=sharing"

# ======================================================================
# CLI
# ======================================================================
parser = argparse.ArgumentParser(description="AgentSociety Official Test-Day Runner")
parser.add_argument("--test-set", default=None,
                    metavar="ZIP", help="Local path to test set zip (overrides Google Drive download)")
parser.add_argument("--threads",  type=int, default=1,   metavar="N",
                    help="Worker threads (default: 1 = sequential)")
parser.add_argument("--timeout",  type=int, default=300, metavar="SEC",
                    help="Per-task timeout in seconds (default: 300)")
parser.add_argument("--mock",     action="store_true",
                    help="Use mock LLM (no token cost) — for dry-run / testing only")
args = parser.parse_args()

TIMEOUT_SEC = args.timeout if args.timeout > 0 else None

# ======================================================================
# Mock vs Real LLM
# ======================================================================
if args.mock:
    from unittest.mock import patch
    import litellm

    def _fake_completion(*a, **kw):
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

    patch("litellm.completion", side_effect=_fake_completion).start()
    os.environ["OPENAI_API_KEY"] = "sk-mock-key"
    print("⚙️  Mode: Mock LLM (dry-run)")
else:
    from dotenv import load_dotenv
    load_dotenv()

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

# ======================================================================
# Banner
# ======================================================================
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
print()
print("=" * 65)
print("  AgentSociety Challenge — Official Test-Day Evaluation")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 65)

# ======================================================================
# 1. Team member input
# ======================================================================
print()
print("Step 1 — Enter team information")
print("-" * 40)

members = []
while True:
    idx = len(members) + 1
    name = input(f"  Member {idx} name  (or press Enter to finish): ").strip()
    if not name:
        if not members:
            print("  ⚠️  At least one member is required.")
            continue
        break
    sid = input(f"  Member {idx} student ID: ").strip()
    if not sid:
        print("  ⚠️  Student ID cannot be empty.")
        continue
    members.append({"name": name, "student_id": sid})
    print(f"  ✅ Added: {name} ({sid})")
    print()

team_label = "_".join(f"{m['name']}_{m['student_id']}" for m in members)
date_label = datetime.now().strftime("%Y-%m-%d %H:%M")
email_subject = f"[AgentSociety Test] {team_label} - {date_label}"

# ======================================================================
# 2. Confirmation screen
# ======================================================================
print()
print("Step 2 — Confirm details")
print("-" * 40)
print(f"  Team members  : {len(members)}")
for m in members:
    print(f"    • {m['name']} ({m['student_id']})")
if args.test_set:
    print(f"  Test set      : {args.test_set}  (local)")
elif GDRIVE_URL:
    print(f"  Test set      : Google Drive  (will download after confirmation)")
else:
    print(f"  Test set      : ⚠️  not configured")
print(f"  Threads       : {args.threads}")
print(f"  Timeout/task  : {TIMEOUT_SEC or '∞'}s")
print(f"  Email subject : {email_subject}")
print(f"  Report to     : {INSTRUCTOR_EMAIL or '⚠️  (not configured)'}")
print()

INSTRUCTOR_APP_PASSWORD = input("  App Password  : (provided by instructor) ").strip()
if not INSTRUCTOR_APP_PASSWORD:
    print("  ⚠️  App Password is required to submit results.")
    sys.exit(1)
print()

confirm = input("Proceed? [y/N]: ").strip().lower()
if confirm != "y":
    print("Aborted.")
    sys.exit(0)

# ======================================================================
# 3. Obtain test set zip (Google Drive download or local path)
# ======================================================================
print()
print("Step 3 — Loading test set ...")

tmp_dir_obj = tempfile.TemporaryDirectory(prefix="agentsociety_test_")
tmp_dir  = tmp_dir_obj.name
task_dir = os.path.join(tmp_dir, "tasks")
gt_dir   = os.path.join(tmp_dir, "groundtruth")

# Decide source: explicit --test-set overrides GDRIVE_URL
if args.test_set:
    # --- Local file (override mode) ---
    if not os.path.exists(args.test_set):
        print(f"❌ Test set not found: {args.test_set}", file=sys.stderr)
        sys.exit(1)
    zip_path = args.test_set
    print(f"  ℹ️  Using local file: {zip_path}")

elif GDRIVE_URL:
    # --- Google Drive download ---
    import gdown
    zip_path = os.path.join(tmp_dir, "test_set.zip")
    print(f"  ⏳ Downloading test set from Google Drive ...")
    try:
        # Extract file ID from sharing URL and download
        import re as _re
        _m = _re.search(r"/d/([a-zA-Z0-9_-]+)", GDRIVE_URL)
        file_id = _m.group(1) if _m else GDRIVE_URL
        gdown.download(id=file_id, output=zip_path, quiet=False)
    except Exception as e:
        print(f"❌ Download failed: {e}", file=sys.stderr)
        print("   Check your internet connection and confirm the sharing link is", file=sys.stderr)
        print("   set to 'Anyone with the link — Viewer'.", file=sys.stderr)
        tmp_dir_obj.cleanup()
        sys.exit(1)
    if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
        print("❌ Downloaded file is empty or missing.", file=sys.stderr)
        print("   The Google Drive link may have expired or sharing permissions", file=sys.stderr)
        print("   may not be set to 'Anyone with the link'.", file=sys.stderr)
        tmp_dir_obj.cleanup()
        sys.exit(1)
    size_kb = os.path.getsize(zip_path) / 1024
    print(f"  ✅ Downloaded ({size_kb:.1f} KB)")

else:
    print("❌ No test set available.", file=sys.stderr)
    print("   Either set GDRIVE_URL in run_test.py, or pass a local zip:", file=sys.stderr)
    print("   uv run python run_test.py --test-set /path/to/test_set.zip", file=sys.stderr)
    tmp_dir_obj.cleanup()
    sys.exit(1)

# Extract zip
with zipfile.ZipFile(zip_path, "r") as zf:
    zf.extractall(tmp_dir)

n_tasks = len([f for f in os.listdir(task_dir) if f.endswith(".json")])
print(f"  ✅ Extracted {n_tasks} tasks")

# ======================================================================
# 4. Inference
# ======================================================================
from websocietysimulator import Simulator
from crewai_simulation_agent import CrewAISimulationAgent

print()
print("Step 4 — Running inference ...")
print(f"  (threads={args.threads}, timeout={TIMEOUT_SEC or '∞'}s)")

init_start = time.time()
simulator = Simulator(data_dir="dummy_dataset", device="cpu", cache=True)
simulator.set_task_and_groundtruth(task_dir=task_dir, groundtruth_dir=gt_dir)
simulator.set_agent(CrewAISimulationAgent)
init_elapsed = time.time() - init_start
print(f"  ✅ Simulator initialized ({init_elapsed:.1f}s) — {len(simulator.tasks)} tasks")

def _run_single(idx, task, interaction_tool):
    from crewai_simulation_agent import CrewAISimulationAgent as Cls
    agent = Cls()
    agent.set_interaction_tool(interaction_tool)
    agent.insert_task(task)
    return agent.workflow()

_RATE_LIMIT_RETRIES = 3

def _run_single_with_retry(idx, task, interaction_tool):
    for attempt in range(_RATE_LIMIT_RETRIES):
        try:
            return _run_single(idx, task, interaction_tool)
        except Exception as e:
            is_rate_limit = "RateLimitError" in type(e).__name__ or "429" in str(e)
            if is_rate_limit and attempt < _RATE_LIMIT_RETRIES - 1:
                wait = 60 * (attempt + 1)
                print(f"\n    ⚠️  Rate limit — waiting {wait}s before retry {attempt + 2}/{_RATE_LIMIT_RETRIES}...", flush=True)
                time.sleep(wait)
                continue
            raise

infer_start = time.time()
per_task_times = []
simulator.simulation_outputs = []

if args.threads > 1:
    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        futures_map = {
            ex.submit(_run_single_with_retry, i, t, simulator.interaction_tool): (i, t)
            for i, t in enumerate(simulator.tasks)
        }
        for future in as_completed(futures_map):
            i, t = futures_map[future]
            t0 = time.time()
            try:
                output = future.result(timeout=TIMEOUT_SEC)
                result = {"task": t.to_dict(), "output": output}
                stars  = output.get("stars", "N/A")
            except FuturesTimeout:
                result = {"task": t.to_dict(), "output": {"stars": 0, "review": ""}, "error": f"Timeout after {TIMEOUT_SEC}s"}
                stars  = "TIMEOUT"
            except Exception as e:
                result = {"task": t.to_dict(), "output": {"stars": 0, "review": ""}, "error": str(e)}
                stars  = "ERR"
            elapsed = time.time() - t0
            per_task_times.append(elapsed)
            simulator.simulation_outputs.append(result)
            print(f"  Task {i+1:02d}/{len(simulator.tasks)} — stars={stars}  ({elapsed:.1f}s)")
else:
    for i, t in enumerate(simulator.tasks):
        print(f"  ⏳ Task {i+1:02d}/{len(simulator.tasks)} — user={t.user_id[:8]}...  item={t.item_id[:8]}...", end="", flush=True)
        t0 = time.time()
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                output = ex.submit(_run_single_with_retry, i, t, simulator.interaction_tool).result(timeout=TIMEOUT_SEC)
            result = {"task": t.to_dict(), "output": output}
            stars  = output.get("stars", "N/A")
        except FuturesTimeout:
            result = {"task": t.to_dict(), "output": {"stars": 0, "review": ""}, "error": f"Timeout after {TIMEOUT_SEC}s"}
            stars  = "TIMEOUT"
        except Exception as e:
            result = {"task": t.to_dict(), "output": {"stars": 0, "review": ""}, "error": str(e)}
            stars  = "ERR"
        elapsed = time.time() - t0
        per_task_times.append(elapsed)
        simulator.simulation_outputs.append(result)
        print(f" → stars={stars}  ({elapsed:.1f}s)")

infer_elapsed = time.time() - infer_start

# ======================================================================
# 5. Evaluate
# ======================================================================
print()
print("Step 5 — Official evaluation ...")
eval_results = simulator.evaluate()

# ======================================================================
# 6. Build report
# ======================================================================
def _git(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"

error_count = sum(1 for r in simulator.simulation_outputs if "error" in r)
avg_time = sum(per_task_times) / len(per_task_times) if per_task_times else 0

api_key  = os.environ.get("OPENAI_API_KEY", "")
api_base = os.environ.get("OPENAI_API_BASE", "")
model    = os.environ.get("OPENAI_MODEL_NAME", "mock" if args.mock else "(not set)")

report = {
    "run_timestamp": RUN_TIMESTAMP,
    "team_members":  members,
    "mode":          "mock" if args.mock else "real_llm",
    "config": {
        "threads":         args.threads,
        "timeout_seconds": TIMEOUT_SEC,
        "tasks_run":       len(simulator.tasks),
    },
    "timing": {
        "init_seconds":      round(init_elapsed, 2),
        "inference_seconds": round(infer_elapsed, 2),
        "avg_task_seconds":  round(avg_time, 2),
        "min_task_seconds":  round(min(per_task_times), 2) if per_task_times else 0,
        "max_task_seconds":  round(max(per_task_times), 2) if per_task_times else 0,
    },
    "errors":           error_count,
    "evaluation":       eval_results,
    "per_task_outputs": simulator.simulation_outputs,
}

env_snapshot = {
    "run_timestamp":  RUN_TIMESTAMP,
    "team_members":   members,
    "git_branch":     _git(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
    "git_commit":     _git(["git", "rev-parse", "--short", "HEAD"]),
    "git_dirty":      bool(_git(["git", "status", "--porcelain"])),
    "python_version": platform.python_version(),
    "model":          model,
    "api_base":       api_base,
    "platform":       platform.system().lower(),
}

REPORT_PATH = f"test_report_{RUN_TIMESTAMP}.json"
with open(REPORT_PATH, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

# ======================================================================
# 7. Summary
# ======================================================================
print()
print("=" * 65)
print("  EVALUATION RESULT SUMMARY")
print("=" * 65)
for k, v in eval_results.get("metrics", {}).items():
    print(f"  {k:30s}: {v}")
print("-" * 65)
print(f"  ⏱  Inference time : {infer_elapsed:.1f}s  (avg {avg_time:.1f}s/task)")
print(f"  ❌  Errors/timeouts: {error_count}")
print(f"  📁  Local report  : {REPORT_PATH}")
print("=" * 65)

# ======================================================================
# 8. Email results to teacher
# ======================================================================
report_bytes = json.dumps(report,       indent=2, ensure_ascii=False).encode("utf-8")
env_bytes    = json.dumps(env_snapshot, indent=2, ensure_ascii=False).encode("utf-8")

if not INSTRUCTOR_EMAIL or not INSTRUCTOR_APP_PASSWORD:
    print()
    print("⚠️  Email not configured (INSTRUCTOR_EMAIL / INSTRUCTOR_APP_PASSWORD not set).")
    print(f"   Please send {REPORT_PATH} to the instructor manually.")
else:
    print()
    print("Step 6 — Sending results to teacher ...")
    msg = EmailMessage()
    msg["Subject"] = email_subject
    msg["From"]    = INSTRUCTOR_EMAIL
    msg["To"]      = INSTRUCTOR_EMAIL

    metrics_lines = "\n".join(
        f"  {k}: {v}" for k, v in eval_results.get("metrics", {}).items()
    )
    members_lines = "\n".join(
        f"  {m['name']} ({m['student_id']})" for m in members
    )
    msg.set_content(
        f"AgentSociety Challenge — Test-Day Evaluation Result\n"
        f"====================================================\n\n"
        f"Team:\n{members_lines}\n\n"
        f"Metrics:\n{metrics_lines}\n\n"
        f"Errors/timeouts : {error_count}\n"
        f"Inference time  : {infer_elapsed:.1f}s\n"
        f"Timestamp       : {RUN_TIMESTAMP}\n\n"
        f"Full details in attached JSON files.\n"
    )
    msg.add_attachment(report_bytes,
                       maintype="application", subtype="json",
                       filename=f"report_{team_label}_{RUN_TIMESTAMP}.json")
    msg.add_attachment(env_bytes,
                       maintype="application", subtype="json",
                       filename=f"env_{team_label}_{RUN_TIMESTAMP}.json")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(INSTRUCTOR_EMAIL, INSTRUCTOR_APP_PASSWORD)
            server.send_message(msg)
        print(f"  ✅ Email sent to {INSTRUCTOR_EMAIL}")
    except smtplib.SMTPAuthenticationError as e:
        print(f"  ❌ Authentication failed: {e}", file=sys.stderr)
        print(f"   Manually send {REPORT_PATH} to the teacher.", file=sys.stderr)
    except Exception as e:
        print(f"  ❌ Email error ({type(e).__name__}): {e}", file=sys.stderr)
        print(f"   Manually send {REPORT_PATH} to the teacher.", file=sys.stderr)

# ======================================================================
# 9. Cleanup temp dir
# ======================================================================
tmp_dir_obj.cleanup()

print()
print("✅  Test run complete!")
