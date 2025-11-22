from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types
from .agents_victim import victim_orchestrator
from .agents_supervisor import supervisor_orchestrator

retry_config = types.HttpRetryOptions(attempts=3)

# --- THE TOP LEVEL ROUTER ---
manager_orchestrator = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="relief_manager",
    description="Top-level orchestrator for the Disaster Relief System.",
    instruction="""
    You are the main router.
    - Victim request? -> Delegate to `victim_orchestrator`.
    - Supervisor command? -> Delegate to `supervisor_orchestrator`.
    """,
    tools=[
        AgentTool(agent=victim_orchestrator),
        AgentTool(agent=supervisor_orchestrator),
    ]
)