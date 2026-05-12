# 🎓 For Students: How to Integrate Your CrewAI into AgentSociety Official Simulator

To let everyone focus on developing cool Multi-Agents without battling the bottom-layer system, we have packaged the most difficult parts: "data connection" and "system bridging"! Here is the standard procedure for your development and integration:

---

## 🛠️ Phase 1: What do students need to do?

As developers, you **only need to modify 3 places**, please **DO NOT touch** other bottom-layer files (such as `CrewAISimulationAgent`, `serving_flow.py`, `interaction_tool_wrapper.py`).

### 1. Design your Agents (`config/agents.yaml`)
Plan how many Agents you need to complete this prediction task.
- Give them clear `role`, `goal`, `backstory`.
- Think about it: besides a data retriever Agent, do you also need an "Extreme Personality Analyst"? Or a "Social Trend Observer"?

### 2. Write your Tasks (`config/tasks.yaml`)
This is the most critical step. You need to define what each Agent should do.
- **For the Agent using the Tool (e.g., Retriever)**:
  It is strongly recommended to use **Few-Shot Prompting** techniques, explicitly writing down how they should use the tools in YAML. For example:
  ```yaml
  Action: Interaction Tool Wrapper
  Action Input: {{"query_type": "user", "target_id": "{user_id}"}}
  ```
- **For the Agent responsible for providing the final rating**:
  You must strictly require them in the `expected_output` to outout ONLY a valid JSON, no nonsense:
  ```yaml
  Your response must contain ONLY a valid JSON object in this exact format:
  {{"stars": 3.0, "review": "The review text..."}}
  ```

### 3. Assemble your Crew (`src/crews/simulation_crew.py`)
Open the assembly factory, and instantiate the Agents you just designed in YAML.
- **The ONLY thing to note**: The Agent responsible for finding data MUST be equipped with the exclusive tool we give you:
  ```python
  from src.tools.interaction_tool_wrapper import get_interaction_tool
  
  @agent
  def data_retriever(self) -> Agent:
      return Agent(
          config=self.agents_config['data_retriever'],
          tools=[get_interaction_tool()] # 👈 Equip them with the tool
      )
  ```

### 4. Advanced: Notes on Modifying the Flow (`src/flows/serving_flow.py`)
You can freely explore and modify the workflow inside the Flow, **BUT PLEASE NEVER change the key names of the dictionary in the final returned State**!
- The bottom-layer Adapter relies on `predicted_rating` and `generated_review` as the two invisible contracts to communicate with the competition system.
- If you rename the variables (e.g., to `stars` or `comment`), the outer layer will fail to fetch the data and will directly send the system default values (4.0 stars and Good.), making all your previous efforts in vain.

---

## 🚀 Phase 2: How to test?

Once development is complete, please use commands to test your Agent's performance!

- **Free/No Token Structural Test (Mock Mode)**:
  `uv run python run_simulator_test.py --mock`
- **Real NVIDIA NIM LLM Inference Test**:
  `uv run python run_simulator_test.py`
- **Official Evaluation against Training Set (Takes more time)**:
  `uv run python evaluate_with_training_data.py`

---
<br>

# 💡 Optimization Suggestions for TAs/Instructors (How to make all this simpler?)

If we want the whole class to onboard painlessly, I strongly recommend we organize the current Repo into a **"Student Sandbox Template"**. Specific approaches are as follows:

### 1. Emphasize the importance of the bottom-layer data contract
Students might easily break the bottom-layer Flow or Tool calls accidentally. Please ensure to advocate to students:
- **"The structure of the output State dictionary"** (Key names in `serving_flow.py`)
- **"The import method of the Interaction Tool"**
These two are non-negotiable data contracts; once broken, the Simulator will fail to retrieve rating data.

### 2. Provide a Base Crew Class
Currently, students still need to do quite a bit of tedious `@agent`, `@task` decorator configuration in `simulation_crew.py`. We could write a Base Class that automatically iterates over YAML to create agents, and students would only be responsible for choosing who gets the Tool. However, the current boilerplate code is still within acceptable limits.

### 3. Provide Default Safety Nets (Sanitizer)
LLMs often output weird JSON (e.g., mixed with ```json block or adding double quotes). We've already implemented a very powerful Regex fault-tolerant capture within `extract_json_from_output` in `serving_flow.py`. Please make sure the students receive this **version where we've already added this powerful safety net**.

### 4. Establish a "Prompt Optimization Leaderboard"
Since the architecture is already unified, the key to winning lies in Prompting skills within YAML.
You can host a small Leaderboard to see which group of students can get the highest `overall_quality` score on `test_review_subset.json` by designing anti-bias instructions or roleplay in `tasks.yaml`.
