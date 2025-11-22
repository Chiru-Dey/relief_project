import asyncio
import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()
VICTIM_RUNNER = None
SUPERVISOR_RUNNER = None
SESSION_SERVICE = InMemorySessionService()

def initialize_adk_agents():
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    if "GOOGLE_API_KEY" not in os.environ: raise ValueError("GOOGLE_API_KEY not found.")
    
    # Define retry options
    retry = types.HttpRetryOptions(attempts=3)
    
    proxy_vic = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    proxy_sup = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")

    # 🔥 FIX: Pass retry_options to the Gemini class, NOT the Agent class
    victim_model = Gemini(model="gemini-2.5-flash", retry_options=retry)
    supervisor_model = Gemini(model="gemini-2.5-flash", retry_options=retry)

    victim_client = Agent(
        model=victim_model, # Pass the object, not a string
        name="victim_client",
        instruction="You are a proxy. Pass the message exactly as received to 'relief_manager'.",
        sub_agents=[proxy_vic]
    )
    VICTIM_RUNNER = Runner(agent=victim_client, app_name="victim_frontend", session_service=SESSION_SERVICE)
    
    supervisor_client = Agent(
        model=supervisor_model, # Pass the object, not a string
        name="supervisor_client",
        instruction="You are a proxy. Pass the message exactly as received to 'relief_manager'.",
        sub_agents=[proxy_sup]
    )
    SUPERVISOR_RUNNER = Runner(agent=supervisor_client, app_name="supervisor_frontend", session_service=SESSION_SERVICE)
    print("✅ Client Proxies Ready.")