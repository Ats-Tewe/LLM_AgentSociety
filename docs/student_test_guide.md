# AgentSociety Challenge — Test Day Guide

> **Prerequisites (already done before today):**
> You have already cloned the repository, set up the environment, configured your API key in `.env`, and implemented your agent in `crewai_simulation_agent.py`.
>
> Today's steps start from pulling the instructor's latest updates.

---

## Overview

| Step | Action | Time estimate |
|------|--------|---------------|
| **1** | Pull latest code from GitHub | ~2 min |
| **2** | Re-sync environment | ~1 min |
| **3** | Run self-check (`check_compatibility.py`) | ~5–10 min |
| **4** | Run the official test (`run_test.py`) | ~15–35 min |

---

## Recommended: Let Your Coding Agent Do Steps 1–3

> **This is the recommended approach.** Paste the prompt below into your Coding Agent (Claude Code, Cursor, Copilot, etc.). The agent will pull the latest code, resolve any conflicts, sync the environment, and keep retrying until all 5 compatibility checks pass — then stop and report back to you.
>
> Once the agent confirms all checks passed, skip directly to [Step 4](#step-4--run-the-official-test).
>
> If you prefer to run the steps manually, follow Steps 1–3 below instead.

```
Today is the official test day for AgentSociety Challenge.

Context you must understand before touching any files:

MY implementation files (written by me — must NEVER be overwritten):
  - src/crews/simulation_crew.py   ← my CrewAI crew design
  - config/agents.yaml             ← my agent role definitions
  - config/tasks.yaml              ← my task instructions
  - crewai_simulation_agent.py     ← adapter I may have customised

What the instructor's update contains (ONLY these change on the instructor's side):
  - run_test.py                    ← new or updated official test runner
  - scripts/check_compatibility.py ← new pre-test checker
  - docs/student_test_guide.md     ← new guide
  - pyproject.toml                 ← dependency updates only
  - uv.lock                        ← auto-generated lock file

Please complete the pre-test setup by doing the following steps in order:

1. Stash any local changes so the pull is clean:
   git stash

2. Pull the instructor's latest updates:
   git pull origin main

3. Re-apply my local changes:
   git stash pop

4. If git stash pop reports conflicts, resolve them file by file:
   - src/crews/simulation_crew.py → always keep MY version (git checkout --ours)
   - config/agents.yaml           → always keep MY version (git checkout --ours)
   - config/tasks.yaml            → always keep MY version (git checkout --ours)
   - crewai_simulation_agent.py   → preserve my existing code; only add new methods the instructor introduced
   - pyproject.toml               → keep BOTH sides' dependencies
   - uv.lock                      → accept the instructor's version (git checkout --theirs)
   After resolving, run: git add <resolved files> && git stash drop

5. Sync the environment:
   uv sync

6. Run the pre-test compatibility check:
   uv run python scripts/check_compatibility.py

7. If any check fails, read the error message and fix it, then re-run check_compatibility.py.

Keep going until you see:
✅ All checks passed — your agent is ready for the test.

Do not run run_test.py — stop after all 5 checks pass and tell me the result.
```

---

## Step 1 — Pull the Latest Code

The instructor has pushed the final test infrastructure to the repository. You need to pull it before anything else.

Navigate to your project folder and pull:

```bash
cd path/to/AgentSocietyChallenge_w_CrewAI   # wherever you cloned it
git pull origin main
```

Expected output (something like):

```
remote: Enumerating objects: 12, done.
...
Updating abc1234..def5678
 run_test.py                    | 200 +++++++++++++++++
 scripts/check_compatibility.py | 150 +++++++++++++
 docs/student_test_guide.md     |  80 +++++++
 pyproject.toml                 |   3 +
 uv.lock                        | 500 +++++++++++++++++++++
 ...
```

> The pull **only adds new files and updates dependencies** (`pyproject.toml`, `uv.lock`). It does **not** touch your implementation files (`src/crews/`, `config/`, `crewai_simulation_agent.py`). If you see those files listed as changed, stop and ask the instructor.

> If you see `Already up to date.`, wait for the instructor to confirm the push has gone through, then try again.

---

## Step 2 — Re-sync the Environment

New dependencies may have been added. Run:

```bash
uv sync
```

This ensures all required packages are installed. It should complete in under a minute.

---

## Step 3 — Self-Check

> **What to expect:** The script runs 5 checks in sequence. Checks [1/5]–[4/5] finish quickly (under 2 minutes total) — they verify your code structure and run a mock pipeline without calling any API. Check [5/5] makes one real LLM call through your `.env` credentials; you will see your CrewAI crew's full log output (banners, agent activity, tool calls) scroll past — this is normal and takes 2–5 minutes depending on your model. The whole script takes **5–10 minutes**. You must reach the final `✅ All checks passed` line before moving to Step 4.

Run the pre-test compatibility checker to confirm your agent will work with the official test runner:

```bash
uv run python scripts/check_compatibility.py
```

The script runs **5 automated checks** and takes roughly 5–10 minutes (check [5/5] makes one real LLM call):

| Check | What it verifies |
|-------|-----------------|
| `[1/5]` Import | Your `crewai_simulation_agent.py` can be imported without errors |
| `[2/5]` Methods | All 4 required methods exist and are callable |
| `[3/5]` Instantiation | `CrewAISimulationAgent(llm=None)` does not raise an exception |
| `[4/5]` Mock pipeline | End-to-end flow completes with mock LLM; output format is `{"stars": float, "review": str}` |
| `[5/5]` Real LLM | Connects to your API (from `.env`) and completes 1 task successfully |

**You must see this before proceeding to Step 4:**

```
============================================================
✅ All checks passed — your agent is ready for the test.
```

### If a check fails

Each failure prints a specific error and a `💡` fix hint. Common fixes:

| Check | Symptom | Fix |
|-------|---------|-----|
| `[1/5]` | `SyntaxError` | Fix the syntax error on the indicated line in `crewai_simulation_agent.py` |
| `[1/5]` | `ImportError` | Run `uv sync` to restore missing packages |
| `[2/5]` | Method missing | Add the missing method to your `CrewAISimulationAgent` class |
| `[3/5]` | `TypeError` on init | Change constructor to `def __init__(self, llm=None, *args, **kwargs)` |
| `[4/5]` | Output format wrong | Ensure `workflow()` returns `{"stars": float, "review": str}` |
| `[5/5]` | `AuthenticationError` | Check `OPENAI_API_KEY` in your `.env` — it may have expired |
| `[5/5]` | `model_not_found` | Check `OPENAI_MODEL_NAME` in `.env` |
| `[5/5]` | `ConnectionError` | Check WiFi connection and `OPENAI_API_BASE` in `.env` |

Fix the issue and **re-run `check_compatibility.py`** until all 5 checks pass.

---

## Step 4 — Run the Official Test

Once all 5 checks pass, start the test:

```bash
uv run python run_test.py
```

### 4.1 Enter team information

```
Step 1 — Enter team information
----------------------------------------
  Member 1 name  (or press Enter to finish): Alice
  Member 1 student ID: B12345678
  ✅ Added: Alice (B12345678)

  Member 2 name  (or press Enter to finish): Bob
  Member 2 student ID: B98765432
  ✅ Added: Bob (B98765432)

  Member 3 name  (or press Enter to finish):   ← press Enter to finish
```

Enter all team members one by one. Press **Enter on an empty name** when the whole team has been entered.

### 4.2 Confirm details and enter App Password

```
Step 2 — Confirm details
----------------------------------------
  Team members  : 2
    • Alice (B12345678)
    • Bob (B98765432)
  Test set      : Google Drive  (will download after confirmation)
  Timeout/task  : 300s
  Email subject : [AgentSociety Test] Alice_B12345678_Bob_B98765432 - 2026-05-XX 14:30
  Report to     : instructor@university.edu.tw

  App Password  : (provided by instructor) jjlpxxxxxxxxxxxxxxx
```

The script will pause here and ask for the **App Password**. The instructor will display this password on the projector on test day. Type or paste it in and press **Enter** — verify it matches what the instructor showed before proceeding.

```
Proceed? [y/N]:
```

Verify that names and student IDs are correct, then type `y` and press **Enter**.

### 4.3 Wait for completion (do not close the terminal)

> **What to expect:** The test downloads 35 tasks, then runs your full CrewAI crew on each one. Each task launches 3 agents in sequence — a User Profiler, a Restaurant Analyst, and a Review Prediction Expert — and each agent goes through a ReAct loop that makes multiple LLM calls (tool queries + reasoning). In total, one task consumes roughly **10–20 LLM API calls**. If your API hits its rate limit (429), the runner automatically waits 60 seconds and retries — you will see a `⚠️ Rate limit — waiting 60s` message; this is expected and you do not need to do anything. The whole inference stage typically takes **60–120 minutes**. Keep the terminal open and your laptop awake throughout.

The test runs automatically through 3 stages:

```
Step 3 — Loading test set ...
  ✅ Downloaded (31.3 KB)
  ✅ Extracted 35 tasks

Step 4 — Running inference ...
  ✅ Simulator initialized — 35 tasks
  ⏳ Task 01/35 — user=_RD91Kuq...  item=9c7MUiE6... → stars=3.5  (108s)
  ⏳ Task 02/35 — user=8zsD9N1t...  item=LINqYppb... → stars=4.0  (107s)
  ...
  ⚠️  Rate limit — waiting 60s before retry 2/3...   ← normal, no action needed
  ...

Step 5 — Official evaluation ...
```

- Each task takes roughly **1–5 minutes** depending on your model, network, and rate limits.
- 35 tasks typically complete in **60–120 minutes** total.
- **Do not close the terminal, sleep your laptop, or lose WiFi** during this time.

### 4.4 Results and submission

When finished, the results summary is printed and your report is emailed to the instructor automatically:

```
=================================================================
  EVALUATION RESULT SUMMARY
=================================================================
  preference_estimation         : 0.72...
  review_generation             : 0.68...
  overall_quality               : 0.70...
-----------------------------------------------------------------
  ⏱  Inference time : 420s  (avg 12s/task)
  ❌  Errors/timeouts: 0
  📁  Local report  : test_report_20260504_143012.json
=================================================================

Step 6 — Sending results to instructor ...
  ✅ Email sent to instructor@university.edu.tw

✅  Test run complete!
```

A local copy of the report is also saved in your project folder as `test_report_<timestamp>.json`.

---

## Troubleshooting

### `git pull` has conflicts

> **⚠️ Warning — files you must NEVER overwrite:**
> The following files contain YOUR implementation. No matter what conflict resolution strategy you use, always keep your own version of these files:
> - `src/crews/simulation_crew.py`
> - `config/agents.yaml`
> - `config/tasks.yaml`
>
> If any of these files appear in a conflict, run `git checkout --ours <file>` to restore your version immediately.

#### General approach — stash first, pull, re-apply

If you have local changes that conflict with the instructor's updates:

```bash
git stash          # temporarily set aside your local changes
git pull origin main
git stash pop      # re-apply your changes
```

If `git stash pop` reports conflicts, open the flagged files and resolve them manually, then:

```bash
git add <file>
git stash drop     # discard the now-applied stash entry
```

---

#### `uv.lock` conflict (most common)

`uv.lock` is auto-generated and almost always conflicts if you ran `uv add` or `uv sync` locally. Always accept the instructor's version — your local packages are not affected:

```bash
git checkout --theirs uv.lock
git add uv.lock
git merge --continue   # or: git rebase --continue
```

Then re-sync to make sure the environment matches:

```bash
uv sync
```

---

#### `pyproject.toml` conflict

If you manually added packages to `pyproject.toml`, the `[project].dependencies` block may conflict. Open the file and keep **both** the instructor's new packages and your own additions, then:

```bash
git add pyproject.toml
git merge --continue
uv sync
```

---

#### `run_pipeline.py` conflict

If you patched `run_pipeline.py` for debugging and the instructor also updated it, you need to merge manually. The critical change to preserve from the instructor's side is the mock LLM fix (the `litellm.completion` patch). After resolving:

```bash
git add run_pipeline.py
git merge --continue
```

---

#### `crewai_simulation_agent.py` conflict (your implementation)

This file contains your agent implementation. If the instructor added a new required method to the template, you need to add that method without removing your existing code. After resolving:

```bash
git add crewai_simulation_agent.py
git merge --continue
```

> If you are unsure whether your resolution is correct, re-run `uv run python scripts/check_compatibility.py` — it will catch any structural issues.

---

If any conflict remains unresolvable, ask the instructor for help.

---

### `run_test.py` — download fails

```
❌ Download failed
```

Check your WiFi connection. If the problem persists, inform the instructor — they can provide the test set via USB as a fallback:

```bash
uv run python run_test.py --test-set /path/to/test_set.zip
```

---

### `run_test.py` — task errors or timeouts

If some tasks show `stars=ERR` or `stars=TIMEOUT`, the test still continues and completes. Your score is calculated from the tasks that did succeed. The local report records all details.

---

### `run_test.py` — email not sent

Your local report (`test_report_<timestamp>.json`) is still saved. Show it to the instructor directly.

---

## Quick Reference

```bash
# Pull instructor's latest updates
git pull origin main
uv sync

# Self-check (must pass before running the test)
uv run python scripts/check_compatibility.py

# Official test
uv run python run_test.py

# If test set must be loaded from USB instead of Google Drive
uv run python run_test.py --test-set /path/to/test_set.zip
```
