# CLAUDE.md — AgentSocietyChallenge_w_CrewAI

## Git 工作流程

### 核心原則
**`main` 只接受 PR merge，不直接 commit。**

所有開發工作在 Claude Code 建立的 worktree 分支上進行，完成後透過 PR merge 回 `main`。

---

### Session 開始時

```bash
# 1. 拉取遠端最新的 main
git -C /Users/jack.ho/WorkSpace/LLM_APP_2026/AgentSocietyChallenge pull origin main

# 2. 將 worktree 分支 rebase 到最新 main 上
git -C <worktree路徑> rebase main
```

> 不管在哪裡修改了本地 `main`，session 開始前都執行這兩步，確保 worktree 分支以最新 `main` 為基底。

---

### Session 進行中

- 所有 commit 只在 **worktree 分支**上進行
- 不直接 commit 到 `main`

---

### Session 結束時

```
Push worktree 分支 → 開 PR → merge 進 main → 本地 pull main
```

---

### 如果不得不直接修改本地 main

1. 將改動 commit 到 `main`
2. 下次 session 開始前執行 `pull` + `rebase`（同「Session 開始時」步驟）
3. 回歸正常流程

---

## 專案結構

| 路徑 | 說明 |
|------|------|
| `websocietysimulator/` | 競賽核心框架（不可修改） |
| `src/crews/simulation_crew.py` | CrewAI Crew 組裝（可修改） |
| `config/agents.yaml` | Agent 角色定義（可修改） |
| `config/tasks.yaml` | Task 指令設計（可修改） |
| `crewai_simulation_agent.py` | 官方 Simulator ↔ CrewAI 轉接器（不可修改） |
| `src/flows/serving_flow.py` | Flow 與 JSON 解析（不可修改） |

## 資料合約

- Track 1 輸出格式：`{"stars": float, "review": str}`
- Pydantic State 欄位：`predicted_rating`、`generated_review`（名稱不可改）
- InteractionTool 查詢類型：`"user"`, `"item"`, `"review_by_user"`, `"review_by_item"`

## 環境管理：永遠使用 uv

本專案**只使用 uv** 管理環境，禁止使用 `pip install`、`poetry`、`conda` 或直接呼叫系統 `python3`。

```bash
# ✅ 正確
uv run python run_pipeline.py
uv sync
uv add <package>

# ❌ 禁止
python3 run_pipeline.py
pip install <package>
```

所有 `.py` 腳本已內建守衛，直接用系統 Python 執行會立即中止並提示正確用法。

## 執行測試

```bash
# Mock 模式（零成本結構驗證）
uv run python run_pipeline.py --mock

# 真實 LLM，全部任務
uv run python run_pipeline.py

# 2-worker threading
uv run python run_pipeline.py --threads 2

# 只跑 1 筆（smoke test，等同 run_nvidia_test.py）
uv run python run_pipeline.py --tasks 1

# 自訂逾時（秒）
uv run python run_pipeline.py --timeout 120
```
