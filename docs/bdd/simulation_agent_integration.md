# Feature: CrewAI SimulationAgent Integration

**User Story:**
As a developer participating in the AgentSociety Challenge (Track 1), 
I want to integrate the core `SimulationAgent` with a loosely coupled CrewAI architecture (using Crews and Flows) 
So that I can maintain cleanly separated AI logic (YAML definitions) while meeting the simulator's strict format constraints.

## Acceptance Criteria
- [ ] All agent definitions (`role`, `goal`, `backstory`) are strictly placed in `config/agents.yaml`.
- [ ] All task definitions (`description`, `expected_output`) are strictly placed in `config/tasks.yaml`.
- [ ] A CrewAI Flow (`AgentSocietyServingFlow`) orchestrates asynchronous inference logic (e.g. data fetching, analysis, and metric generation).
- [ ] The `SimulationAgent` adapter (`CrewAISimulationAgent`) receives the `self.task` payload and delegates execution purely to the CrewAI Flow.
- [ ] The Adapter correctly outputs `{"stars": float, "review": str}` as expected by the Simulator.
- [ ] A generic CrewAI `BaseTool` wrapper exposes the `interaction_tool` for safe dataset querying by agents.

## Scenarios

### Scenario: Gateway handles incoming scene payload 
Given the `Simulator` triggers the `CrewAISimulationAgent` with a scene payload containing a specific User ID and Item ID
When the `workflow()` method is executed
Then the agent should initialize an `InferenceState` with the respective User ID and Item ID
And it should invoke the `kickoff()` sequence for `AgentSocietyServingFlow`

### Scenario: Flow routes data request dynamically to Crews
Given the `AgentSocietyServingFlow` is running its `fetch_user_profile` node
When the flow tries to accumulate user information
Then it should load configurations from `config/agents.yaml` and `config/tasks.yaml` via a specific Crew formulation
And the spawned Crew must retrieve the correct dataset entries via the `InteractionToolWrapper`
And seamlessly deposit the textual profile into the Flow's runtime state

### Scenario: Adapter strictly complies with Track 1 evaluation standards
Given the `AgentSocietyServingFlow` has concluded all LLM reasoning steps
When the Flow kickoff completes and returns the terminal state
Then the state should present a finalized `predicted_rating` (float) and a `generated_review` (str)
And the `CrewAISimulationAgent` adapter must intercept this state and return a well-formed dictionary `{ "stars": <float>, "review": <str> }` to the executing Simulator
