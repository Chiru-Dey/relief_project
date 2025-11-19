import os
import asyncio
import uuid
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# --- CONFIGURATION ---
retry_config = types.HttpRetryOptions(
    attempts=5, exp_base=7, initial_delay=1, http_status_codes=[429, 500, 503]
)

# --- DEFINE AGENT ---

# 1. Proxy to Manager (Port 8001)
remote_manager_proxy = RemoteA2aAgent(
    name="relief_manager",
    description="The central hub that has inventory data and can dispatch supplies.",
    agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}"
)

# 2. The Victim Support Agent
support_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="victim_support",
    instruction="""
    You are a compassionate Disaster Relief Support agent. 
    Your goal is to help victims get water, food, or medical kits.
    
    1. Ask for their location if not provided.
    2. Use the 'relief_manager' tool to check if items are available or to place a request.
    3. If the manager says it needs approval, explain that to the user gently.
    """,
    sub_agents=[remote_manager_proxy]
)

# --- HELPER ---
async def run_chat(runner, query, session_id):
    session_service = runner.session_service
    app_name = runner.app_name
    
    try: 
        session = await session_service.create_session(app_name=app_name, user_id="victim_user", session_id=session_id)
    except: 
        session = await session_service.get_session(app_name=app_name, user_id="victim_user", session_id=session_id)
    
    print(f"\n🔵 VICTIM: {query}")
    
    user_msg = types.Content(role="user", parts=[types.Part(text=query)])
    
    async for event in runner.run_async(user_id="victim_user", session_id=session.id, new_message=user_msg):
        if event.is_final_response() and event.content:
            print(f"🟢 AGENT: {event.content.parts[0].text}")

# --- MAIN ---
async def main():
    print("🚑 Initializing Support Client...")
    
    runner = Runner(
        agent=support_agent, 
        app_name="relief_support_app", 
        session_service=InMemorySessionService()
    )

    print("✅ Support Agent Ready. Connecting to Manager...")

    # SCENARIO 1: Small Request
    print("\n--- SCENARIO 1: Small Request (Auto-approve) ---")
    await run_chat(runner, "I am at Sector 4. We need 5 water bottles immediately.", "session_small")

    # SCENARIO 2: Large Request
    print("\n--- SCENARIO 2: Large Request (Needs Approval) ---")
    await run_chat(runner, "This is the shelter at Sector 9. We need 20 food packs.", "session_large")
    print("\n(NOTE: Switch to 'supervisor_client.py' to approve this request!)")

if __name__ == "__main__":
    asyncio.run(main())