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

# 2. The Supervisor Agent
supervisor_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="relief_supervisor",
    instruction="""
    You are the Relief Operation Supervisor.
    Your job is to manage high-level logistics.
    
    1. You can ask the 'relief_manager' to show you pending requests.
    2. You can approve or reject requests using the manager's tools.
    3. You can check overall inventory levels.
    """,
    sub_agents=[remote_manager_proxy]
)

# --- HELPER ---
async def run_chat(runner, query, session_id):
    session_service = runner.session_service
    app_name = runner.app_name
    
    try: 
        session = await session_service.create_session(app_name=app_name, user_id="supervisor_user", session_id=session_id)
    except: 
        session = await session_service.get_session(app_name=app_name, user_id="supervisor_user", session_id=session_id)
    
    print(f"\n🔵 SUPERVISOR: {query}")
    
    user_msg = types.Content(role="user", parts=[types.Part(text=query)])
    
    async for event in runner.run_async(user_id="supervisor_user", session_id=session.id, new_message=user_msg):
        if event.is_final_response() and event.content:
            print(f"🟢 AGENT: {event.content.parts[0].text}")

# --- MAIN ---
async def main():
    print("👮 Initializing Supervisor Client...")
    
    runner = Runner(
        agent=supervisor_agent, 
        app_name="relief_supervisor_app", 
        session_service=InMemorySessionService()
    )

    print("✅ Supervisor Agent Ready. Connecting to Manager...")
    
    # SCENARIO 3: Check Queue
    print("\n--- SCENARIO 3: Checking Pending Approvals ---")
    await run_chat(runner, "Check inventory levels and see if there are any pending approvals.", "sup_session_1")
    
    # SCENARIO 4: Action
    # Note: In a real loop, the supervisor would read the ID from the previous output.
    # Here we simulate the supervisor seeing the 'Sector 9' request and acting on it.
    print("\n--- SCENARIO 4: Approving Request ---")
    await run_chat(runner, "Approve the request for the food packs at Sector 9.", "sup_session_1")

if __name__ == "__main__":
    asyncio.run(main())