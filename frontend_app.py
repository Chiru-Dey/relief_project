import asyncio
import os
import sqlite3
import base64
import queue
import threading
import time
import random
import re
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# --- ADK IMPORTS ---
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.errors import ClientError
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

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
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY not found.")

    # We rely on our own loop for retries, so we keep internal retries low/fast
    retry_config = types.HttpRetryOptions(attempts=1, initial_delay=1)
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

# --- SMARTER WORKER ---

def calculate_backoff(attempt):
    """Fallback exponential backoff."""
    delay = min(60, 2 * (2 ** attempt))
    return delay * (0.5 + random.random() / 2)

def extract_retry_delay(error_message):
    """
    Parses wait time from Gemini error messages.
    Supports:
    1. "retry in 13.72s"
    2. "'retryDelay': '13s'" (JSON format)
    """
    msg = str(error_message)
    
    # Check for JSON format first (most common in your logs)
    json_match = re.search(r"retryDelay': '(\d+(\.\d+)?)s'", msg)
    if json_match:
        return float(json_match.group(1))
        
    # Check for plain text format
    text_match = re.search(r"retry in (\d+(\.\d+)?)s", msg)
    if text_match:
        return float(text_match.group(1))
        
    return None

def agent_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Global Throttle
    last_api_call_time = 0
    MIN_REQUEST_INTERVAL = 6.5 

    async def run_task_logic(job):
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
            except Exception as e: return f"Audio Error: {e}"

        if not user_message: return "No content"

        try: await runner.session_service.create_session(app_name=runner.app_name, user_id=job["persona"], session_id=session_id)
        except: pass

        final_response = None
        async for event in runner.run_async(user_id=job["persona"], session_id=session_id, new_message=user_message):
            if event.is_final_response() and event.content:
                final_response = event.content.parts[0].text
        
        if final_response:
            return final_response
        else:
            raise Exception("Empty response from agent")

    print("🤖 Agent Worker started with Smart Re-Queueing.")
    
    while True:
        job = TASK_QUEUE.get()
        if job is None: break
        
        # 1. Rate Limiter (Pre-flight check)
        time_since = time.time() - last_api_call_time
        if time_since < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - time_since)
        last_api_call_time = time.time()
        
        client_id = job["client_id"]
        result_text = ""
        should_requeue = False

        try:
            result_text = loop.run_until_complete(run_task_logic(job))
            
        except Exception as e:
            error_str = str(e)
            
            # 🔥 CATCH RATE LIMITS
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "Quota" in error_str:
                # 1. Get wait time
                wait_time = extract_retry_delay(error_str)
                if not wait_time:
                    # Fallback logic based on retry count in job
                    attempt = job.get("retry_count", 0)
                    wait_time = calculate_backoff(attempt)
                
                # Add safety buffer
                wait_time += 1.0
                
                print(f"⚠️ Rate Limit Hit! Google says wait {wait_time:.2f}s. Re-queueing...")
                
                # 2. Sleep here to prevent tight loop hammering
                time.sleep(wait_time)
                
                # 3. Re-queue logic
                job["retry_count"] = job.get("retry_count", 0) + 1
                if job["retry_count"] <= 10: # Max 10 retries
                    should_requeue = True
                else:
                    result_text = "ERROR: System overloaded. Max retries exceeded."
            
            elif "503" in error_str:
                print("⚠️ 503 Error. Sleeping 5s and Re-queueing...")
                time.sleep(5)
                job["retry_count"] = job.get("retry_count", 0) + 1
                should_requeue = True
            
            else:
                print(f"❌ Fatal Error: {error_str}")
                result_text = "ERROR: Internal System Failure."

        # --- POST PROCESSING ---
        if should_requeue:
            # Put back in queue. The frontend will just keep waiting (spinner spinning).
            TASK_QUEUE.put(job)
        else:
            # Success or Fatal Error -> Send result to UI
            if client_id not in JOB_RESULTS: JOB_RESULTS[client_id] = []
            JOB_RESULTS[client_id].append({"task_name": job["task_name"], "output": result_text, "persona": job["persona"]})

# --- FLASK ROUTES ---
@app.route("/")
def victim_chat(): return render_template("victim_chat.html")
@app.route("/supervisor")
def supervisor_dashboard(): return render_template("supervisor_dashboard.html")
@app.route("/api/submit_task", methods=["POST"])
def submit_task():
    TASK_QUEUE.put(request.json)
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
    worker_thread = threading.Thread(target=agent_worker, daemon=True)
    worker_thread.start()
    app.run(port=5000, debug=True, use_reloader=False)