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
    
    # Create separate proxy instances to avoid parent-child conflicts
    proxy_vic = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    proxy_sup = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")

    valid_items = "water_bottles, food_packs, medical_kits, blankets, batteries"

    # --- 🔥 NEW, STRICT INSTRUCTIONS for Victim Agent ---
    victim_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="victim_support_flask",
        instruction=f"""
        You are a Disaster Relief Support agent. Your goal is to process relief requests accurately.

        CRITICAL WORKFLOW:
        1.  **Identify Items:** Identify all items the user asks for (e.g., "bandages", "batteries").
        2.  **Verify Inventory:** For EACH item, you MUST first call the `check_inventory` tool via the 'relief_manager'.
            - If the tool returns an ERROR that the item is not found, you MUST inform the user and list the available items. DO NOT proceed with the invalid item.
            - Example: If user asks for "bandages", the tool will return "ERROR: Item 'bandages' not found...". You must tell the user "Sorry, we don't have bandages, but we do have medical_kits." and ask if they want that instead.
        3.  **Confirm Location:** If the location is not clear from the conversation, you must ask for it.
        4.  **Dispatch SEPARATELY:** For EACH valid and available item, you MUST make a separate call to the `request_relief` tool. Do NOT try to request multiple items in a single call.
        5.  **Summarize:** After all tool calls are complete, provide a final, clear summary to the user detailing what was successfully dispatched and what failed (and why).
        """,
        sub_agents=[proxy_vic]
    )
    VICTIM_RUNNER = Runner(agent=victim_agent, app_name="victim_frontend", session_service=SESSION_SERVICE)
    
    # --- Supervisor Agent (Instructions remain the same) ---
    supervisor_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="supervisor_flask",
        instruction=f"""
        You are a Relief Operation Supervisor. Your role is to AUDIT and OVERSEE.
        - Most requests are auto-approved by the AI. You can view them with 'supervisor_view_audit_log'.
        - You only need to act on requests in the 'supervisor_view_pending_requests' queue.
        - You have full inventory control.
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
        pass  # Session likely already exists

    final_response = "Sorry, an agent error occurred."
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
            if event.is_final_response() and event.content:
                final_response = event.content.parts[0].text
    except Exception as e:
        final_response = f"Agent Error: {e}"
        print(f"ERROR in run_agent_query: {e}") # Log to server console
    
    return final_response