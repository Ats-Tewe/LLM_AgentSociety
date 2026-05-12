---
trigger: always_on
glob:
description:
---

**Rule:** 本專案全面採用 Astral `uv` 作為唯一的 Python 環境、專案與套件管理工具。Agent 在進行任何依賴解析、套件安裝、虛擬環境建立或腳本執行時，必須嚴格使用 `uv` 的原生指令。**絕對禁止**在終端機或自動化腳本中使用傳統的 `pip`、`poetry`、`conda` 或 `pipenv`。

#### 💡 實作規範 (Implementation Standard)
為了維持專案依賴的純淨與高速解析，AI 代理在執行環境操作時，必須遵守以下指令對應關係：

1. **套件安裝與移除 (Dependency Management):**
   * ❌ **禁止：** `pip install crewai`, `poetry add chromadb`
   * ✅ **必須：** `uv add crewai chromadb` (新增依賴至 `pyproject.toml`)
   * ✅ **必須：** `uv remove [package_name]` (移除依賴)
   * 若僅供開發環境測試使用（例如 `pytest`, `ruff`），必須加上 `--dev` 標籤：`uv add --dev pytest`

2. **執行 Python 腳本 (Execution):**
   * ❌ **禁止：** 手動 `source venv/bin/activate` 然後執行 `python main.py`
   * ✅ **必須：** `uv run main.py` (讓 `uv` 自動處理虛擬環境與路徑)
   * 當需要執行 CrewAI 的啟動指令時，一律使用 `uv run crewai run`。

3. **環境同步與鎖定 (Sync & Lock):**
   * 當讀取到 `pyproject.toml` 有變更，或是切換 Git 分支後，若需更新環境，請執行 `uv sync` 來確保環境與 `uv.lock` 狀態一致。
   * 嚴禁手動生成或修改 `requirements.txt`，所有依賴皆以 `pyproject.toml` 與 `uv.lock` 為唯一真理 (Single Source of Truth)。

4. **隔離工具執行 (Tool Running):**
   * 若需執行不需要安裝到專案依賴中的獨立工具（例如一次性的資料庫檢查腳本或專案模板生成），請使用 `uvx [tool_name]`（等同於 `uv tool run`）。

#### ⚠️ 攔截與警告機制 (Guardrail)
如果在工作流 (Workflow) 或對話中，使用者要求「幫我 pip install 某個套件」，Agent 必須主動糾正使用者，並自動將指令轉換為對應的 `uv add` 指令後再執行。

