import asyncio
import os
import sqlite3
import base64
import queue
import threading
import time
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# --- ADK IMPORTS ---
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.api_core import exceptions

load_dotenv()

# --- FLASK APP ---
app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "relief_logistics.db")

# --- GLOBAL QUEUE & STORAGE ---
TASK_QUEUE = queue.Queue()
JOB_RESULTS = {}

# --- GLOBAL ADK AGENTS ---
VICTIM_RUNNER = None
SUPERVISOR_RUNNER = None

def initialize_adk_agents():
    """Initializes ADK Runners. Called once at startup."""
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY not found.")

    retry_config = types.HttpRetryOptions(attempts=5, initial_delay=5, max_delay=60, exp_base=2)
    session_service = InMemorySessionService()

    proxy_vic = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    proxy_sup = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")

    valid_items = "water_bottles, food_packs, medical_kits, blankets, batteries"

    victim_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="victim_support",
        instruction=f"Victim Support. Items: [{valid_items}]. Delegate to 'relief_manager'.",
        sub_agents=[proxy_vic]
    )
    VICTIM_RUNNER = Runner(agent=victim_agent, app_name="victim_frontend", session_service=session_service)
    
    supervisor_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="supervisor",
        instruction=f"Supervisor. Items: [{valid_items}]. Delegate to 'relief_manager'. Use BATCH tools.",
        sub_agents=[proxy_sup]
    )
    SUPERVISOR_RUNNER = Runner(agent=supervisor_agent, app_name="supervisor_frontend", session_service=session_service)
    print("✅ ADK Agents Initialized.")

# --- BACKGROUND WORKER THREAD ---

def agent_worker():
    """A single, long-running thread that consumes jobs from TASK_QUEUE with rate limiting."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    last_api_call_time = 0
    MIN_INTERVAL_SECONDS = 6.5 

    async def run_task(job):
        nonlocal last_api_call_time
        time_since_last_call = time.time() - last_api_call_time
        if time_since_last_call < MIN_INTERVAL_SECONDS:
            wait_time = MIN_INTERVAL_SECONDS - time_since_last_call
            print(f"⏳ Rate Limiter: Waiting for {wait_time:.2f} seconds...")
            time.sleep(wait_time)
        
        last_api_call_time = time.time()
        
        runner = SUPERVISOR_RUNNER if job["persona"] == "supervisor" else VICTIM_RUNNER
        session_id = job.get("session_id", "default_session")
        
        user_message = None
        if "text" in job and job["text"]:
            user_message = types.Content(role="user", parts=[types.Part(text=job["text"])])
        elif "audio" in job and job["audio"]:
            try:
                header, encoded = job["audio"].split(",", 1)
                audio_bytes = base64.b64decode(encoded)
                user_message = types.Content(role="user", parts=[types.Part(inline_data=types.Blob(mime_type="audio/webm", data=audio_bytes))])
            except Exception as e: return f"Audio Decode Error: {e}"

        if not user_message: return "No message content"

        try: await runner.session_service.create_session(app_name=runner.app_name, user_id=job["persona"], session_id=session_id)
        except: pass

        final_response = "Agent Error."
        try:
            async for event in runner.run_async(user_id=job["persona"], session_id=session_id, new_message=user_message):
                if event.is_final_response() and event.content:
                    final_response = event.content.parts[0].text
        
        except exceptions.ResourceExhausted as e:
            print(f"RATE LIMIT HIT: {e}")
            final_response = "System is busy. Your request has been re-queued automatically. Please wait."
            TASK_QUEUE.put(job) 
            time.sleep(10)
        except Exception as e:
            final_response = f"An unexpected agent error occurred."
        
        return final_response

    print("🤖 Agent Worker thread started with Rate Limiter.")
    while True:
        job = TASK_QUEUE.get()
        if job is None: break
        
        client_id = job["client_id"]
        result_text = loop.run_until_complete(run_task(job))

        if client_id not in JOB_RESULTS: JOB_RESULTS[client_id] = []
        JOB_RESULTS[client_id].append({"task_name": job["task_name"], "output": result_text, "persona": job["persona"]})

# --- FLASK ROUTES ---
@app.route("/")
def victim_chat(): return render_template("victim_chat.html")

@app.route("/supervisor")
def supervisor_dashboard(): return render_template("supervisor_dashboard.html")

@app.route("/api/submit_task", methods=["POST"])
def submit_task():
    data = request.json
    TASK_QUEUE.put(data)
    return jsonify({"status": "queued"})

@app.route("/api/get_results/<client_id>", methods=["GET"])
def get_results(client_id):
    results = JOB_RESULTS.pop(client_id, [])
    return jsonify({"results": results})

@app.route("/api/supervisor_data", methods=["GET"])
def get_supervisor_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        inventory = [dict(row) for row in conn.execute("SELECT * FROM inventory ORDER BY item_name ASC").fetchall()]
        requests = [dict(row) for row in conn.execute("SELECT * FROM requests WHERE status='PENDING' OR status='ACTION_REQUIRED' ORDER BY urgency DESC, id ASC").fetchall()]
        conn.close()
        return jsonify({"inventory": inventory, "requests": requests})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🔥 FIX: RESTORED THE AUDIT LOG ENDPOINT
@app.route("/api/audit_log", methods=["GET"])
def get_audit_log():
    """
    Returns the list of recently COMPLETED (AI or Manual) actions.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # Get last 20 actions that are NOT pending/required
        rows = conn.execute("""
            SELECT * FROM requests 
            WHERE status NOT IN ('PENDING', 'ACTION_REQUIRED', 'FLAGGED') 
            ORDER BY id DESC LIMIT 20
        """).fetchall()
        conn.close()
        
        logs = []
        for r in rows:
            # Create a user-friendly log message
            action_desc = "Unknown Action"
            if r['status'] == 'AI_APPROVED':
                action_desc = f"AI Auto-Approved: Dispatched {r['quantity']}x {r['item_name']} to {r['location']}."
            elif r['status'] == 'APPROVED_MANUAL':
                action_desc = f"Supervisor Approved: Dispatched {r['quantity']}x {r['item_name']}."
            elif r['status'] == 'REJECTED':
                action_desc = f"Supervisor Rejected request for {r['quantity']}x {r['item_name']}."
            elif r['status'] == 'ACTION_TAKEN':
                 action_desc = f"Supervisor resolved alert: {r['notes']}"

            logs.append({
                "id": r["id"],
                "action": action_desc,
                "status": r["status"]
            })
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    initialize_adk_agents()
    worker_thread = threading.Thread(target=agent_worker, daemon=True)
    worker_thread.start()
    app.run(port=5000, debug=True, use_reloader=False)