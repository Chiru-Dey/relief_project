from google.adk.agents import Agent # <--- CHANGED
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types
import tools_supervisor

# --- SETUP ---
retry_config = types.HttpRetryOptions(attempts=5)

# --- TIER 3: SUPERVISOR WORKER AGENTS ---

inventory_manager_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="inventory_manager_agent",
    instruction="You manage inventory. Use your tools to add, delete, restock, or view items.",
    tools=[
        tools_supervisor.admin_add_new_item,
        tools_supervisor.admin_delete_item,
        tools_supervisor.admin_restock_item,
        tools_supervisor.admin_batch_update_inventory,
        tools_supervisor.admin_view_full_inventory,
        tools_supervisor.admin_get_low_stock_report
    ]
)

approval_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="approval_agent",
    instruction="You handle approvals. Use your tools to view pending requests, approve/reject them, or view the audit log.",
    tools=[
        tools_supervisor.supervisor_view_pending_requests,
        tools_supervisor.supervisor_decide_request,
        tools_supervisor.supervisor_batch_decide_requests,
        tools_supervisor.supervisor_view_audit_log,
        tools_supervisor.supervisor_mark_action_taken
    ]
)

action_item_strategist = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="action_item_strategist",
    instruction="""
    You analyze ACTION_REQUIRED tasks and create a plan for the supervisor.
    Read the task notes and suggest the next logical step.
    """
)

# --- TIER 2: SUPERVISOR ORCHESTRATOR ---
supervisor_orchestrator = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="supervisor_orchestrator",
    instruction="""
    You are an orchestrator for supervisor commands. Delegate to the correct specialist:
    - **Inventory** -> `inventory_manager_agent`.
    - **Approvals** -> `approval_agent`.
    - **Action Items** -> `action_item_strategist`.
    """,
    tools=[
        AgentTool(agent=inventory_manager_agent),
        AgentTool(agent=approval_agent),
        AgentTool(agent=action_item_strategist)
    ]
)