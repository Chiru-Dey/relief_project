import asyncio
import os
import base64
from dotenv import load_dotenv

# --- ADK IMPORTS ---
from google.adk.agents import Agent # <--- CHANGED
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types
import database

load_dotenv()

# --- GLOBALS ---
VICTIM_RUNNER = None
SUPERVISOR_RUNNER = None
SESSION_SERVICE = InMemorySessionService()

def initialize_adk_agents():
    """Initializes the client-side ADK Agents."""
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY not found.")

    retry_config = types.HttpRetryOptions(attempts=3)
    
    # 1. PROXIES
    proxy_for_victim = RemoteA2aAgent(
        name="relief_manager", 
        description="Hub", 
        agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}"
    )
    proxy_for_supervisor = RemoteA2aAgent(
        name="relief_manager", 
        description="Hub", 
        agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}"
    )
    
    # Dynamic Item List
    try:
        valid_items_list = database.get_all_item_names()
        valid_items = ", ".join(valid_items_list)
    except:
        valid_items = "water_bottles, food_packs"

    # 2. VICTIM CLIENT (THIN PROXY)
    victim_client = Agent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="victim_client",
        instruction=f"""
        You are a Disaster Relief Support agent.
        VALID INVENTORY: [{valid_items}]
        YOUR JOB:
        1. If item is in VALID INVENTORY, pass request to 'relief_manager'.
        2. If item is NOT in list, ask if they want to log a request.
        """,
        sub_agents=[proxy_for_victim]
    )
    VICTIM_RUNNER = Runner(agent=victim_client, app_name="victim_frontend", session_service=SESSION_SERVICE)
    
    # 3. SUPERVISOR CLIENT (THIN PROXY)
    supervisor_client = Agent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="supervisor_client",
        instruction="You are a proxy. Pass the supervisor's command directly to the 'relief_manager' sub-agent without modification.",
        sub_agents=[proxy_for_supervisor]
    )
    SUPERVISOR_RUNNER = Runner(agent=supervisor_client, app_name="supervisor_frontend", session_service=SESSION_SERVICE)
    
    print(f"✅ ADK Client Agents Initialized. ({len(valid_items_list)} items)")

async def run_agent_query(runner, user_id, session_id, message):
    try: await runner.session_service.create_session(app_name=runner.app_name, user_id=user_id, session_id=session_id)
    except: pass

    final_response = "Sorry, an agent error occurred."
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
            if event.is_final_response() and event.content:
                final_response = event.content.parts[0].text
    except Exception as e:
        final_response = f"Agent Error: {e}"
        print(f"ERROR in run_agent_query: {e}")
    
    return final_response