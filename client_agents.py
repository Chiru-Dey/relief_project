import asyncio
import os
import base64
from dotenv import load_dotenv

# --- ADK IMPORTS ---
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# --- GLOBALS ---
VICTIM_RUNNER = None
SUPERVISOR_RUNNER = None
SESSION_SERVICE = InMemorySessionService()

def initialize_adk_agents():
    """Initializes both Victim and Supervisor ADK Agents."""
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY not found.")

    retry_config = types.HttpRetryOptions(attempts=3)
    
    proxy_vic = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    proxy_sup = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")

    valid_items = "water_bottles, food_packs, medical_kits, blankets, batteries"

    # Victim Agent
    victim_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="victim_support_flask",
        instruction=f"Victim Support. Items: [{valid_items}]. Map generic terms. Delegate to 'relief_manager'.",
        sub_agents=[proxy_vic]
    )
    VICTIM_RUNNER = Runner(agent=victim_agent, app_name="victim_frontend", session_service=SESSION_SERVICE)
    
    # --- 🔥 NEW, STRICT SUPERVISOR INSTRUCTIONS ---
    supervisor_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="supervisor_flask",
        instruction=f"""
        You are a Relief Operation Supervisor. Your job is to manage inventory and approvals by delegating tasks to your sub-agent, 'relief_manager'.

        CRITICAL WORKFLOW FOR BATCH OPERATIONS (e.g., "add 7 items"):
        1.  **Acknowledge and Gather:** If the user's request is vague (like "add 7 items"), you MUST ask for the specific names and quantities for each item.
        2.  **Construct JSON:** Once you have the list of items and quantities, you MUST construct a single, valid JSON dictionary string. The keys must be the EXACT item names (e.g., "water_bottles") and the values must be integers.
            - Correct Example: '{{"water_bottles": 50, "tents": 20}}'
            - Incorrect: 'water_bottles: 50, tents: 20' (This is not valid JSON)
        3.  **Execute Batch Tool:** You MUST then ask 'relief_manager' to call the `admin_batch_update_inventory` tool, passing the complete JSON string you created as the `updates_json` argument.
        4.  **Confirm:** Relay the success or failure message from the tool call back to the user.

        - For single-item tasks (e.g., "approve request 5"), you can call the specific tool directly via 'relief_manager'.
        - ALWAYS use your tools. Do not hallucinate actions.
        """,
        sub_agents=[proxy_sup]
    )
    SUPERVISOR_RUNNER = Runner(agent=supervisor_agent, app_name="supervisor_frontend", session_service=SESSION_SERVICE)
    
    print("✅ ADK Agents Initialized with Strict Workflow.")


# --- ASYNC HELPER FOR FLASK ---
async def run_agent_query(runner, user_id, session_id, message):
    """A self-contained async function to run the agent."""
    try:
        await runner.session_service.create_session(app_name=runner.app_name, user_id=user_id, session_id=session_id)
    except Exception:
        pass

    final_response = "Sorry, an agent error occurred."
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
            if event.is_final_response() and event.content:
                final_response = event.content.parts[0].text
    except Exception as e:
        final_response = f"Agent Error: {e}"
        print(f"ERROR in run_agent_query: {e}")
    
    return final_response