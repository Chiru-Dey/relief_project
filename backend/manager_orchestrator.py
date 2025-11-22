from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.models.google_llm import Gemini
from google.genai import types
from .agents_victim import victim_orchestrator
from .agents_supervisor import supervisor_orchestrator

retry_config = types.HttpRetryOptions(attempts=5)

# --- TIER 1: TOP-LEVEL MANAGER ---
manager_orchestrator = Agent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="relief_manager",
    description="Top-level router.",
    instruction="""
    You are the Router. 
    1. Look for the tag `[[SOURCE: ...]]` at the start of the message.
    
    2. **IF [[SOURCE: VICTIM]]:**
       - Remove the tag.
       - Delegate the remaining text to `victim_orchestrator`.
       
    3. **IF [[SOURCE: SUPERVISOR]]:**
       - Remove the tag.
       - Delegate the remaining text to `supervisor_orchestrator`.
       
    Do not process the request yourself. Route and strip the tag.
    """,
    tools=[
        AgentTool(agent=victim_orchestrator),
        AgentTool(agent=supervisor_orchestrator),
    ]
)