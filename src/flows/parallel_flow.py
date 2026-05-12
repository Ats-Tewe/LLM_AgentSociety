"""Parallel CrewAI flow for Yelp review prediction.

Architecture:
  user_profiler ──┐
                  ├──► prediction_modeler  →  {"stars": X, "review": "..."}
  item_analyst  ──┘

Both analysis agents run concurrently via CrewAI Flow's and_() join.
Data is pre-fetched in CrewAISimulationAgent; agents receive summaries as inputs.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, and_, listen, start
from pydantic import BaseModel

from src.crews.simulation_crew import _build_llm, _rag_tool

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _agents_cfg() -> dict:
    with open(_CONFIG_DIR / "agents.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _tasks_cfg() -> dict:
    with open(_CONFIG_DIR / "tasks.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ParallelState(BaseModel):
    """Flow state — inputs from pre-fetch + intermediate analysis + final output."""
    # Inputs (identical to InferenceState)
    user_id:          str   = ""
    item_id:          str   = ""
    user_summary:     str   = ""
    item_summary:     str   = ""
    history_summary:  str   = ""
    fallback_rating:  float = 4.0
    # Intermediate: parallel agent outputs
    user_analysis:    str   = ""
    item_analysis:    str   = ""
    # Outputs (same field names as InferenceState — required by crewai_simulation_agent.py)
    predicted_rating: float = 0.0
    generated_review: str   = ""


class YelpParallelFlow(Flow[ParallelState]):
    """Parallel flow: user_profiler and item_analyst run concurrently.

    user_profiler ──┐
                    ├──► prediction_modeler
    item_analyst  ──┘
    """

    @start()
    def analyze_user(self) -> None:
        agent = Agent(
            config=_agents_cfg()["user_profiler"],
            llm=_build_llm(),
            verbose=False,
            allow_delegation=False,
            max_iter=2,
        )
        task_cfg = {k: v for k, v in _tasks_cfg()["analyze_user_task"].items() if k != "agent"}
        task = Task(**task_cfg, agent=agent)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff(inputs={
            "user_summary":    self.state.user_summary,
            "history_summary": self.state.history_summary,
            "item_summary":    self.state.item_summary,
        })
        self.state.user_analysis = getattr(result, "raw", "") or ""

    @start()
    def analyze_item(self) -> None:
        rag = _rag_tool()
        task_key = "analyze_item_task_rag" if rag else "analyze_item_task"
        agent = Agent(
            config=_agents_cfg()["item_analyst"],
            llm=_build_llm(),
            verbose=False,
            allow_delegation=False,
            max_iter=3 if rag else 2,
            tools=[rag] if rag else [],
        )
        task_cfg = {k: v for k, v in _tasks_cfg()[task_key].items() if k != "agent"}
        task = Task(**task_cfg, agent=agent)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff(inputs={
            "item_summary":    self.state.item_summary,
            "user_summary":    self.state.user_summary,
            "history_summary": self.state.history_summary,
        })
        self.state.item_analysis = getattr(result, "raw", "") or ""

    @listen(and_(analyze_user, analyze_item))
    def predict_review(self) -> dict:
        agent = Agent(
            config=_agents_cfg()["prediction_modeler"],
            llm=_build_llm(),
            verbose=True,
            allow_delegation=False,
            max_iter=3,
        )
        task_cfg = {k: v for k, v in _tasks_cfg()["predict_review_task_parallel"].items() if k != "agent"}
        task = Task(**task_cfg, agent=agent)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
        result = crew.kickoff(inputs={
            "user_analysis":   self.state.user_analysis  or "User analysis unavailable.",
            "item_analysis":   self.state.item_analysis  or "Item analysis unavailable.",
            "history_summary": self.state.history_summary,
            "user_summary":    self.state.user_summary,
            "item_summary":    self.state.item_summary,
        })

        raw = getattr(result, "raw", "") or ""
        try:
            m = re.search(r'\{[^{}]*"stars"[^{}]*"review"[^{}]*\}', raw, re.DOTALL)
            if m:
                data = json.loads(m.group())
                self.state.predicted_rating = max(
                    1.0, min(5.0, float(data.get("stars", self.state.fallback_rating)))
                )
                self.state.generated_review = str(data.get("review", "")).strip()
            else:
                self.state.predicted_rating = self.state.fallback_rating
                self.state.generated_review = raw[:500] or "No review generated."
        except Exception:
            self.state.predicted_rating = self.state.fallback_rating
            self.state.generated_review = raw[:500] or "Prediction failed."

        return self.state.model_dump()
