from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types
import tools_client

# --- SETUP ---
retry_config = types.HttpRetryOptions(attempts=5)
VALID_ITEMS_STR = ", ".join(tools_client.database.get_all_item_names())

# --- WORKER AGENTS ---

strategist_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="strategist_agent",
    instruction=f"You are a strategist. Given a situation, create a dispatch plan using items from: [{VALID_ITEMS_STR}]. Suggest alternatives for invalid items."
)

# Escalation agent is rarely needed now as the tool handles it, but kept for edge cases
escalation_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="escalation_agent",
    instruction="Your only job is to call the `log_inventory_gap` tool.",
    tools=[tools_client.log_inventory_gap]
)

request_dispatcher_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="request_dispatcher_agent",
    instruction="""
    Your only job is to call the `request_relief` tool.
    Pass the Item Name, Quantity, and Location exactly.
    The tool handles partial stock automatically, so just report whatever message the tool returns (Success, Partial, or Failure).
    """,
    tools=[tools_client.request_relief]
)

item_finder_agent = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="item_finder_agent",
    instruction=f"""
    You are a database key finder.
    VALID KEYS: [{VALID_ITEMS_STR}]
    - Map user input (e.g. "med kits") to the closest VALID KEY (e.g. "medical_kits").
    - Output ONLY the key or "None".
    """
)

# --- ORCHESTRATOR ---

victim_orchestrator = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="victim_orchestrator",
    instruction=f"""
    You are the orchestrator for victim requests.

    **WORKFLOW:**
    1.  **Identify Intent:** 
        - Is this a follow-up? -> Execute using items from history.
        - Is this a new request? -> Proceed.

    2.  **Find Item Keys (Loop):** 
        - For EACH item requested, call `item_finder_agent` to get the official database key.

    3.  **Execute (Loop):**
        - For EACH valid key found (e.g., `medical_kits`), call `request_dispatcher_agent`.
        - **IMPORTANT:** Pass the requested QUANTITY and LOCATION.
        - If the tool returns "PARTIAL SUCCESS", report that clearly to the user (e.g., "We sent 10, but are missing 5").

    4.  **Summarize:** Provide a final summary confirming exactly what was dispatched.
    """,
    tools=[
        AgentTool(agent=strategist_agent),
        AgentTool(agent=escalation_agent),
        AgentTool(agent=request_dispatcher_agent),
        AgentTool(agent=item_finder_agent)
    ]
)