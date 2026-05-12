import os
import logging
from websocietysimulator import Simulator

# 載入我們的 CrewAI 轉接層
from crewai_simulation_agent import CrewAISimulationAgent

logging.basicConfig(level=logging.INFO)

# ======================================================================
# [第一步] 設定您的 LLM API Key
# ======================================================================
# ⚠️【重要】CrewAI 架構下，LLM 是「必須的」，但設定方式與官方不同：
#   - 官方寫法: simulator.set_llm(DeepseekLLM(api_key="..."))
#   - CrewAI 寫法: 透過「環境變數」提供 API Key，CrewAI 會自動抓取
#
# 請取消下方其中一行的註解，填入您的真實 API Key：
os.environ["OPENAI_API_KEY"] = "sk-your-openai-api-key"        # OpenAI
# os.environ["DEEPSEEK_API_KEY"] = "your-deepseek-key"         # DeepSeek
#
# 💡 您也可以在 config/agents.yaml 裡為每個 Agent 指定不同模型，
#    例如 llm: deepseek/deepseek-chat 或 llm: openai/gpt-4o

print("🚀 啟動 CrewAI 真實訓練集大規模評測")

# ======================================================================
# [第二步] 指向真實的龐大 Dataset 與任務路徑
# ======================================================================
# 💡 注意: 建議保留 cache=True，否則 16GB+ 的資料表會瞬間吃滿您的本機記憶體！
DATA_DIR = "path/to/your/dataset"        
TASK_DIR = "path/to/task_directory"      
GROUNDTRUTH_DIR = "path/to/groundtruth_directory" 

simulator = Simulator(data_dir=DATA_DIR, device="auto", cache=True)
simulator.set_task_and_groundtruth(task_dir=TASK_DIR, groundtruth_dir=GROUNDTRUTH_DIR)

# ======================================================================
# [第三步] 掛載轉接器 (不需要 simulator.set_llm()!)
# ======================================================================
simulator.set_agent(CrewAISimulationAgent)
# ⚠️ 不需要呼叫 simulator.set_llm(...)！
# 在 CrewAI 架構下，LLM 由 CrewAI Agent 內部自行管理，
# 而非由 Simulator 統一分發。API Key 已在第一步透過環境變數提供。

# ======================================================================
# [第四步] 啟動多執行緒全速評測  ⚡️
# ======================================================================
# 💡 注意: 同時併發多個 Flow 會以 N 倍的速度消耗您的 Token Rate Limit (TPM/RPM)，
# 如果遇到 HTTP 429 Too Many Requests 報錯，請把 max_workers 降低。
outputs = simulator.run_simulation(
    number_of_tasks=None,       # None 代表跑完資料夾內所有任務
    enable_threading=True,      # 開啟多執行緒並發 (CrewAI 原生完全支援 Threading!)
    max_workers=10              # 併發 10 個 CrewAI Flow 實例
)

# ======================================================================
# [第五步] 產生成績單
# ======================================================================
print("\n📊 呼叫官方評分系統 (simulator.evaluate())...")
evaluation_results = simulator.evaluate()

import json
print("\n💡 最終競賽衡量結果:")
print(json.dumps(evaluation_results, indent=2, ensure_ascii=False))
