from google.adk.agents import Agent
from google.adk.tools import AgentTool
from .smart_model import SmartGemini # <--- USE CUSTOM MODEL
import tools_supervisor

# --- WORKERS ---

inventory_manager_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="inventory_manager_agent",
    instruction="Manage inventory.",
    tools=[
        tools_supervisor.admin_add_new_item, tools_supervisor.admin_delete_item,
        tools_supervisor.admin_restock_item, tools_supervisor.admin_batch_update_inventory,
        tools_supervisor.admin_view_full_inventory, tools_supervisor.admin_get_low_stock_report
    ]
)

approval_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="approval_agent",
    instruction="Handle approvals.",
    tools=[
        tools_supervisor.supervisor_view_pending_requests, tools_supervisor.supervisor_decide_request,
        tools_supervisor.supervisor_batch_decide_requests, tools_supervisor.supervisor_view_audit_log,
        tools_supervisor.supervisor_mark_action_taken
    ]
)

action_item_strategist = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="action_item_strategist",
    instruction="Analyze ACTION_REQUIRED tasks. Suggest next steps."
)

# --- ORCHESTRATOR ---
supervisor_orchestrator = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="supervisor_orchestrator",
    instruction="Delegate to inventory_manager, approval_agent, or action_item_strategist.",
    tools=[
        AgentTool(agent=inventory_manager_agent),
        AgentTool(agent=approval_agent),
        AgentTool(agent=action_item_strategist)
    ]
)