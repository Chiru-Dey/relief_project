import os
import uvicorn
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.google_llm import Gemini
from google.genai import types
from dotenv import load_dotenv

# --- IMPORTS ---
import database
import tools_client      # <--- Import Client Tools
import tools_supervisor  # <--- Import Admin Tools

load_dotenv()

# --- SETUP ---
if "GOOGLE_API_KEY" not in os.environ:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

retry_config = types.HttpRetryOptions(
    attempts=5, exp_base=7, initial_delay=1, http_status_codes=[429, 500, 503]
)

# Initialize Database
database.init_db()

# --- AGENT DEFINITION ---

manager_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="relief_manager",
    description="Central Disaster Relief Database & Logistics Hub.",
    instruction="""
    You are the Central Relief Manager.
    You manage a SQL database of inventory and requests.
    
    You expose tools for two types of users:
    1. Support Agents (Client Tools): Checking stock, requesting relief.
    2. Supervisors (Admin Tools): Approving requests, viewing full inventory, restocking.
    
    Always use the appropriate tool for the request.
    """,
    # Register tools from both files
    tools=[
        # Client Tools
        tools_client.check_inventory,
        tools_client.request_relief,
        
        # Supervisor Tools
        tools_supervisor.supervisor_view_pending_requests,
        tools_supervisor.supervisor_decide_request,
        tools_supervisor.admin_view_full_inventory,
        tools_supervisor.admin_restock_item
    ]
)

# --- EXPOSE VIA A2A ---
app = to_a2a(manager_agent, port=8001)

if __name__ == "__main__":
    print("🚀 Starting Modular Relief Manager Server on Port 8001...")
    uvicorn.run("manager_server:app", host="0.0.0.0", port=8001, reload=True)