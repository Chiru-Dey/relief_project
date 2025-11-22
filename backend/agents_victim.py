from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types
import tools_client # Server-side tool import

retry_config = types.HttpRetryOptions(attempts=3)
# The Server has access to the database to fetch valid items
VALID_ITEMS_STR = ", ".join(tools_client.database.get_all_item_names())

# --- WORKER 1: THE STRATEGIST (Planner) ---
strategist_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="strategist_agent",
    instruction=f"""
    You are the Disaster Relief Strategist.
    VALID INVENTORY: [{VALID_ITEMS_STR}]
    
    Your Job:
    1. Analyze the situation (e.g. "10 injured").
    2. Create a plan using ONLY valid inventory items.
    3. If items are missing (e.g. "bandages"), suggest valid alternatives (e.g. "medical_kits").
    4. Output a clear list of actions for the dispatcher.
    """
)

# --- WORKER 2: THE ESCALATOR (Alerts) ---
escalation_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="escalation_agent",
    instruction="Call `log_inventory_gap` when a user requests an item we do not carry (e.g. 'ambulance').",
    tools=[tools_client.log_inventory_gap]
)

# --- WORKER 3: THE DISPATCHER (Doer) ---
request_dispatcher_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="request_dispatcher_agent",
    instruction="Call `request_relief` for specific items and quantities as directed.",
    tools=[tools_client.request_relief]
)

# --- THE ORCHESTRATOR (Manager of this Domain) ---
victim_orchestrator = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="victim_orchestrator",
    instruction=f"""
    You are an orchestrator for victim requests.
    VALID INVENTORY: [{VALID_ITEMS_STR}]

    1.  **Analyze:**
        - Use `strategist_agent` for complex plans (e.g. "we are injured").
        - Use `escalation_agent` for invalid items.
    2.  **Execute:** 
        - Use `request_dispatcher_agent` to dispatch valid items.
    3.  **CONFIRMATION (CRITICAL):** 
        - Do NOT say "I have initiated a plan".
        - You MUST report the exact result of the dispatch. 
        - Example: "Confirmed. I have dispatched 10 medical_kits to Sector 9 (Request ID 55). I have also dispatched 20 blankets."
        - If the tool returns a Request ID, you MUST share it with the user.
    """,
    tools=[
        AgentTool(agent=strategist_agent),
        AgentTool(agent=escalation_agent),
        AgentTool(agent=request_dispatcher_agent)
    ]
)