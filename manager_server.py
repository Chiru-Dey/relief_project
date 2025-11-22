import os
import sys
import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from dotenv import load_dotenv

# Setup Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Init DB
import database
database.init_db()

# Import Top-Level Agent
from backend.manager_orchestrator import manager_orchestrator

load_dotenv()

if "GOOGLE_API_KEY" not in os.environ:
    raise ValueError("GOOGLE_API_KEY not found")

app = to_a2a(manager_orchestrator, port=8001)

if __name__ == "__main__":
    print("🚀 Starting Hierarchical Multi-Agent Backend Server...")
    uvicorn.run("manager_server:app", host="0.0.0.0", port=8001, reload=True)