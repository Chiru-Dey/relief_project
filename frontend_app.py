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

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "relief_logistics.db")

# --- GLOBAL STATE ---
TASK_QUEUE = queue.Queue()
JOB_RESULTS = {}

# Store chat history in RAM: { session_id: [ {sender: 'user'|'ai', text: '...'} ] }
CHAT_STORE = {} 

# Store supervisor activity logs in RAM: [ {timestamp: '...', action: '...', type: '...'} ]
SUPERVISOR_ACTIVITY_LOG = []

VICTIM_RUNNER = None
SUPERVISOR_RUNNER = None

def initialize_adk_agents():
    global VICTIM_RUNNER, SUPERVISOR_RUNNER
    if "GOOGLE_API_KEY" not in os.environ: raise ValueError("GOOGLE_API_KEY not found.")

    retry_config = types.HttpRetryOptions(attempts=3, initial_delay=1, max_delay=10, exp_base=2)
    session_service = InMemorySessionService()

    proxy_vic = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
    proxy_sup = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")

    valid_items = "water_bottles, food_packs, medical_kits, blankets, batteries"

    victim_agent = Agent(
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        name="victim_support",
        instruction=f"""You coordinate victim relief requests.

CRITICAL: If user provides additional info (like location), look at EARLIER messages for items/quantities!

Example CORRECT:
- User: "need 20 water bottles"
- User: "at Delhi"
→ You remember: 20 water bottles at Delhi

Example WRONG:
- User: "need 20 water bottles"
- User: "at Delhi"  
→ You ask: "What item?" ❌ NO! You already know!

Available items: [{valid_items}]
Delegate to 'relief_manager'.""",
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

# --- WORKER ---
def calculate_backoff(attempt):
    delay = min(60, 2 * (2 ** attempt))
    return delay * (0.5 + random.random() / 2)

def extract_retry_delay(error_message):
    match = re.search(r"retry in (\d+(\.\d+)?)s", str(error_message))
    if match: return float(match.group(1))
    return None

def agent_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    last_api_call_time = 0
    MIN_GAP = 6.0 

    async def run_task(job):
        nonlocal last_api_call_time
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
            except: return "Audio Error"

        if not user_message: return "No content"

        max_retries = 5
        for attempt in range(max_retries + 1):
            elapsed = time.time() - last_api_call_time
            if elapsed < MIN_GAP: time.sleep(MIN_GAP - elapsed)

            try:
                try: await runner.session_service.create_session(app_name=runner.app_name, user_id=job["persona"], session_id=session_id)
                except: pass

                final_response = None
                async for event in runner.run_async(user_id=job["persona"], session_id=session_id, new_message=user_message):
                    if event.is_final_response() and event.content:
                        final_response = event.content.parts[0].text
                
                if final_response:
                    last_api_call_time = time.time()
                    return final_response
                else:
                    raise Exception("Empty response")

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE" in error_str or "Quota" in error_str:
                    if attempt < max_retries:
                        wait = extract_retry_delay(error_str) or calculate_backoff(attempt)
                        print(f"⏳ Frontend: Rate limit hit, retrying after {wait:.2f}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait + 1)
                        continue
                    else:
                        print(f"❌ Frontend: Rate limit exceeded after {max_retries} retries")
                        return None  # Don't send error to frontend
                elif "503" in error_str:
                    time.sleep(2)
                    continue
                else:
                    print(f"❌ Frontend: Connection error: {error_str}")
                    return None  # Don't send error to frontend
        return None  # Timeout - don't send to frontend

    while True:
        job = TASK_QUEUE.get()
        if job is None: break
        
        # Save User Message to History
        user_msg_added = False
        if job["persona"] == "victim":
            sess_id = job.get("session_id")
            if sess_id not in CHAT_STORE: CHAT_STORE[sess_id] = []
            msg_text = job.get("text", "Audio Message")
            CHAT_STORE[sess_id].append({"sender": "user", "text": msg_text})
            user_msg_added = True
            
            # Set session context for tools to use
            import tools_client
            tools_client.set_session_context(sess_id)
            
            # PRE-REGISTER session with potential locations mentioned in message
            # This allows backend to find session even before tool executes
            import database
            import re
            # Extract location mentions (simple heuristic)
            locations = re.findall(r'\b(at|in|to)\s+(\w+)', msg_text.lower())
            for _, location in locations:
                database.register_active_session(sess_id, location.title())

        client_id = job["client_id"]
        res = loop.run_until_complete(run_task(job))
        
        # Clear session context after task completion
        if job["persona"] == "victim":
            import tools_client
            tools_client.clear_session_context()

        # Only save and send to frontend if we have a valid response
        if res is not None:
            # Save AI Response to History
            if job["persona"] == "victim":
                sess_id = job.get("session_id")
                CHAT_STORE[sess_id].append({"sender": "ai", "text": res})
            elif job["persona"] == "supervisor":
                # Log supervisor command to activity log
                log_supervisor_activity(f"Command executed: {job.get('text', job['task_name'])}", "info")

            if client_id not in JOB_RESULTS: JOB_RESULTS[client_id] = []
            JOB_RESULTS[client_id].append({"task_name": job["task_name"], "output": res, "persona": job["persona"]})
        else:
            print(f"⚠️ Skipping result for {job['task_name']} - backend error suppressed")
            # Remove user message from history if we added it but got no response
            if user_msg_added and job["persona"] == "victim":
                sess_id = job.get("session_id")
                if CHAT_STORE.get(sess_id) and CHAT_STORE[sess_id][-1]["sender"] == "user":
                    CHAT_STORE[sess_id].pop()
                    print(f"   Removed orphaned user message from chat history")

# --- ROUTES ---
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

# --- HISTORY ENDPOINT ---
@app.route("/api/victim_history/<session_id>", methods=["GET"])
def get_victim_history(session_id):
    """Returns chat history for a specific session ID."""
    return jsonify({"history": CHAT_STORE.get(session_id, [])})

@app.route("/api/debug/all_sessions", methods=["GET"])
def debug_all_sessions():
    """Debug endpoint to view all active chat sessions."""
    sessions_info = {}
    for sess_id, messages in CHAT_STORE.items():
        sessions_info[sess_id] = {
            "message_count": len(messages),
            "last_message": messages[-1] if messages else None,
            "messages": messages
        }
    return jsonify({
        "total_sessions": len(CHAT_STORE),
        "sessions": sessions_info
    })

# --- SUPERVISOR DATA ---
@app.route("/api/supervisor_data", methods=["GET"])
def get_supervisor_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        inventory = [dict(row) for row in conn.execute("SELECT * FROM inventory ORDER BY item_name ASC").fetchall()]
        # Include PENDING_DISPATCH in the supervisor view so they can see pending auto-dispatch requests
        requests = [dict(row) for row in conn.execute("SELECT * FROM requests WHERE status IN ('PENDING', 'ACTION_REQUIRED', 'PENDING_DISPATCH') ORDER BY urgency DESC, id ASC").fetchall()]
        conn.close()
        return jsonify({"inventory": inventory, "requests": requests})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/audit_log", methods=["GET"])
def get_audit_log():
    """Returns audit logs from database (excluding AI_APPROVED and PENDING_DISPATCH which are now in activity log)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # Fetch logs excluding AI_APPROVED and PENDING_DISPATCH (those go to activity log now)
        rows = conn.execute("SELECT * FROM requests WHERE status NOT IN ('PENDING', 'ACTION_REQUIRED', 'FLAGGED', 'AI_APPROVED', 'PENDING_DISPATCH') ORDER BY id DESC LIMIT 20").fetchall()
        conn.close()
        logs = []
        for r in rows:
            status = r["status"]
            action = f"{status}: {r['notes'] or 'Processed'} ({r['item_name']} x{r['quantity']})"
            logs.append({"id": r["id"], "action": action})
        return jsonify({"logs": logs})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/supervisor_activity_log", methods=["GET"])
def get_supervisor_activity_log():
    """Returns in-memory supervisor activity logs"""
    return jsonify({"logs": SUPERVISOR_ACTIVITY_LOG})

@app.route("/api/log_supervisor_activity", methods=["POST"])
def log_supervisor_activity_api():
    """API endpoint for logging supervisor activities from tools"""
    data = request.json
    action = data.get("action", "")
    log_type = data.get("type", "info")
    if action:
        log_supervisor_activity(action, log_type)
    return jsonify({"status": "logged"})

@app.route("/api/send_victim_notification", methods=["POST"])
def send_victim_notification():
    """Add an AI message to victim's chat history (used for auto-dispatch confirmations)"""
    data = request.json
    session_id = data.get("session_id")
    message = data.get("message")
    
    if session_id and message:
        if session_id not in CHAT_STORE:
            CHAT_STORE[session_id] = []
        CHAT_STORE[session_id].append({"sender": "ai", "text": message})
    
    return jsonify({"status": "sent"})

def log_supervisor_activity(action: str, log_type: str = "info"):
    """
    Add activity log entry for supervisor.
    log_type can be: 'info', 'success', 'warning', 'error', 'system'
    """
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    SUPERVISOR_ACTIVITY_LOG.append({
        "timestamp": timestamp,
        "action": action,
        "type": log_type
    })
    # Keep only last 100 entries to prevent memory bloat
    if len(SUPERVISOR_ACTIVITY_LOG) > 100:
        SUPERVISOR_ACTIVITY_LOG.pop(0)

# --- 🔥 NEW DIRECT ADMIN ROUTES ---

@app.route("/api/admin/restock", methods=["POST"])
def admin_restock():
    """Directly updates DB without using the Agent, and auto-dispatches pending requests."""
    data = request.json
    item = data.get("item_name")
    qty = int(data.get("quantity", 0))
    
    try:
        conn = sqlite3.connect(DB_PATH)
        # 1. Update Stock
        conn.execute("UPDATE inventory SET quantity = quantity + ? WHERE item_name = ?", (qty, item))
        # 2. Log Action for Audit (still in DB for record-keeping)
        conn.execute(
            "INSERT INTO requests (item_name, quantity, location, status, urgency, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (item, qty, "Warehouse", "ADMIN_ACTION", "NORMAL", f"Manual Restock by Supervisor")
        )
        conn.commit()
        
        # Fetch new total
        new_total = conn.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item,)).fetchone()[0]
        conn.close()
        
        # Log to supervisor activity log
        log_supervisor_activity(f"ADMIN_ACTION: Restocked {item} by {qty}. Total: {new_total}", "success")
        
        # 3. Process any pending dispatch requests for this item
        import tools_client
        dispatch_messages = tools_client.process_pending_dispatches(item)
        
        # Log dispatch results
        for msg in dispatch_messages:
            log_supervisor_activity(msg, "system")
        
        # Build response message
        response_msg = f"Restocked {item} by {qty}. Total: {new_total}"
        if dispatch_messages:
            response_msg += f"\n\n{len(dispatch_messages)} pending request(s) auto-dispatched."
        
        return jsonify({"success": True, "message": response_msg, "dispatches": dispatch_messages})
    except Exception as e:
        log_supervisor_activity(f"ADMIN_ACTION ERROR: Failed to restock {item} - {str(e)}", "error")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/admin/add_item", methods=["POST"])
