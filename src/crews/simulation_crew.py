import os
import sqlite3
from pathlib import Path

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task


def _build_llm() -> LLM:
    """Explicit api_key bypasses the system-level OPENAI_API_KEY conflict."""
    nvidia_key = os.environ.get("NVIDIA_API_KEY", os.environ.get("LLAMA_API_KEY", ""))
    groq_key   = os.environ.get("GROQ_API_KEY", "")
    groq_key2  = os.environ.get("GROQ_API_KEY_2", "")

    nvidia_model = "nvidia_nim/minimaxai/minimax-m2.7"
    groq_model   = "groq/llama-3.3-70b-versatile"

    fallbacks = []
    if groq_key:
        fallbacks.append({"model": groq_model, "api_key": groq_key})
    if groq_key2:
        fallbacks.append({"model": groq_model, "api_key": groq_key2})

    return LLM(model=nvidia_model, api_key=nvidia_key, max_retries=3, fallbacks=fallbacks)


def _rag_tool():
    """Return search_historical_reviews tool when RAG_ENABLED=1 and chroma_index present."""
    if os.environ.get("RAG_ENABLED", "0").strip() not in ("1", "true", "True"):
        return None

    # chroma_index lives at workspace root (parents[3] from src/crews/<file>)
    workspace = Path(__file__).resolve().parents[3]
    candidates = [workspace / "chroma_index" / "chroma.sqlite3"]
    storage_dir = os.environ.get("CREWAI_STORAGE_DIR", "").strip()
    if storage_dir:
        candidates.insert(0, Path(storage_dir) / "chroma.sqlite3")

    db_file = next(
        (p for p in candidates if p.exists() and p.stat().st_size > 1_000_000), None
    )
    if db_file is None:
        print("[RAG] chroma_index not found — running without RAG.")
        return None

    collection = "benchmark_true_fresh_index_Filtered_Review_1"
    try:
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        cur.execute("SELECT id FROM collections WHERE name = ?", (collection,))
        exists = cur.fetchone() is not None
        conn.close()
    except Exception as exc:
        print(f"[RAG] Cannot check collection: {exc}")
        return None

    if not exists:
        print(f"[RAG] Collection {collection!r} not in {db_file.name} — skipping RAG.")
        return None

    try:
        from crewai_tools import JSONSearchTool
        from crewai_tools.tools.json_search_tool.json_search_tool import FixedJSONSearchToolSchema

        rag_config = {
            "embedding_model": {
                "provider": "sentence-transformer",
                "config": {"model_name": "BAAI/bge-small-en-v1.5"},
            }
        }
        t = JSONSearchTool(collection_name=collection, config=rag_config)
        t.args_schema = FixedJSONSearchToolSchema
        t.name = "search_historical_reviews"
        t.description = (
            "Semantic search over 1.8M historical Yelp reviews. "
            "Action Input MUST be JSON with key 'search_query'. "
            'Example: {"search_query": "Vietnamese pho quality Philadelphia"}. '
            "Use when the item summary is sparse and you need peer review context."
        )
        print(f"[RAG] search_historical_reviews loaded from {db_file.name}")
        return t
    except Exception as exc:
        print(f"[RAG] Failed to load tool: {exc}")
        return None


@CrewBase
class SimulationCrew():
    """Sequential crew for Yelp review prediction (Process.sequential).

    Three agents run one after the other:
      user_profiler → item_analyst → prediction_modeler

    Data is pre-fetched in CrewAISimulationAgent and passed as template variables.
    Agents receive compact summary strings — no tool calls needed inside the crew.
    """

    agents_config = '../../config/agents.yaml'
    tasks_config  = '../../config/tasks.yaml'

    @agent
    def user_profiler(self) -> Agent:
        return Agent(
            config=self.agents_config['user_profiler'],
            llm=_build_llm(),
            verbose=False,
            allow_delegation=False,
            max_iter=2,
        )

    @agent
    def item_analyst(self) -> Agent:
        tool = _rag_tool()
        return Agent(
            config=self.agents_config['item_analyst'],
            llm=_build_llm(),
            verbose=False,
            allow_delegation=False,
            max_iter=3 if tool else 2,
            tools=[tool] if tool else [],
        )

    @agent
    def prediction_modeler(self) -> Agent:
        return Agent(
            config=self.agents_config['prediction_modeler'],
            llm=_build_llm(),
            verbose=False,
            allow_delegation=False,
            max_iter=3,
        )

    @task
    def analyze_user_task(self) -> Task:
        return Task(config=self.tasks_config['analyze_user_task'])

    @task
    def analyze_item_task(self) -> Task:
        rag_on = os.environ.get("RAG_ENABLED", "0").strip() in ("1", "true", "True")
        key = "analyze_item_task_rag" if rag_on else "analyze_item_task"
        return Task(config=self.tasks_config[key])

    @task
    def predict_review_task(self) -> Task:
        return Task(config=self.tasks_config['predict_review_task'])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
