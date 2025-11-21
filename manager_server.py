import os
import uvicorn
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool # <--- FIXED
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.google_llm import Gemini
from google.genai import types
from dotenv import load_dotenv

import database
import tools_client
import tools_supervisor

load_dotenv()

if "GOOGLE_API_KEY" not in os.environ:
    raise ValueError("GOOGLE_API_KEY not found")

retry_config = types.HttpRetryOptions(attempts=3)

database.init_db()

# --- 1. THE TRIAGE AGENT ---
triage_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="triage_agent",
    instruction="""
    Analyze the user's request. Your only job is to classify the request.
    - If the user explicitly mentions "supervisor", "manual approval", "human", or similar, you MUST respond with the single word: MANUAL.
    - For all other standard requests, you MUST respond with the single word: AUTO.
    Do not add any other text or explanation.
    """
)

# --- 2. THE MAIN MANAGER AGENT ---
manager_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="relief_manager",
    description="Central Disaster Relief Database & Logistics Hub.",
    instruction="""
    You are the Central Relief Manager. You have two main jobs: handling supervisor commands and processing relief requests.

    **For Supervisor Commands:**
    If the request is from a supervisor (e.g., 'approve', 'restock', 'audit'), use the appropriate supervisor or admin tool directly.

    **For Relief Requests (from victims):**
    You MUST follow this two-step process:
    1.  **TRIAGE:** First, call the `triage_agent` tool with the full user request to classify it as 'AUTO' or 'MANUAL'.
    2.  **EXECUTE:**
        - If the triage result is 'MANUAL', call the `request_relief` tool with `force_manual_approval=True`.
        - If the triage result is 'AUTO', call the `request_relief` tool with `force_manual_approval=False`.
    """,
    tools=[
        AgentTool(agent=triage_agent),
        
        # Client Tools
        tools_client.check_inventory,
        tools_client.request_relief,
        tools_client.check_request_status,
        
        # Supervisor Tools
        tools_supervisor.supervisor_view_pending_requests,
        tools_supervisor.supervisor_decide_request,
        tools_supervisor.supervisor_batch_decide_requests,
        tools_supervisor.supervisor_view_audit_log,
        
        tools_supervisor.admin_view_full_inventory,
        tools_supervisor.admin_restock_item,
        tools_supervisor.admin_add_new_item,
        tools_supervisor.admin_delete_item,
        tools_supervisor.admin_get_low_stock_report,
        tools_supervisor.admin_batch_update_inventory
    ]
)

app = to_a2a(manager_agent, port=8001)

if __name__ == "__main__":
    uvicorn.run("manager_server:app", host="0.0.0.0", port=8001, reload=True)