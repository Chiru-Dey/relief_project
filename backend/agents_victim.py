from google.adk.agents import Agent
from google.adk.tools import AgentTool
from .smart_model import SmartGemini # <--- USE CUSTOM MODEL
import tools_client

# --- SETUP ---
# We don't need retry_config here anymore, SmartGemini handles it
VALID_ITEMS_STR = ", ".join(tools_client.database.get_all_item_names())

# --- WORKER AGENTS ---

strategist_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="strategist_agent",
    instruction=f"Strategist. Plan using: [{VALID_ITEMS_STR}]."
)

escalation_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="escalation_agent",
    instruction="Call `log_inventory_gap`.",
    tools=[tools_client.log_inventory_gap]
)

request_dispatcher_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="request_dispatcher_agent",
    instruction="Call `request_relief`.",
    tools=[tools_client.request_relief]
)

item_finder_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="item_finder_agent",
    instruction=f"Find key in [{VALID_ITEMS_STR}]. Return Key or 'None'."
)

# --- ORCHESTRATOR ---

victim_orchestrator = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="victim_orchestrator",
    instruction=f"""
    Orchestrator for victims.
    1. Check Context: If providing location/confirmation, EXECUTE history.
    2. Find Keys: Use `item_finder_agent`.
    3. Execute: Call `request_dispatcher_agent` (Pass Key, Qty, Loc).
    4. Summarize.
    """,
    tools=[
        AgentTool(agent=strategist_agent),
        AgentTool(agent=escalation_agent),
        AgentTool(agent=request_dispatcher_agent),
        AgentTool(agent=item_finder_agent)
    ]
)