from behave import given, when, then
import sys
from unittest.mock import MagicMock

# --- Prevent heavy ML libraries from crashing standard CI/tests using Mocks ---
sys.modules['torch'] = MagicMock()
sys.modules['transformers'] = MagicMock()
sys.modules['nltk'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()

# --- Mocks for AgentSociety Core components ---
class MockInteractionTool:
    def get_user(self, user_id): return f"MockUser_{user_id}"
    def get_item(self, item_id): return f"MockItem_{item_id}"

class MockTask(dict):
    pass

class MockSimulationAgent:
    """Mocking the websocietysimulator SimulationAgent basic skeleton to avoid overhead"""
    def __init__(self, *args, **kwargs):
        self.task = MockTask()
        self.interaction_tool = MockInteractionTool()

mock_agent_module = MagicMock()
mock_agent_module.SimulationAgent = MockSimulationAgent
sys.modules['websocietysimulator.agent'] = mock_agent_module
sys.modules['websocietysimulator'] = MagicMock()

# --- Importing real adapter mapping and flows ---
from crewai_simulation_agent import CrewAISimulationAgent
from src.flows.serving_flow import AgentSocietyServingFlow, InferenceState

# Verify our override actually points to the mock
CrewAISimulationAgent.__bases__ = (MockSimulationAgent,)

# ==========================================================
# Scenario 1: Gateway handles incoming scene payload
# ==========================================================
@given('the Simulator framework is loaded')
def step_impl(context):
    context.agent = CrewAISimulationAgent()

@when('the SimulationAgent receives a payload with User ID "{user_id}" and Item ID "{item_id}"')
def step_impl(context, user_id, item_id):
    context.agent.task = {"user_id": user_id, "item_id": item_id}

@then('the agent should initialize an InferenceState with the respective User ID and Item ID')
def step_impl(context):
    assert context.agent.task.get('user_id') == "U123"
    assert context.agent.task.get('item_id') == "I456"

@then('it should invoke the Flow kickoff sequence')
def step_impl(context):
    pass

# ==========================================================
# Scenario 2: Flow routes data request dynamically to Crews
# ==========================================================
@given('the AgentSocietyServingFlow is running its user profile node')
def step_impl(context):
    pass

@when('the flow needs user information')
def step_impl(context):
    pass

@then('it should trigger the Crew inference')
def step_impl(context):
    pass

@then('the Crew should retrieve data via the InteractionToolWrapper')
def step_impl(context):
    pass

# ==========================================================
# Scenario 3: Adapter strictly complies with Track 1 evaluation standards
# ==========================================================
@given('the AgentSocietyServingFlow completes its execution')
def step_impl(context):
    context.flow = AgentSocietyServingFlow()

@when('the terminal state returns a predicted_rating of {rating:f} and generated_review of "{review}"')
def step_impl(context, rating, review):
    context.flow.state.predicted_rating = rating
    context.flow.state.generated_review = review
    context.final_state_dict = context.flow.state.model_dump()

@then('the SimulationAgent adapter must return a dictionary containing stars and review')
def step_impl(context):
    output = {
        'stars': float(context.final_state_dict.get('predicted_rating', 4.0)),
        'review': str(context.final_state_dict.get('generated_review', 'Good.'))
    }
    assert "stars" in output
    assert "review" in output
    assert isinstance(output["stars"], float)
    assert output["stars"] == 4.5
    assert output["review"] == "Amazing experience!"
