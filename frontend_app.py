import asyncio
import os
import sqlite3
import base64
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# --- ADK IMPORTS ---
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# --- FLASK APP ---
app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "relief_logistics.db")

# --- GLOBAL ADK AGENT SETUP ---
VICTIM_RUNNER = None
SUPERVISOR_RUNNER = None
SESSION_SERVICE = InMemorySessionService()

def initialize_adk_agents():
    # ... (Keep existing initialization logic) ...
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    if "GOOGLE_API_KEY" not in os.environ: raise ValueError("GOOGLE_API_KEY not found.")
    retry_config = types.HttpRetryOptions(attempts=3)
    proxy_vic = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    proxy_sup = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    valid_items = "water_bottles, food_packs, medical_kits, blankets, batteries"
    victim_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="victim_support_flask",
        instruction=f"Victim Support. Items: [{valid_items}]. Delegate to 'relief_manager'.",
        sub_agents=[proxy_vic]
    )
    VICTIM_RUNNER = Runner(agent=victim_agent, app_name="victim_frontend", session_service=SESSION_SERVICE)
    supervisor_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="supervisor_flask",
        instruction=f"Supervisor. Items: [{valid_items}]. Delegate to 'relief_manager'. Use BATCH tools.",
        sub_agents=[proxy_sup]
    )
    SUPERVISOR_RUNNER = Runner(agent=supervisor_agent, app_name="supervisor_frontend", session_service=SESSION_SERVICE)
    print("✅ ADK Agents Initialized Successfully.")


# --- FLASK ROUTES ---

@app.route("/")
def victim_chat():
    # 🔥 Pass the correct API endpoint to the template
    return render_template("victim_chat.html", api_endpoint="/api/victim_chat")

@app.route("/api/victim_chat", methods=["POST"])
async def handle_victim_chat():
    # ... (Keep existing logic) ...
    data = request.json
    session_id = data.get("session_id", "default_web_session")
    user_message = None
    if "text" in data and data["text"]: user_message = types.Content(role="user", parts=[types.Part(text=data["text"])])
    elif "audio" in data and data["audio"]:
        try:
            header, encoded = data["audio"].split(",", 1)
            audio_bytes = base64.b64decode(encoded)
            user_message = types.Content(role="user", parts=[types.Part(inline_data=types.Blob(mime_type="audio/webm", data=audio_bytes))])
        except Exception as e: return jsonify({"reply": f"Audio Error: {e}"}), 400
    if not user_message: return jsonify({"reply": "No message."}), 400
    try: await SESSION_SERVICE.create_session(app_name=VICTIM_RUNNER.app_name, user_id="victim_user", session_id=session_id)
    except: pass 
    final_response = "Error running victim agent."
    try:
        async for event in VICTIM_RUNNER.run_async(user_id="victim_user", session_id=session_id, new_message=user_message):
            if event.is_final_response() and event.content: final_response = event.content.parts[0].text
    except Exception as e: final_response = f"Agent Error: {e}"
    return jsonify({"reply": final_response})


@app.route("/supervisor")
def supervisor_dashboard():
    # 🔥 Pass the correct API endpoints to the template
    return render_template(
        "supervisor_dashboard.html", 
        data_endpoint="/api/supervisor_data",
        command_endpoint="/api/supervisor_command"
    )

@app.route("/api/supervisor_data", methods=["GET"])
def get_supervisor_data():
    # ... (Keep existing logic) ...
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        inventory = [dict(row) for row in conn.execute("SELECT * FROM inventory ORDER BY item_name ASC").fetchall()]
        requests = [dict(row) for row in conn.execute("SELECT * FROM requests WHERE status='PENDING' ORDER BY urgency DESC, id ASC").fetchall()]
        conn.close()
        return jsonify({"inventory": inventory, "requests": requests})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/supervisor_command", methods=["POST"])
async def run_supervisor_command():
    # ... (Keep existing logic) ...
    data = request.json
    command = data.get("command")
    if not command: return jsonify({"reply": "No command."}), 400
    session_id = "supervisor_flask_session"
    user_message = types.Content(role="user", parts=[types.Part(text=command)])
    try: await SESSION_SERVICE.create_session(app_name=SUPERVISOR_RUNNER.app_name, user_id="admin_user", session_id=session_id)
    except: pass
    final_response = "Error running supervisor command."
    try:
        async for event in SUPERVISOR_RUNNER.run_async(user_id="admin_user", session_id=session_id, new_message=user_message):
            if event.is_final_response() and event.content: final_response = event.content.parts[0].text
    except Exception as e: final_response = f"Agent Error: {e}"
    return jsonify({"reply": final_response})


if __name__ == "__main__":
    initialize_adk_agents()
    app.run(port=5000, debug=True, use_reloader=False) # Important: use_reloader=False for threads