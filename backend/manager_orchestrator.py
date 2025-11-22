from google.adk.agents import Agent # <--- CHANGED
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types

from .agents_victim import victim_orchestrator
from .agents_supervisor import supervisor_orchestrator

retry_config = types.HttpRetryOptions(attempts=5)

# --- TIER 1: TOP-LEVEL MANAGER (Exposed via A2A) ---
manager_orchestrator = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="relief_manager",
    description="Top-level router for the Disaster Relief System.",
    instruction="""
    You are the main router.
    - If the message sounds like it's from a **victim** in need of help, delegate to the `victim_orchestrator`.
    - If it is a **supervisor** command (e.g., "restock", "approve"), delegate to the `supervisor_orchestrator`.
    """,
    tools=[
        AgentTool(agent=victim_orchestrator),
        AgentTool(agent=supervisor_orchestrator),
    ]
)