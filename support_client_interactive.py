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

support_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
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

# --- INTERACTIVE LOOP ---
async def main():
    runner = Runner(
        agent=support_agent, 
        app_name="relief_support_app", 
        session_service=InMemorySessionService()
    )

    # Generate a unique session ID for this specific chat interaction
    session_id = str(uuid.uuid4())
    
    # Create the session
    await runner.session_service.create_session(app_name=runner.app_name, user_id="victim_user", session_id=session_id)

    print("\n" + "="*60)
    print("🚑 DISASTER RELIEF SUPPORT (Live Terminal)")
    print("   Type 'exit' or 'quit' to end the chat.")
    print("="*60 + "\n")

    print("🟢 AGENT: Hello. I am the disaster relief support. How can I help you today?")

    while True:
        try:
            user_input = input("\n🔵 YOU: ").strip()
            
            if user_input.lower() in ["exit", "quit"]:
                print("👋 Exiting.")
                break
            
            if not user_input:
                continue

            user_msg = types.Content(role="user", parts=[types.Part(text=user_input)])
            
            print("   (Agent is thinking/contacting HQ...)")
            
            async for event in runner.run_async(user_id="victim_user", session_id=session_id, new_message=user_msg):
                if event.is_final_response() and event.content:
                    response_text = event.content.parts[0].text
                    print(f"🟢 AGENT: {response_text}")
                    
        except KeyboardInterrupt:
            print("\n👋 Exiting.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())