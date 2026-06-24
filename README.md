# AgentSociety Challenge — OpenEvolve + CrewAI Yelp Review Predictor

> **Assignment 2 — Final Project** LLM Course (Second Semester 2026)
>
> **Student:** Atsbaha Teweldemedhn Hagos |
> **Track:** User Behavior Simulation | **Framework:** OpenEvolve + CrewAI + NVIDIA NIM

---

## What This Project Does

This project **automatically evolves CrewAI agent prompts** using the OpenEvolve framework — a MAP-Elites + island-based evolutionary algorithm — to maximize Yelp review prediction accuracy.

Given a Yelp **user ID** and **business ID**, the evolved system predicts:
1. The **star rating** (1–5) the user would give to that business
2. The **review text** the user would write — matching their real writing voice

The system **starts** from the Assignment 1 baseline (score = 0.847) and **evolves** agent prompts over 50 iterations, discovering better prompt strategies without manual tuning.

---

## Assignment 1 → Assignment 2 Improvements

| | Assignment 1 (Baseline) | Assignment 2 (Evolved) |
|---|---|---|
| **Framework** | CrewAI (manual prompts) | CrewAI + OpenEvolve (auto-evolved) |
| **Agents** | 4 (+ manager) | 4 (+ manager) — new `rating_critic` |
| **combined_score** | 0.847 | **0.9525** (+12.5%) |
| **preference_estimation** | 0.878 | **1.0000** |
| **review_generation** | 0.821 | **0.9049** |
| **Prompt strategy** | Hand-crafted | Machine-discovered via evolution |
| **Iterations** | N/A | 50 iterations, 3 islands |
| **Programs survived** | N/A | 17 programs in MAP-Elites archive |

---

## Architecture

```
OpenEvolve Evolution Loop (50 iterations × 3 islands)
│
├── SEED (Gen-0): config/agents_evolving.yaml
│     └── EVOLVE-BLOCK covers BOTH agent roles AND task descriptions
│
├── Mutation LLM: NVIDIA NIM → Groq (circular fallback)
│
├── MAP-Elites Archive: best program per (complexity, diversity) cell
│
└── BEST (Gen-1): config/openevolve_output/best/best_program.yaml
      └── Discovered at iteration 32, combined_score = 0.9525

CrewAI Pipeline (run by each evaluated program):
  ① Pre-fetch:  get_user() · get_item() · get_reviews(user) · get_reviews(item)
  ② Agents:     user_profiler → item_analyst → prediction_modeler → rating_critic
  ③ Output:     { "stars": float, "review": str }
```

---

## Evolution Results

| Metric | Value |
|--------|-------|
| **combined_score (best)** | **0.9525** |
| preference_estimation | 1.0000 |
| review_generation | 0.9049 |
| Best iteration | 32 (Generation 1) |
| Total iterations | 50 |
| Islands | 3 |
| Programs in final archive | **17** |
| Archive score range | 0.9434 – 0.9525 |
| Assignment 1 baseline | 0.847 |
| **Improvement** | **+12.5%** |

---

## Gen-0 → Gen-1 Prompt Evolution

OpenEvolve discovered these changes automatically through 50 iterations of mutation and selection:

### `prediction_modeler` — Star Formula

| | Gen-0 Seed | Gen-1 Best (evolved) |
|---|---|---|
| Formula | `base = 0.60×A + 0.30×B + 0.10×C` | `base = 0.55×A + 0.30×B + 0.15×C` |
| Lenient threshold | avg ≥ 4.0 | avg > 3.8 |
| PEER adjustment | ±0.3 | ±0.2 |

*(A = USER_HISTORICAL_AVERAGE_STARS, B = PRIOR_STAR_ESTIMATE, C = USER_MODAL_STARS)*

### `rating_critic` — Correction Formula

| | Gen-0 Seed | Gen-1 Best (evolved) |
|---|---|---|
| Trigger threshold | \|predicted − PRIOR\| > 0.75 | \|predicted − PRIOR\| > 0.65 |
| Correction | `round(0.70×PRIOR + 0.30×predicted)` | `round(0.65×PRIOR + 0.35×predicted)` |

### Agent Temperatures

