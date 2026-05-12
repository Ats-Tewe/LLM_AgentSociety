import json
import os
import re

from pydantic import BaseModel
from crewai.flow.flow import Flow, listen, start

from src.crews.simulation_crew import SimulationCrew


def _clamp_stars(value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 4.0
    return max(1.0, min(5.0, v))


def extract_json_from_output(raw_output: str) -> dict:
    """Extract a {stars, review} dict from a noisy LLM output."""
    text = str(raw_output).strip()
    text = text.replace("{{", "{").replace("}}", "}")

    match = re.search(r'\{[^{}]*"stars"[^{}]*"review"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    match = re.search(
        r'\{[^{}]*"predicted_rating"[^{}]*"generated_review"[^{}]*\}', text, re.DOTALL
    )
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    star_match = re.search(r"(\d+\.?\d*)\s*(?:stars?|分|顆星)", text, re.IGNORECASE)
    rating = float(star_match.group(1)) if star_match else 4.0
    return {"stars": rating, "review": text}


class InferenceState(BaseModel):
    # Input fields — populated by CrewAISimulationAgent before the flow starts
    user_id:         str   = ""
    item_id:         str   = ""
    user_summary:    str   = ""
    item_summary:    str   = ""
    history_summary: str   = ""
    fallback_rating: float = 4.0
    # Output fields — written by the crew
    predicted_rating: float = 0.0
    generated_review: str   = ""


def _pick_crew(inputs: dict):
    """Instantiate the correct crew based on CREWAI_PROCESS_MODE env var."""
    mode = os.environ.get("CREWAI_PROCESS_MODE", "sequential").strip().lower()
    if mode == "collaborative":
        from src.crews.collaborative_crew import CollaborativeCrew
        return CollaborativeCrew().crew()
    if mode == "hierarchical":
        from src.crews.hierarchical_crew import HierarchicalCrew
        return HierarchicalCrew().crew()
    return SimulationCrew().crew()


class AgentSocietyServingFlow(Flow[InferenceState]):
    @start()
    def init_request(self) -> None:
        pass

    @listen(init_request)
    def trigger_crew_inference(self) -> dict:
        inputs = {
            "user_id":         self.state.user_id,
            "item_id":         self.state.item_id,
            "user_summary":    self.state.user_summary,
            "item_summary":    self.state.item_summary,
            "history_summary": self.state.history_summary,
            "fallback_rating": f"{self.state.fallback_rating:.2f}",
        }

        try:
            result = _pick_crew(inputs).kickoff(inputs=inputs)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Crew execution failed, using fallback: {e}")
            self.state.predicted_rating = _clamp_stars(self.state.fallback_rating)
            self.state.generated_review = "Crew execution failed; falling back to historical average."
            return self.state.model_dump()

        try:
            if getattr(result, "pydantic", None):
                data = result.pydantic.model_dump()
            else:
                data = extract_json_from_output(result.raw)

            stars_value = data.get("stars", data.get("predicted_rating"))
            if stars_value is None:
                stars_value = self.state.fallback_rating
            self.state.predicted_rating = _clamp_stars(stars_value)

            review_value = data.get("review") or data.get("generated_review") or ""
            self.state.generated_review = str(review_value).strip() or "No review text produced."
        except Exception:
            self.state.predicted_rating = _clamp_stars(self.state.fallback_rating)
            self.state.generated_review = str(getattr(result, "raw", ""))[:1000] or "No review text produced."

        return self.state.model_dump()
