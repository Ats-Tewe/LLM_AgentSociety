# 🎓 學生專用：如何將你開發的 CrewAI 整合進 AgentSociety 官方 Simulator

為了讓大家專注在開發酷炫的 Multi-Agent，而不是跟系統底層打架，我們已經把最困難的「資料串接」與「系統橋接」打包好了！以下是你們開發與整合的標準流程：

---

## 🛠️ 第一階段：學生需要做什麼？

身為開發者，你們**只需要改動 3 個地方**，其他底層檔案（如 `CrewAISimulationAgent`, `serving_flow.py`, `interaction_tool_wrapper.py`）**請不要動**。

### 1. 設計你的 Agents (`config/agents.yaml`)
規劃你需要幾個 Agent 來完成這個預測任務。
- 給他們明確的 `role`, `goal`, `backstory`。
- 想想看：除了找資料的 Agent，是不是還需要一個「極端性格分析師」？或是「社群風向觀察家」？

### 2. 撰寫你的 Tasks (`config/tasks.yaml`)
這是最關鍵的一步。你需要定義每個 Agent 該做什麼。
- **針對負責調用 Tool 的 Agent (例如檢索員)**：
  強烈建議使用 **Few-Shot Prompting (給範例)** 的技巧，在 YAML 裡明確寫下他該怎麼用工具。例如：
  ```yaml
  Action: Interaction Tool Wrapper
  Action Input: {{"query_type": "user", "target_id": "{user_id}"}}
  ```
- **針對最後負責給出評分的 Agent**：
  你必須在 `expected_output` 嚴格要求他只輸出合法的 JSON，不要說廢話：
  ```yaml
  Your response must contain ONLY a valid JSON object in this exact format:
  {{"stars": 3.0, "review": "The review text..."}}
  ```

### 3. 組裝你的 Crew (`src/crews/simulation_crew.py`)
打開組裝廠，把你剛剛在 YAML 設計好的 Agent 建立出來。
- **唯一要注意的點**：負責找資料的那個 Agent，必須裝備上我們給你的專屬工具：
  ```python
  from src.tools.interaction_tool_wrapper import get_interaction_tool
  
  @agent
  def data_retriever(self) -> Agent:
      return Agent(
          config=self.agents_config['data_retriever'],
          tools=[get_interaction_tool()] # 👈 幫他把工具裝備上去
      )
  ```

### 4. 進階：若要修改 Flow 的注意事項 (`src/flows/serving_flow.py`)
你可以自由探索並修改了 Flow 裡的工作流，**但請絕對不要更改最後回傳的 State 字典鍵值名稱**！
- 底層的 Adapter 依賴著 `predicted_rating` 與 `generated_review` 這兩個隱形合約來跟大會系統溝通。
- 若你將變數改名（例如改成 `stars` 或 `comment`），外層會因為抓不到資料，直接送出系統預設值（4.0 星與 Good.），導致你前功盡棄。

---

## 🚀 第二階段：如何測試？

開發完成後，請用指令測試你的 Agent 表現如何！

- **免費/不花 Token 的結構測試 (Mock 模式)**:
  `uv run python run_simulator_test.py --mock`
- **真實 NVIDIA NIM LLM 推論測試**:
  `uv run python run_simulator_test.py`
- **正式丟進訓練集評分 (會花費較多時間)**:
  `uv run python evaluate_with_training_data.py`

---
<br>

# 💡 給課程助教/講師的優化建議 (如何讓這一切更簡單？)

如果要讓全班學生無痛上手，我強烈建議我們把當前的 Repo 整理成一個 **"Student Sandbox Template" (學生沙盒模板)**。具體做法如下：

### 1. 強調底層資料合約的重要性
學生容易不小心改破底層的 Flow 或 Tool 呼叫。請務必向學生宣導：
- **「輸出 State 字典的結構」** (`serving_flow.py` 的鍵值名稱)
- **「Interaction Tool 的 Import 方式」**
這兩者是不可妥協的資料合約，一旦改破就會導致 Simulator 取不到評分資料。

### 2. 提供 Base Crew 類別
目前學生在 `simulation_crew.py` 裡還是要做滿多繁瑣的 @agent, @task 裝飾器設定。我們可以寫一個 Base Class，自動遍歷 yaml 把 agent 造出來，學生只要負責挑誰要拿 Tool 就好。不過目前的 boilerplate code 還在可接受範圍內。

### 3. 提供預設防護網 (Sanitizer)
LLM 常常會輸出奇怪的 JSON（例如夾雜 ```json block 或者加上雙引號）。這部分我們已經在 `serving_flow.py` 的 `extract_json_from_output` 實作了很強大的 Regex 容錯捕捉了。請確保學生拿到的是**我們已經加上這個強大防護網的版本**

### 4. 建立「Prompt 優化排行榜」
既然架構已經統一，決定勝負的關鍵就在於 YAML 裡的 Prompting 功力。
可以舉辦小型 Leaderboard，看哪組同學在 `tasks.yaml` 中設計的防偏護欄 (Anti-bias instruction) 或角色扮演，能在 `test_review_subset.json` 拿到最高的 `overall_quality` 分數。
