from google.adk.agents import Agent # <--- CHANGED
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types
import tools_client

# --- SETUP ---
retry_config = types.HttpRetryOptions(attempts=5)
VALID_ITEMS_STR = ", ".join(tools_client.database.get_all_item_names())

# --- TIER 3: VICTIM WORKER AGENTS ---

strategist_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="strategist_agent",
    instruction=f"You are a strategist. Given a situation (e.g., '10 people injured'), create a dispatch plan using items from this list: [{VALID_ITEMS_STR}]. Suggest alternatives for invalid items."
)

escalation_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="escalation_agent",
    instruction="Your only job is to call the `log_inventory_gap` tool to report a missing item that a user requested.",
    tools=[tools_client.log_inventory_gap]
)

request_dispatcher_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="request_dispatcher_agent",
    instruction="Your only job is to call the `request_relief` tool for a single, valid inventory item with the exact parameters you receive.",
    tools=[tools_client.request_relief]
)

# --- SPECIALIST: ITEM FINDER ---
item_finder_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="item_finder_agent",
    instruction=f"""
    You are a database key finder. Your only job is to find the best match for a user's requested item from a predefined list.
    VALID INVENTORY KEYS: [{VALID_ITEMS_STR}]

    - Read the user's item request (e.g., "med kits", "water").
    - Find the closest matching key from the VALID INVENTORY KEYS list.
    - Your output MUST BE ONLY the single, exact, official key (e.g., `medical_kits`, `water_bottles`).
    - If no reasonable match can be found, you MUST respond with the word "None".
    """
)

# --- TIER 2: VICTIM ORCHESTRATOR ---
victim_orchestrator = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="victim_orchestrator",
    instruction=f"""
    You are the orchestrator for victim requests. You MUST follow this workflow:

    1.  **Analyze Request:** 
        - If situational (e.g., "we are injured"), delegate to `strategist_agent`.
        - If asking for a specific item, proceed to step 2.

    2.  **Find Item Key:** For EACH item requested, call `item_finder_agent` to get the official database key.

    3.  **Validate & Execute:**
        - If `item_finder_agent` returns a valid key (e.g., `medical_kits`), delegate to `request_dispatcher_agent` with that key.
        - If it returns "None" (e.g., for "ambulance"), delegate to `escalation_agent`.

    4.  **Summarize:** Provide a final summary of what was dispatched.
    """,
    tools=[
        AgentTool(agent=strategist_agent),
        AgentTool(agent=escalation_agent),
        AgentTool(agent=request_dispatcher_agent),
        AgentTool(agent=item_finder_agent)
    ]
)