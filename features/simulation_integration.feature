Feature: CrewAI SimulationAgent Integration
  As a developer participating in the AgentSociety Challenge (Track 1)
  I want to integrate the core SimulationAgent with a loosely coupled CrewAI architecture
  So that I can maintain cleanly separated AI logic while meeting the simulator's format constraints.

  Scenario: Gateway handles incoming scene payload 
    Given the Simulator framework is loaded
    When the SimulationAgent receives a payload with User ID "U123" and Item ID "I456"
    Then the agent should initialize an InferenceState with the respective User ID and Item ID
    And it should invoke the Flow kickoff sequence

  Scenario: Flow routes data request dynamically to Crews
    Given the AgentSocietyServingFlow is running its user profile node
    When the flow needs user information
    Then it should trigger the Crew inference
    And the Crew should retrieve data via the InteractionToolWrapper

  Scenario: Adapter strictly complies with Track 1 evaluation standards
    Given the AgentSocietyServingFlow completes its execution
    When the terminal state returns a predicted_rating of 4.5 and generated_review of "Amazing experience!"
    Then the SimulationAgent adapter must return a dictionary containing stars and review