| Agent | Gen-0 | Gen-1 |
|-------|-------|-------|
| user_profiler | 0.30 | 0.25 |
| item_analyst | 0.30 | 0.25 |
| prediction_modeler | 0.20 | 0.20 |
| rating_critic | 0.10 | 0.10 |

---

## 4 Creative Novelties

### 1. Evolving BOTH Agent Prompts AND Task Descriptions Together

Unlike typical OpenEvolve usage (which only mutates agent role/goal/backstory), the `EVOLVE-BLOCK` in `config/agents_evolving.yaml` covers **both agent definitions and task descriptions** simultaneously.

This means OpenEvolve discovers better **reasoning strategies** (what to compute, in what order, how to format output) — not just personality changes. The evolved task descriptions instruct agents differently about HOW to think through the prediction problem.

### 2. The `rating_critic` Agent (4th Evolved Agent)

A new agent that does not exist in the Assignment 1 baseline. After `prediction_modeler` outputs a star rating, `rating_critic` validates it against `PRIOR_STAR_ESTIMATE` using a mathematical correction formula:

```
IF |predicted − PRIOR| > threshold:
    corrected = round(weight_prior × PRIOR + weight_pred × predicted)
```

This prevents the #1 LLM failure mode: hallucinating 4.0 or 5.0 regardless of the user's actual rating history. OpenEvolve evolved both the threshold and the correction weights.

### 3. Explicit Mathematical Formula Embedded in Agent Prompts

Instead of telling the LLM to "use the user's history," the `prediction_modeler` prompt contains an **exact weighted formula**:

```
base = A × USER_HISTORICAL_AVERAGE_STARS + B × PRIOR_STAR_ESTIMATE + C × USER_MODAL_STARS
```

OpenEvolve can then discover optimal coefficient values (A, B, C) through evolution. Gen-0 started at (0.60, 0.30, 0.10); Gen-1 evolved to (0.55, 0.30, 0.15) — giving more weight to the user's most-frequent star rating.

### 4. Circular LLM Fallback for the OpenEvolve Mutation Engine

OpenEvolve's `LLMEnsemble` natively uses **random weighted selection** among providers — if the selected provider times out, that iteration is wasted. 

The `openevolve_evaluator.py` monkey-patches `LLMEnsemble.generate_with_context` to implement **circular sequential fallback**:

```
NVIDIA NIM (3 attempts) → Groq account 1 (3 attempts) → Groq account 2 (3 attempts) → NVIDIA (circular)
```

This ensures **no iteration is ever wasted**: the next provider takes over automatically. The patch uses `_last_success_idx` state to remember which provider last worked, minimizing unnecessary fallback attempts.

---

## Project Structure

```
AgentSocietyChallenge_w_CrewAI-main/
│
├── run_evolve.ps1                     # Run OpenEvolve (50 iterations)
├── openevolve_evaluator.py            # OpenEvolve fitness function + circular LLM fallback
├── plot_evolution.py                  # Evolution curve visualizer (custom-built)
├── crewai_simulation_agent.py         # Data pre-fetch + star prior + post-processing
│
├── config/
│   ├── agents_evolving.yaml           # Gen-0 SEED — EVOLVE-BLOCK covers agents + tasks
│   ├── openevolve_config.yaml         # OpenEvolve settings (3 islands, MAP-Elites)
│   ├── agents.yaml                    # Static agent definitions (Assignment 1 baseline)
│   ├── tasks.yaml                     # Task prompts
│   └── openevolve_output/
│       ├── best/
│       │   ├── best_program.yaml      # Gen-1 BEST EVOLVED program
│       │   └── best_program_info.json # Score metadata (0.9525 at iter 32)
│       ├── checkpoints/               # checkpoint_5, _10, ..., _50 (each has programs/)
│       └── evolution_curve.png        # Generated by plot_evolution.py
│
├── src/
│   └── crews/
│       ├── simulation_crew.py         # Sequential crew
│       ├── hierarchical_crew.py       # Hierarchical crew (Assignment 1 best mode)
│       └── evolving_crew.py           # 4-agent crew used during OpenEvolve evaluation
│
├── websocietysimulator/               # Competition framework (do not modify)
└── dummy_dataset/                     # Local Yelp data for development
```

