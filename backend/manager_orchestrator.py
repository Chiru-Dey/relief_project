from google.adk.agents import Agent
from google.adk.tools import AgentTool
from .smart_model import SmartGemini # <--- USE CUSTOM MODEL

from .agents_victim import victim_orchestrator
from .agents_supervisor import supervisor_orchestrator

# --- TOP-LEVEL MANAGER ---
manager_orchestrator = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="relief_manager",
    description="Top-level router.",
    instruction="""
    Router:
    - [[SOURCE: VICTIM]] -> `victim_orchestrator`
    - [[SOURCE: SUPERVISOR]] -> `supervisor_orchestrator`
    Remove the tag before delegating.
    """,
    tools=[
        AgentTool(agent=victim_orchestrator),
        AgentTool(agent=supervisor_orchestrator),
    ]
)