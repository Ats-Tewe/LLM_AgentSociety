---
trigger: always_on
glob:
description:
---

**Rule:** 在撰寫 CrewAI 程式碼時，必須嚴格遵守 Agent 與 Task 分離的設計模式。Agent 的定義必須包含清晰且具體的 `role`（角色）、`goal`（目標）與 `backstory`（背景故事）；Task 則必須明確定義 `description`（任務描述）與 `expected_output`（預期輸出格式）。嚴禁將任務邏輯直接寫死在 Agent 的定義中。

#### 💡 實作規範 (Implementation Standard)
為了落實此原則，AI 代理在生成或修改 CrewAI 相關程式碼時，必須嚴格遵守以下 **YAML 優先 (YAML-First)** 的架構：

1. **配置分離 (Configuration Separation):**
   - **Agents:** 所有 Agent 的 `role`, `goal`, `backstory` 必須定義在 `config/agents.yaml` 檔案中。
   - **Tasks:** 所有 Task 的 `description`, `expected_output` 必須定義在 `config/tasks.yaml` 檔案中。
   - **變數替換:** 若有動態參數（如 `{topic}` 或 `{user_id}`），應在 YAML 中使用大括號標示，並在主程式呼叫 `kickoff(inputs=...)` 時傳入。

2. **程式碼編排 (Code Orchestration):**
   - Python 程式碼（如 `crew.py`）的職責僅限於「組裝」。
   - 必須使用 `@CrewBase` 裝飾器定義 Crew 類別。
   - 必須使用 `@agent` 與 `@task` 裝飾器來載入 YAML 設定並綁定 Tools（例如您的 RAG Tool），**禁止**在 Python 程式碼中硬編碼 (Hardcode) 任何 prompt 或字串內容。

#### ✅ 正確範例 (Agent 行為準則)
當我要求「新增一個負責分析 User 的 Agent 與 Task」時，你應該這樣修改檔案：

**1. `config/agents.yaml`**
```yaml
user_analyst:
  role: >
    資深使用者行為分析師
  goal: >
    深度解析使用者資料，找出潛在偏好與購買意圖
  backstory: >
    你擁有心理學與資料科學雙重背景，擅長從冷冰冰的 JSONL 數據中看出使用者的真實需求。
```

**2. `config/tasks.yaml`**
```yaml
analyze_user_task:
  description: >
    讀取目標使用者 (User ID: {user_id}) 在 subset_user.jsonl 中的紀錄，並分析其特徵。
  expected_output: >
    一段包含使用者輪廓、偏好特徵與潛在需求的分析報告，以 Markdown 格式呈現。
  agent: user_analyst
```

**3. `crew.py`**
```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

@CrewBase
class UserAnalysisCrew():
    """User Analysis Crew"""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def user_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['user_analyst'],
            verbose=True
            # 這裡可以掛載 RAG Tool 等工具
        )

    @task
    def analyze_user_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_user_task']
        )
```