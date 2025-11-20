import os
import uvicorn
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.google_llm import Gemini
from google.genai import types
from dotenv import load_dotenv

import database
import tools_client
import tools_supervisor

load_dotenv()

if "GOOGLE_API_KEY" not in os.environ:
    raise ValueError("GOOGLE_API_KEY not found")

retry_config = types.HttpRetryOptions(attempts=5, exp_base=7, initial_delay=1, http_status_codes=[429, 500, 503])

# Initialize DB
database.init_db()

manager_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
    name="relief_manager",
    description="Central Disaster Relief Database & Logistics Hub.",
    instruction="""
    You are the Central Relief Manager.
    You manage a SQL database of inventory and requests.
    
    Capabilities:
    1. Support Agents: Check stock, Place requests (mark as critical if needed), Check status of ID.
    2. Supervisors: 
       - Approve/Reject requests.
       - CRUD Inventory: Add new items, Delete items, Restock.
       - Reporting: View full inventory, Get Low Stock alerts.
    """,
    tools=[
        # Client Tools
        tools_client.check_inventory,
        tools_client.request_relief,
        tools_client.check_request_status, 
        
        # Supervisor Tools
        tools_supervisor.supervisor_view_pending_requests,
        tools_supervisor.supervisor_decide_request,
        tools_supervisor.admin_view_full_inventory,
        tools_supervisor.admin_restock_item,
        tools_supervisor.admin_add_new_item,      
        tools_supervisor.admin_delete_item,       
        tools_supervisor.admin_get_low_stock_report 
    ]
)

app = to_a2a(manager_agent, port=8001)

if __name__ == "__main__":
    print("🚀 Starting Relief Manager Server (Dev Mode) on Port 8001...")
    uvicorn.run("manager_server:app", host="0.0.0.0", port=8001, reload=True)