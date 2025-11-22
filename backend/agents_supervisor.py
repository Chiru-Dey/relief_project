from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types
import tools_supervisor

retry_config = types.HttpRetryOptions(attempts=3)

# --- WORKER 1: INVENTORY MANAGER ---
inventory_manager_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="inventory_manager_agent",
    instruction="Manage inventory database (Add, Delete, Restock, View).",
    tools=[
        tools_supervisor.admin_add_new_item,
        tools_supervisor.admin_delete_item,
        tools_supervisor.admin_restock_item,
        tools_supervisor.admin_batch_update_inventory,
        tools_supervisor.admin_view_full_inventory,
        tools_supervisor.admin_get_low_stock_report
    ]
)

# --- WORKER 2: APPROVAL MANAGER ---
approval_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="approval_agent",
    instruction="Handle request queue (View pending, Approve, Reject, Audit).",
    tools=[
        tools_supervisor.supervisor_view_pending_requests,
        tools_supervisor.supervisor_decide_request,
        tools_supervisor.supervisor_batch_decide_requests,
        tools_supervisor.supervisor_view_audit_log,
        tools_supervisor.supervisor_mark_action_taken
    ]
)

# --- WORKER 3: ACTION STRATEGIST ---
action_item_strategist = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="action_item_strategist",
    instruction="Analyze 'ACTION_REQUIRED' alerts and suggest the correct admin command to resolve them."
)

# --- THE ORCHESTRATOR ---
supervisor_orchestrator = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="supervisor_orchestrator",
    instruction="""
    You manage all Supervisor Commands. Delegate to your team:
    - Inventory tasks -> `inventory_manager_agent`
    - Approval tasks -> `approval_agent`
    - Alert resolution strategy -> `action_item_strategist`
    """,
    tools=[
        AgentTool(agent=inventory_manager_agent),
        AgentTool(agent=approval_agent),
        AgentTool(agent=action_item_strategist)
    ]
)