---

## Setup

### Prerequisites
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager

### Installation

```powershell
# 1. Clone the repository
git clone https://github.com/Ats-Tewe/LLM_AgentSociety.git
cd LLM_AgentSociety

# 2. Install dependencies
uv sync

# 3. Install visualization dependency
uv add matplotlib
```

### API Keys

The evolution script reads API keys directly in `run_evolve.ps1`. Edit the file to set your own keys:

```powershell
# NVIDIA NIM (primary LLM for agents + OpenEvolve mutation)
$env:OPENAI_API_KEY   = "nvapi-your-key-here"
$env:OPENAI_API_BASE  = "https://integrate.api.nvidia.com/v1"

# Groq fallback accounts (circular failover)
$env:GROQ_API_KEY     = "gsk_your-groq-key-1"
$env:GROQ_API_KEY_2   = "gsk_your-groq-key-2"
```

---

## Running

### Run OpenEvolve Evolution (50 iterations)

```powershell
.\run_evolve.ps1
```

This runs MAP-Elites evolutionary search for 50 iterations across 3 islands, evaluating each mutated program on 1 Yelp task. The best evolved program is saved to `config/openevolve_output/best/best_program.yaml`.

### Visualize the Evolution Curve

```powershell
uv run python plot_evolution.py
```

Reads all checkpoint `best_program_info.json` files and generates `config/openevolve_output/evolution_curve.png` — a dual-panel chart showing:
- Top: `combined_score` vs iteration (with best-score annotation and Assignment 1 baseline line)
- Bottom: MAP-Elites archive size growth per checkpoint

### Evaluate the Best Evolved Program

```powershell
uv run python openevolve_evaluator.py
```

Runs the best evolved agent configuration (`config/openevolve_output/best/best_program.yaml`) against the local Yelp tasks and prints `combined_score`, `preference_estimation`, and `review_generation`.

### Development Smoke Test (Mock Mode)

```powershell
$env:PYTHONUTF8=1; uv run python run_test.py --mock
```

---

## How the Agents Work

| Agent | Role | Key Contribution |
|-------|------|-----------------|
| `user_profiler` | Yelp User Behavior Analyst | Analyzes rating history, writing style, category preferences |
| `item_analyst` | Business Intelligence Analyst | Extracts business profile, strengths, complaints from peer reviews |
| `prediction_modeler` | Prediction Strategist | Applies weighted formula → outputs `{"stars": X, "review": "..."}` |
| `rating_critic` | Rating Validation Specialist | Corrects star if it deviates too far from statistical prior *(evolved threshold + weights)* |

### Data Pre-Fetched Before Agents Run (Zero LLM Cost)

| Variable | Source |
|----------|--------|
| `USER_HISTORICAL_AVERAGE_STARS` | Average of all user's past star ratings |
| `USER_MODAL_STARS` | User's most-frequently-given star rating |
| `USER_RATING_VARIANCE` | Standard deviation — flags consistent vs. erratic raters |
| `USER_TYPICAL_WORD_COUNT` | Avg word count — forces review length matching |
| `PEER_AVG_STARS` | Average stars from peer reviews of this business |
| `USER_CATEGORY_SPECIFIC_AVERAGE` | User's avg stars for similar venues |
| `PRIOR_STAR_ESTIMATE` | Adaptive blend of user avg + item avg (weights by review count) |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `crewai` | Multi-agent orchestration framework |
| `openevolve` | MAP-Elites evolutionary prompt optimization |
| `litellm` | Unified LLM API client with fallback support |
| `matplotlib` | Evolution curve visualization |
| `pydantic` | State management and data validation |
| `uv` | Fast Python package manager |

---

## Repository

GitHub: [https://github.com/Ats-Tewe/LLM_AgentSociety](https://github.com/Ats-Tewe/LLM_AgentSociety)

---

*Built on the [WWW'25 AgentSociety Challenge](https://github.com/tsinghua-fib-lab/AgentSocietyChallenge) framework by Tsinghua University FIB Lab.*
*OpenEvolve: [https://github.com/codelion/openevolve](https://github.com/codelion/openevolve)*
