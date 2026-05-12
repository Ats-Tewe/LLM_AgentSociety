from crewai.tools import tool

# 單例全域變數：負責盛裝執行期 Simulator.py 動態配給的 interaction_tool
_GLOBAL_INTERACTION_TOOL = None

def inject_simulator_tool(tool_instance):
    global _GLOBAL_INTERACTION_TOOL
    _GLOBAL_INTERACTION_TOOL = tool_instance

@tool("Interaction Tool Wrapper")
def interaction_tool_wrapper(query_type: str, target_id: str) -> str:
    """
    能調用 AgentSociety 提供的本地檢索工具查詢歷史數據。
    query_type 必須是下列之一："user", "item", "review_by_user", "review_by_item"。
    target_id 是對應的 user_id 或 item_id。
    """
    if _GLOBAL_INTERACTION_TOOL is None:
        return "Error: InteractionTool has not been injected by the Simulator."
        
    try:
        if query_type == "user":
            return str(_GLOBAL_INTERACTION_TOOL.get_user(user_id=target_id))
        elif query_type == "item":
            return str(_GLOBAL_INTERACTION_TOOL.get_item(item_id=target_id))
        elif query_type == "review_by_user":
            return str(_GLOBAL_INTERACTION_TOOL.get_reviews(user_id=target_id))
        elif query_type == "review_by_item":
            return str(_GLOBAL_INTERACTION_TOOL.get_reviews(item_id=target_id))
        else:
            return "Error: Unknown query_type. Use exactly 'user', 'item', 'review_by_user' or 'review_by_item'."
    except Exception as e:
        return f"Error occurred during interaction_tool query: {str(e)}"

def get_interaction_tool():
    """回傳工具實例供 Crew Agent 使用"""
    return interaction_tool_wrapper
