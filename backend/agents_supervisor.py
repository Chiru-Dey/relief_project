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
    instruction="Handle approvals and resolve ACTION_REQUIRED tasks with automatic restocking.",
    tools=[
        tools_supervisor.supervisor_view_pending_requests, tools_supervisor.supervisor_decide_request,
        tools_supervisor.supervisor_batch_decide_requests, tools_supervisor.supervisor_view_audit_log,
        tools_supervisor.supervisor_mark_action_taken, tools_supervisor.supervisor_resolve_action_required
    ]
)

action_item_strategist = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="action_item_strategist",
    instruction="Analyze ACTION_REQUIRED tasks and resolve them by restocking with appropriate buffer.",
    tools=[
        tools_supervisor.supervisor_view_pending_requests,
        tools_supervisor.supervisor_resolve_action_required,
        tools_supervisor.admin_view_full_inventory
    ]
)

# --- ORCHESTRATOR ---
supervisor_orchestrator = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="supervisor_orchestrator",
    instruction="""Delegate tasks appropriately:
    - For inventory operations (add, delete, restock, view): Use inventory_manager_agent
    - For approvals/rejections of pending requests: Use approval_agent
    - For 'resolve', 'fix', or handling ACTION_REQUIRED tasks: Use action_item_strategist
    
    When user says 'resolve' or 'fix' an action item, delegate to action_item_strategist 
    which will automatically restock with buffer and dispatch to victims.""",
    tools=[
        AgentTool(agent=inventory_manager_agent),
        AgentTool(agent=approval_agent),
        AgentTool(agent=action_item_strategist)
    ]
)