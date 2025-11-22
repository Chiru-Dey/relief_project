import asyncio
import os
import sqlite3
import base64
import queue
import threading
import time
import random
import re  # <--- NEW: For parsing the error message
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# --- ADK IMPORTS ---
from google.adk.agents import Agent
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
    """Initializes ADK Runners."""
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY not found.")

    # Internal ADK retries (fast failures)
    retry_config = types.HttpRetryOptions(
        attempts=3, initial_delay=1, max_delay=10, exp_base=2
    )
    
    session_service = InMemorySessionService()

    proxy_vic = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    proxy_sup = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")

    valid_items = "water_bottles, food_packs, medical_kits, blankets, batteries"

    victim_agent = Agent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="victim_support",
        instruction=f"Victim Support. Items: [{valid_items}]. Delegate to 'relief_manager'.",
        sub_agents=[proxy_vic]
    )
    VICTIM_RUNNER = Runner(agent=victim_agent, app_name="victim_frontend", session_service=session_service)
    
    supervisor_agent = Agent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="supervisor",
        instruction=f"Supervisor. Items: [{valid_items}]. Delegate to 'relief_manager'. Use BATCH tools.",
        sub_agents=[proxy_sup]
    )
    SUPERVISOR_RUNNER = Runner(agent=supervisor_agent, app_name="supervisor_frontend", session_service=session_service)
    print("✅ ADK Agents Initialized.")

# --- BACKGROUND WORKER ---

def calculate_backoff(attempt, base_delay=2.0, max_delay=60.0):
    """Fallback exponential backoff."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    return delay * (0.5 + random.random() / 2) # Add Jitter

def extract_retry_delay(error_message):
    """
    Parses 'Please retry in 37.19s' from the Gemini error message.
    Returns the float seconds or None.
    """
    # Pattern matches "retry in 12.34s" or "retry in 12s"
    match = re.search(r"retry in (\d+(\.\d+)?)s", str(error_message))
    if match:
        return float(match.group(1))
    return None

def agent_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    last_api_success_time = 0
    MIN_REQUEST_INTERVAL = 5.0

    async def run_task(job):
        nonlocal last_api_success_time
        
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
            except Exception as e: return "Audio Error"

        if not user_message: return "No content"

        # --- APPLICATION LEVEL RETRY LOOP ---
        max_app_retries = 5
        current_attempt = 0
        
        while current_attempt < max_app_retries:
            # 1. Global Throttle (Prevent bursts)
            time_since_last = time.time() - last_api_success_time
            if time_since_last < MIN_REQUEST_INTERVAL:
                time.sleep(MIN_REQUEST_INTERVAL - time_since_last)

            try:
                try: await runner.session_service.create_session(app_name=runner.app_name, user_id=job["persona"], session_id=session_id)
                except: pass

                final_response = None
                async for event in runner.run_async(user_id=job["persona"], session_id=session_id, new_message=user_message):
                    if event.is_final_response() and event.content:
                        final_response = event.content.parts[0].text
                
                if final_response:
                    last_api_success_time = time.time()
                    return final_response
                else:
                    raise Exception("Empty response")

            # 🔥 SMART RETRY LOGIC
            except exceptions.ResourceExhausted as e:
                current_attempt += 1
                
                # 1. Try to extract exact time from Google
                google_wait_time = extract_retry_delay(e)
                
                if google_wait_time:
                    # Add small buffer (0.5s) to be safe
                    wait_time = google_wait_time + 0.5
                    print(f"⚠️ Rate Limit: Google asked to wait {google_wait_time}s. Sleeping {wait_time:.2f}s...")
                else:
                    # Fallback if message format changes
                    wait_time = calculate_backoff(current_attempt)
                    print(f"⚠️ Rate Limit: Backing off {wait_time:.2f}s...")
                
                time.sleep(wait_time)
                continue

            except Exception as e:
                print(f"❌ Fatal Error: {e}")
                return "System Error. Please try again."
        
        return "⚠️ System overloaded. Please try again in a minute."

    print("🤖 Agent Worker started (Smart Rate Limiting).")
    while True:
        job = TASK_QUEUE.get()
        if job is None: break
        
        client_id = job["client_id"]
        res = loop.run_until_complete(run_task(job))

        if client_id not in JOB_RESULTS: JOB_RESULTS[client_id] = []
        JOB_RESULTS[client_id].append({"task_name": job["task_name"], "output": res, "persona": job["persona"]})

# --- ROUTES ---
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
    except Exception as e: return jsonify({"error": str(e)}), 500
@app.route("/api/audit_log", methods=["GET"])
def get_audit_log():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM requests WHERE status NOT IN ('PENDING', 'ACTION_REQUIRED', 'FLAGGED') ORDER BY id DESC LIMIT 20").fetchall()
        conn.close()
        logs = [{"id": r["id"], "action": f"{r['status']}: {r['notes'] or 'Processed'} ({r['item_name']} x{r['quantity']})"} for r in rows]
        return jsonify({"logs": logs})
    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    initialize_adk_agents()
    threading.Thread(target=agent_worker, daemon=True).start()
    app.run(port=5000, debug=True, use_reloader=False)