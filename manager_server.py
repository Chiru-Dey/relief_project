import os
import sys
import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from dotenv import load_dotenv

# --- 1. SYSTEM PATH SETUP ---
# This ensures Python can find your 'backend', 'database.py', etc.
# regardless of where you run the command from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

# --- 2. INITIALIZE DATABASE ---
# We must do this BEFORE importing agents, because the agents read 
# valid items from the DB during their initialization.
import database
database.init_db()

# --- 3. IMPORT THE BRAIN ---
# This imports the top-level orchestrator, which recursively imports
# the supervisor and victim orchestrators and their workers.
from backend.manager_orchestrator import manager_orchestrator

# --- 4. CONFIGURATION ---
load_dotenv()

if "GOOGLE_API_KEY" not in os.environ:
    raise ValueError("GOOGLE_API_KEY not found. Please check your .env file.")

# --- 5. A2A SERVER SETUP ---
# This wraps the ADK agent in a FastAPI server compatible with the A2A protocol.
app = to_a2a(manager_orchestrator, port=8001)

if __name__ == "__main__":
    print("🚀 Starting Hierarchical Multi-Agent Backend Server on Port 8001...")
    print("   - Database Initialized")
    print("   - Agents Loaded")
    print("   - A2A Endpoint: http://localhost:8001")
    
    # reload=True allows the server to restart if you modify agent code
    uvicorn.run("manager_server:app", host="0.0.0.0", port=8001, reload=True)