"""
evolving_crew.py — Dynamically builds a 4-agent CrewAI crew from the
YAML file that OpenEvolve writes to OPENEVOLVE_AGENTS_YAML env var.

Agents:  user_profiler -> item_analyst -> prediction_modeler -> rating_critic
Novelty: Both agent prompts AND task descriptions are loaded from the
         evolved YAML, so OpenEvolve mutates both simultaneously.
"""
import json
import os
import re
import yaml

from crewai import Agent, Crew, Process, Task, LLM


def _build_llm(temperature: float = 0.3) -> LLM:
    key = os.environ.get("NVIDIA_API_KEY", os.environ.get("LLAMA_API_KEY", ""))
    return LLM(
        model="nvidia_nim/minimaxai/minimax-m2.7",
        api_key=key,
        temperature=temperature,
        max_retries=3,
    )


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_json_from_crew_output(raw: str) -> dict:
    """Extract a {stars, review} dict from noisy LLM output."""
    text = str(raw).strip()
    text = text.replace("{{", "{").replace("}}", "}")

    # Try to find {"stars": ..., "review": ...} pattern
    match = re.search(r'\{[^{}]*"stars"[^{}]*"review"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Try reversed key order
    match = re.search(r'\{[^{}]*"review"[^{}]*"stars"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Try parsing the whole text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Last resort: extract star number from text
    star_match = re.search(r'"stars"\s*:\s*([\d.]+)', text)
    rating = float(star_match.group(1)) if star_match else 4.0
    review_match = re.search(r'"review"\s*:\s*"([^"]*)"', text)
    review = review_match.group(1) if review_match else text[:300]
    return {"stars": rating, "review": review}


def build_evolving_crew(inputs: dict) -> Crew:
    """
    Build a 4-agent Crew from the OpenEvolve-mutated YAML.

    The YAML contains:
      - Top-level agent keys: user_profiler, item_analyst,
                              prediction_modeler, rating_critic
      - Sub-key 'tasks': analyze_user_task, analyze_item_task,
                         predict_review_task, validate_prediction_task

    Args:
        inputs: dict passed to Crew.kickoff(inputs=inputs).
                Must contain user_summary, item_summary,
                history_summary, fallback_rating, user_id, item_id.

    Returns:
        A ready-to-run CrewAI Crew object.
    """
    yaml_path = os.environ.get("OPENEVOLVE_AGENTS_YAML")
    if not yaml_path or not os.path.exists(yaml_path):
        raise FileNotFoundError(
            f"OPENEVOLVE_AGENTS_YAML not set or missing: {yaml_path}"
        )

    config = _load_yaml(yaml_path)

    # Separate tasks sub-dict from agent dicts
    tasks_config: dict = config.pop("tasks", {})
    agents_config: dict = config  # remaining keys are agent definitions

    # -----------------------------------------------------------------
    # Build agents
    # -----------------------------------------------------------------
    def make_agent(name: str, max_iter: int = 3) -> Agent:
        cfg = agents_config.get(name, {})
        temp = float(cfg.get("temperature", 0.3))
        return Agent(
            role=str(cfg.get("role", name)).strip(),
            goal=str(cfg.get("goal", "")).strip(),
            backstory=str(cfg.get("backstory", "")).strip(),
            llm=_build_llm(temperature=temp),
            verbose=False,
            allow_delegation=False,
            max_iter=max_iter,
        )

    profiler  = make_agent("user_profiler",     max_iter=2)
    analyst   = make_agent("item_analyst",      max_iter=2)
    modeler   = make_agent("prediction_modeler", max_iter=3)
    critic    = make_agent("rating_critic",     max_iter=2)

    # -----------------------------------------------------------------
    # Build tasks (descriptions are template strings filled by kickoff)
    # -----------------------------------------------------------------
    def make_task(name: str, agent: Agent, context: list = None) -> Task:
        cfg = tasks_config.get(name, {})
        desc     = str(cfg.get("description", "")).strip()
        expected = str(cfg.get("expected_output", "")).strip()
        kwargs = dict(description=desc, expected_output=expected, agent=agent)
        if context:
            kwargs["context"] = context
        return Task(**kwargs)

    t_user    = make_task("analyze_user_task",       profiler)
    t_item    = make_task("analyze_item_task",        analyst)
    t_predict = make_task("predict_review_task",      modeler,  context=[t_user, t_item])
    t_validate= make_task("validate_prediction_task", critic,   context=[t_user, t_item, t_predict])

    return Crew(
        agents=[profiler, analyst, modeler, critic],
        tasks=[t_user, t_item, t_predict, t_validate],
        process=Process.sequential,
        verbose=True,
    )
