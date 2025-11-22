import asyncio
import os
import sqlite3
import base64
import queue
import threading
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google.genai import types
import client_agents

load_dotenv()
app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "relief_logistics.db")
TASK_QUEUE = queue.Queue()
JOB_RESULTS = {}

def agent_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def run_task(job):
        runner = client_agents.SUPERVISOR_RUNNER if job["persona"] == "supervisor" else client_agents.VICTIM_RUNNER
        session_id = job.get("session_id", "default")
        
        if "text" in job: msg = types.Content(role="user", parts=[types.Part(text=job["text"])])
        elif "audio" in job:
            try:
                _, encoded = job["audio"].split(",", 1)
                msg = types.Content(role="user", parts=[types.Part(inline_data=types.Blob(mime_type="audio/webm", data=base64.b64decode(encoded)))])
            except: return "Audio Error"
        else: return "No Content"
        
        return await client_agents.run_agent_query(runner, job["persona"], session_id, msg)

    while True:
        job = TASK_QUEUE.get()
        if job is None: break
        res = loop.run_until_complete(run_task(job))
        if job["client_id"] not in JOB_RESULTS: JOB_RESULTS[job["client_id"]] = []
        JOB_RESULTS[job["client_id"]].append({"task_name": job["task_name"], "output": res, "persona": job["persona"]})

@app.route("/")
def victim(): return render_template("victim_chat.html")
@app.route("/supervisor")
def supervisor(): return render_template("supervisor_dashboard.html")

@app.route("/api/submit_task", methods=["POST"])
def submit():
    TASK_QUEUE.put(request.json)
    return jsonify({"status": "queued"})

@app.route("/api/get_results/<cid>", methods=["GET"])
def results(cid):
    return jsonify({"results": JOB_RESULTS.pop(cid, [])})

@app.route("/api/supervisor_data", methods=["GET"])
def data():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        inv = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
        req = [dict(r) for r in conn.execute("SELECT * FROM requests WHERE status='PENDING' OR status='ACTION_REQUIRED' ORDER BY urgency DESC").fetchall()]
        conn.close()
        return jsonify({"inventory": inv, "requests": req})
    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    client_agents.initialize_adk_agents()
    threading.Thread(target=agent_worker, daemon=True).start()
    app.run(port=5000, debug=True, use_reloader=False)