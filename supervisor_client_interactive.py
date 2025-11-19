import os
import asyncio
import uuid
import sys
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# --- CONFIG ---
retry_config = types.HttpRetryOptions(attempts=5, exp_base=7, initial_delay=1, http_status_codes=[429, 500, 503])

# --- AGENT SETUP ---
print("🔌 Connecting to Relief Manager Hub...")
try:
    remote_manager_proxy = RemoteA2aAgent(
        name="relief_manager",
        description="The central hub that has inventory data and can dispatch supplies.",
        agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}"
    )
except Exception as e:
    print(f"❌ Error: Could not connect to Manager. Is 'manager_server.py' running? {e}")
    sys.exit(1)

supervisor_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="relief_supervisor",
    instruction="""
    You are the Relief Operation Supervisor.
    Your job is to manage high-level logistics.
    
    1. You can ask the 'relief_manager' to show you pending requests.
    2. You can approve or reject requests using the manager's tools.
    3. You can check overall inventory levels.
    
    Be concise and direct.
    """,
    sub_agents=[remote_manager_proxy]
)

# --- INTERACTIVE LOOP ---
async def main():
    runner = Runner(
        agent=supervisor_agent, 
        app_name="relief_supervisor_app", 
        session_service=InMemorySessionService()
    )

    session_id = str(uuid.uuid4())
    await runner.session_service.create_session(app_name=runner.app_name, user_id="admin_user", session_id=session_id)

    print("\n" + "="*60)
    print("👮 RELIEF SUPERVISOR DASHBOARD (Live Terminal)")
    print("   Commands examples:")
    print("   - 'Check pending approvals'")
    print("   - 'Show inventory'")
    print("   - 'Approve request 1'")
    print("   Type 'exit' to quit.")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("\n🔵 COMMAND: ").strip()
            
            if user_input.lower() in ["exit", "quit"]:
                break
            
            if not user_input:
                continue

            user_msg = types.Content(role="user", parts=[types.Part(text=user_input)])
            
            print("   (Processing command...)")
            
            async for event in runner.run_async(user_id="admin_user", session_id=session_id, new_message=user_msg):
                if event.is_final_response() and event.content:
                    response_text = event.content.parts[0].text
                    print(f"🟢 SYSTEM: {response_text}")
                    
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())