def admin_add_item():
    """Directly adds item to DB without Agent."""
    data = request.json
    item = data.get("item_name")
    qty = int(data.get("quantity", 0))
    
    try:
        conn = sqlite3.connect(DB_PATH)
        # 1. Add Item
        conn.execute("INSERT INTO inventory (item_name, quantity) VALUES (?, ?)", (item, qty))
        # 2. Log (still in DB for record-keeping)
        conn.execute(
            "INSERT INTO requests (item_name, quantity, location, status, urgency, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (item, qty, "Warehouse", "ADMIN_ACTION", "NORMAL", f"New Item Created")
        )
        conn.commit()
        conn.close()
        
        # Log to supervisor activity log
        log_supervisor_activity(f"ADMIN_ACTION: Created item '{item}' with {qty} units", "success")
        
        return jsonify({"success": True, "message": f"Created item '{item}' with {qty} units."})
    except Exception as e:
        log_supervisor_activity(f"ADMIN_ACTION ERROR: Failed to create item {item} - {str(e)}", "error")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/admin/resolve/<int:request_id>", methods=["POST"])
def admin_resolve(request_id):
    """Resolve an ACTION_REQUIRED request with buffer and auto-dispatch."""
    try:
        import tools_supervisor
        result = tools_supervisor.supervisor_resolve_action_required(request_id, buffer_multiplier=1.5)
        
        # Clean the result string for JSON (remove special characters, newlines)
        result_cleaned = result.replace('\n', ' ').replace('\r', ' ').strip()
        
        # Log to supervisor activity log
        log_supervisor_activity(f"RESOLVE: Request #{request_id} - {result_cleaned[:100]}", "success")
        
        # Check if there were auto-dispatches
        import tools_client
        # Get the item from the request
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        req = conn.execute("SELECT item_name FROM requests WHERE id = ?", (request_id,)).fetchone()
        conn.close()
        
        if req:
            item_name = req['item_name']
            # Process any pending dispatches (shouldn't be any, but check)
            dispatch_messages = tools_client.process_pending_dispatches(item_name)
            
            return jsonify({
                "success": True,
                "message": result_cleaned,
                "dispatches": dispatch_messages
            })
        else:
            return jsonify({
                "success": True,
                "message": result_cleaned,
                "dispatches": []
            })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        log_supervisor_activity(f"RESOLVE ERROR: Request #{request_id} - {str(e)}", "error")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    initialize_adk_agents()
    threading.Thread(target=agent_worker, daemon=True).start()
    app.run(port=5000, debug=True, use_reloader=False)