import asyncio
import os
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
    """Initializes the client-side ADK Agents (Proxies)."""
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY not found.")

    retry_config = types.HttpRetryOptions(attempts=3)
    
    # 1. PROXIES
    # These connect to your backend running on port 8001
    proxy_vic = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    proxy_sup = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")

    # 2. VICTIM CLIENT (THIN PROXY)
    # No logic here. Just forwards the message.
    victim_client = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="victim_client",
        instruction="You are a proxy. Pass the user's message directly to the 'relief_manager' sub-agent without modification.",
        sub_agents=[proxy_vic]
    )
    VICTIM_RUNNER = Runner(agent=victim_client, app_name="victim_frontend", session_service=SESSION_SERVICE)
    
    # 3. SUPERVISOR CLIENT (THIN PROXY)
    # No logic here. Just forwards the command.
    supervisor_client = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="supervisor_client",
        instruction="You are a proxy. Pass the supervisor's command directly to the 'relief_manager' sub-agent without modification.",
        sub_agents=[proxy_sup]
    )
    SUPERVISOR_RUNNER = Runner(agent=supervisor_client, app_name="supervisor_frontend", session_service=SESSION_SERVICE)
    
    print("✅ Client-side Proxies Initialized (Logic is on Backend).")

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
        print(f"ERROR: {e}")
    
    return final_response