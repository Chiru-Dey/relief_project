import reflex as rx
import asyncio
import os
import sqlite3
import uuid
import threading
import base64
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# --- CONFIGURATION ---
DB_PATH = "../relief_logistics.db"
MANAGER_URL = "http://localhost:8001"
APP_NAME = "relief_app"

# --- GLOBAL SHARED STATE ---
GLOBAL_JOB_STORE = {}
GLOBAL_SESSION_SERVICE = InMemorySessionService()

# --- WORKER FUNCTION ---
def background_agent_worker(client_id: str, persona: str, command: str, task_name: str):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if "GOOGLE_API_KEY" not in os.environ:
            raise ValueError("GOOGLE_API_KEY not found")

        retry = types.HttpRetryOptions(attempts=3, initial_delay=1)
        proxy = RemoteA2aAgent(
            name="relief_manager", 
            description="Hub", 
            agent_card=f"{MANAGER_URL}{AGENT_CARD_WELL_KNOWN_PATH}"
        )
        
        valid_items = "water_bottles, food_packs"
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            rows = conn.execute("SELECT item_name FROM inventory").fetchall()
            conn.close()
            valid_items = ", ".join([r[0] for r in rows])
        except: pass

        if persona == "supervisor":
            agent = LlmAgent(
                model=Gemini(model="gemini-2.5-flash", retry_options=retry),
                name="supervisor",
                instruction=f"""
                You are a Relief Operation Supervisor.
                Current Valid Inventory Items: [{valid_items}]
                
                CRITICAL RULES:
                1. Delegation: You have NO direct DB access. You MUST ask 'relief_manager' to perform actions.
                2. BATCH OPERATIONS: Use batch tools for multiple items.
                """,
                sub_agents=[proxy]
            )
        else:
            agent = LlmAgent(
                model=Gemini(model="gemini-2.5-flash", retry_options=retry),
                name="victim",
                instruction=f"""
                You are Victim Support. Valid Items: [{valid_items}]
                1. Map generic terms (e.g., "water") to specific DB items ("water_bottles").
                2. Delegate to 'relief_manager' to place requests.
                """,
                sub_agents=[proxy]
            )
            
        runner = Runner(agent=agent, app_name=APP_NAME, session_service=GLOBAL_SESSION_SERVICE)
        session_id = f"{persona}_bg_session_{client_id}" 

        async def run_logic():
            try: await runner.session_service.create_session(app_name=APP_NAME, user_id=persona, session_id=session_id)
            except: pass

            if command.startswith("AUDIO:"):
                try:
                    base64_str = command.split("AUDIO:", 1)[1]
                    if "," in base64_str: base64_str = base64_str.split(",", 1)[1]
                    audio_bytes = base64.b64decode(base64_str)
                    msg = types.Content(role="user", parts=[types.Part(inline_data=types.Blob(mime_type="audio/wav", data=audio_bytes))])
                except Exception as e:
                    return f"Error decoding audio: {e}"
            else:
                msg = types.Content(role="user", parts=[types.Part(text=command)])

            final_res = "..."
            try:
                async for event in runner.run_async(user_id=persona, session_id=session_id, new_message=msg):
                    if event.is_final_response() and event.content:
                        final_res = event.content.parts[0].text
            except Exception as e:
                final_res = f"Agent Error: {str(e)}"
            return final_res

        result_text = loop.run_until_complete(run_logic())
        loop.close()

        if client_id not in GLOBAL_JOB_STORE: GLOBAL_JOB_STORE[client_id] = {"results": []}
        GLOBAL_JOB_STORE[client_id]["results"].append({
            "task_name": task_name, "output": result_text, "persona": persona
        })

    except Exception as e:
        if client_id not in GLOBAL_JOB_STORE: GLOBAL_JOB_STORE[client_id] = {"results": []}
        GLOBAL_JOB_STORE[client_id]["results"].append({
            "task_name": task_name, "output": f"Critical Error: {str(e)}", "persona": persona
        })


