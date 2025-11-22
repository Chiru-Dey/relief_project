from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types
import tools_client

# --- SETUP ---
retry_config = types.HttpRetryOptions(attempts=5)
VALID_ITEMS_STR = ", ".join(tools_client.database.get_all_item_names())

# --- TIER 3: WORKER AGENTS ---

strategist_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="strategist_agent",
    instruction=f"""
    You are a strategist. Your job is to interpret HIGH-LEVEL descriptions of disasters (e.g. "Earthquake", "Flooding", "Many injured").
    VALID INVENTORY: [{VALID_ITEMS_STR}]. 
    
    **NEGATIVE CONSTRAINTS (CRITICAL):**
    - DO NOT create a plan if the input is just a location name (e.g., "in Leh", "at the hospital").
    - DO NOT create a plan if the input is a simple confirmation (e.g., "yes", "okay").
    - In those cases, reply with "N/A".
    
    If valid trigger, create a dispatch plan.
    """
)

escalation_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="escalation_agent",
    instruction="Call `log_inventory_gap` for items not in inventory.",
    tools=[tools_client.log_inventory_gap]
)

request_dispatcher_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="request_dispatcher_agent",
    instruction="Call `request_relief` for a SINGLE item type. Do not combine items.",
    tools=[tools_client.request_relief]
)

item_finder_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="item_finder_agent",
    instruction=f"""
    Database key finder.
    VALID KEYS: [{VALID_ITEMS_STR}]
    - Input: User request (e.g. "med kits").
    - Output: Exact key (e.g. "medical_kits") or "None".
    """
)

# --- TIER 2: VICTIM ORCHESTRATOR ---
victim_orchestrator = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="victim_orchestrator",
    instruction=f"""
    You are the orchestrator for victim requests.
    
    **STEP 0: CHECK CONTEXT (HIGHEST PRIORITY)**
    Look at the previous turn in the conversation history.
    - Did you just ask the user for a location?
    - If YES, and the user just provided a location (e.g., "at leh"), **STOP ANALYSIS**.
    - **IMMEDIATELY** take the ITEMS from the previous turn and the LOCATION from this turn, and jump to Step 3 (Execute).
    - DO NOT call the strategist.
    
    **STEP 1: ANALYZE NEW REQUEST**
    - If this is a brand new request:
      - Situational ("help, fire")? -> `strategist_agent`.
      - Specific items ("send water")? -> Proceed.

    **STEP 2: FIND KEYS**
    - For each item, call `item_finder_agent`.

    **STEP 3: EXECUTE (Dispatch Loop)**
    - For EACH valid item (found in history or current turn), call `request_dispatcher_agent`.
    - Pass: Item Key, Quantity, Location.
    - **Example:** "Dispatching 5 tents to Leh... Dispatching 6 water_bottles to Leh..."

    **STEP 4: SUMMARIZE**
    - Report the specific results returned by the dispatcher tools.
    """,
    tools=[
        AgentTool(agent=strategist_agent),
        AgentTool(agent=escalation_agent),
        AgentTool(agent=request_dispatcher_agent),
        AgentTool(agent=item_finder_agent)
    ]
)