class State(rx.State):
    """The shared application state and logic."""

    inventory: list[dict] = []
    requests: list[dict] = []
    logs: list[str] = ["System initialized."]
    is_add_modal_open: bool = False
    is_restock_modal_open: bool = False
    selected_item_for_restock: str = ""
    new_item_name: str = ""
    new_item_qty: str = "0" 
    restock_qty: str = "0"
    supervisor_input: str = ""
    chat_history: list[dict] = [{"role": "assistant", "content": "Hello. How can I help?"}]
    input_text: str = ""
    
    my_client_id: str = str(uuid.uuid4())
    task_queue: list[str] = []
    is_recording: bool = False
    audio_data_bridge: str = ""

    @rx.var
    def current_task_name(self) -> str:
        if self.task_queue:
            count = len(self.task_queue)
            if count > 1: return f"{self.task_queue[0]} (+{count-1})"
            return self.task_queue[0]
        return ""

    @rx.var
    def is_working(self) -> bool:
        return len(self.task_queue) > 0

    # --- POLLING HANDLER (FIXED SIGNATURE) ---
    # date=None handles the positional arg from rx.moment
    # **kwargs catches any internal event args to prevent crashes
    async def check_job_results(self, date=None, **kwargs):
        """Checks global store for finished threads."""
        await self._fetch_data_internal()

        if self.my_client_id in GLOBAL_JOB_STORE:
            store = GLOBAL_JOB_STORE[self.my_client_id]
            if "results" in store and store["results"]:
                for res in store["results"]:
                    task = res["task_name"]
                    out = res["output"]
                    
                    if res["persona"] == "supervisor":
                        self.logs.append(f"✅ {task}: {out}")
                    else:
                        self.chat_history.append({"role": "assistant", "content": out})
                    
                    if task in self.task_queue:
                        self.task_queue.remove(task)
                store["results"] = []

    # --- INTERNAL DB FETCH ---
    async def _fetch_data_internal(self):
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            conn.row_factory = sqlite3.Row
            self.inventory = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
            self.requests = [dict(r) for r in conn.execute("SELECT * FROM requests WHERE status='PENDING'").fetchall()]
            conn.close()
        except: pass

    # --- THREAD DISPATCHER ---
    def _dispatch(self, command: str, task_name: str, persona: str = "supervisor"):
        self.task_queue.append(task_name)
        if persona == "supervisor":
            self.logs.append(f"⏳ Queued: {task_name}")
        elif persona == "victim" and command and not command.startswith("AUDIO:"):
            self.chat_history.append({"role": "user", "content": command})

        t = threading.Thread(
            target=background_agent_worker, 
            args=(self.my_client_id, persona, command, task_name)
        )
        t.start()

    # --- ACTIONS ---
    def refresh_dashboard_data(self): pass

    def submit_supervisor_query(self):
        if not self.supervisor_input: return
        cmd = self.supervisor_input
        self.supervisor_input = "" 
        self._dispatch(cmd, f"Chat: {cmd[:10]}...")

    def approve_request(self, req_id: int):
        self._dispatch(f"Approve request ID {req_id}", f"Approving Req {req_id}")

    def reject_request(self, req_id: int):
        self._dispatch(f"Reject request ID {req_id}", f"Rejecting Req {req_id}")

    def submit_restock(self):
        try: qty = int(self.restock_qty)
        except: qty = 0
        self.is_restock_modal_open = False
        item = self.selected_item_for_restock
        self._dispatch(f"Add {qty} units to inventory for item '{item}'", f"Restocking {item}")

    def submit_add_item(self):
        try: qty = int(self.new_item_qty)
        except: qty = 0
        self.is_add_modal_open = False
        name = self.new_item_name
        self._dispatch(f"Add new item '{name}' with {qty} units", f"Adding {name}")

    def send_message(self):
        if not self.input_text: return
        txt = self.input_text
        self.input_text = ""
        self._dispatch(txt, "Support Agent Thinking...", persona="victim")

    def start_recording(self):
        self.is_recording = True
        return rx.call_script("startRecording()")

    def stop_recording(self):
        self.is_recording = False
        return rx.call_script("stopRecording()")

    def set_audio_data_bridge(self, data: str):
        self.audio_data_bridge = data 
        if data:
            self.chat_history.append({"role": "user", "content": "🎤 [Voice Message Sent]"})
            self._dispatch(f"AUDIO:{data}", "Processing Voice...", persona="victim")

    # --- EXPLICIT SETTERS ---
    def open_restock_modal(self, item_name: str):
        self.selected_item_for_restock = item_name
        self.is_restock_modal_open = True
    def set_input_text(self, val: str): self.input_text = val
    def set_is_add_modal_open(self, val: bool): self.is_add_modal_open = val
    def set_is_restock_modal_open(self, val: bool): self.is_restock_modal_open = val
    def set_restock_qty(self, val: str): self.restock_qty = val
    def set_new_item_name(self, val: str): self.new_item_name = val
    def set_new_item_qty(self, val: str): self.new_item_qty = val
    def set_supervisor_input(self, val: str): self.supervisor_input = val