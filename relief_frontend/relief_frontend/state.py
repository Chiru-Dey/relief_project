import reflex as rx
import asyncio
import os
import sqlite3
import uuid
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

DB_PATH = "../relief_logistics.db"
MANAGER_URL = "http://localhost:8001"
APP_NAME = "relief_app"

# We need a fresh session service for background tasks
GLOBAL_SESSION_SERVICE = InMemorySessionService()

class State(rx.State):
    """The shared application state and logic."""

    # --- QUEUE VISUALIZATION ---
    task_queue: list[str] = []

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

    # --- AGENT HELPERS (Safe for Background) ---
    def _get_valid_items_string(self) -> str:
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            rows = conn.execute("SELECT item_name FROM inventory").fetchall()
            conn.close()
            return ", ".join([r[0] for r in rows])
        except:
            return "water_bottles, food_packs"

    def _get_runner_instance(self, persona: str):
        if "GOOGLE_API_KEY" not in os.environ:
            print("❌ Error: GOOGLE_API_KEY not found.")
        
        retry = types.HttpRetryOptions(attempts=3, initial_delay=1)
        proxy = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"{MANAGER_URL}{AGENT_CARD_WELL_KNOWN_PATH}")
        items = self._get_valid_items_string()

        if persona == "supervisor":
            agent = LlmAgent(
                model=Gemini(model="gemini-2.5-flash", retry_options=retry),
                name="supervisor",
                instruction=f"""
                You are a Relief Operation Supervisor. Valid Items: [{items}]. 
                CRITICAL:
                1. Delegation: You have NO direct DB access. Ask 'relief_manager'.
                2. Use BATCH tools (`admin_batch_update_inventory`, `supervisor_batch_decide_requests`) for multiple items.
                """,
                sub_agents=[proxy]
            )
        else:
            agent = LlmAgent(
                model=Gemini(model="gemini-2.5-flash", retry_options=retry),
                name="victim",
                instruction=f"Victim Support. Items: [{items}]. Map generic terms. Delegate to 'relief_manager'.",
                sub_agents=[proxy]
            )
        return Runner(agent=agent, app_name=APP_NAME, session_service=GLOBAL_SESSION_SERVICE)

    # --- UI STATE ---
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
    is_victim_loading: bool = False

    # --- SYNC ACTIONS (Immediate UI Updates) ---

    async def refresh_dashboard_data(self):
        """Standard event handler to refresh data."""
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            conn.row_factory = sqlite3.Row
            self.inventory = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
            self.requests = [dict(r) for r in conn.execute("SELECT * FROM requests WHERE status='PENDING'").fetchall()]
            conn.close()
        except Exception as e:
            self.logs.append(f"DB Error: {e}")

    # --- 🔥 BACKGROUND TASKS (The Modern Way) ---

    @rx.event(background=True)
    async def run_agent_task(self, command: str, task_name: str, persona: str = "supervisor"):
        """
        Runs entirely in the background.
        Uses `async with self` to push updates to the UI.
        """
        # 1. LOCK UI: Add to Queue
        async with self:
            self.task_queue.append(task_name)
            if persona == "supervisor":
                self.logs.append(f"⏳ Started: {task_name}")
            elif persona == "victim":
                self.is_victim_loading = True

        # 2. HEAVY LIFTING (No UI Lock)
        runner = self._get_runner_instance(persona)
        session_id = f"{persona}_bg_session"
        
        # For audio handling, we would handle bytes here, simplified to text for brevity
        msg = types.Content(role="user", parts=[types.Part(text=command)])
        final_text = "..."
        
        try:
            try: await runner.session_service.create_session(app_name=APP_NAME, user_id=persona, session_id=session_id)
            except: pass

            async for event in runner.run_async(user_id=persona, session_id=session_id, new_message=msg):
                if event.is_final_response() and event.content:
                    final_text = event.content.parts[0].text
        except Exception as e:
            final_text = f"Agent Error: {e}"

        # 3. UNLOCK UI: Update Data & Remove from Queue
        async with self:
            if persona == "supervisor":
                self.logs.append(f"✅ {task_name}: {final_text}")
                # Reuse the refresh logic
                await self.refresh_dashboard_data()
            else:
                self.chat_history.append({"role": "assistant", "content": final_text})
                self.is_victim_loading = False
            
            if task_name in self.task_queue:
                self.task_queue.remove(task_name)

    # --- EVENT HANDLERS (Triggers) ---

    def submit_supervisor_query(self):
        if not self.supervisor_input: return
        cmd = self.supervisor_input
        self.supervisor_input = "" 
        return State.run_agent_task(cmd, f"Chat: {cmd[:10]}...")

    def approve_request(self, req_id: int):
        return State.run_agent_task(f"Approve request ID {req_id}", f"Approving Req {req_id}")

    def reject_request(self, req_id: int):
        return State.run_agent_task(f"Reject request ID {req_id}", f"Rejecting Req {req_id}")

    def submit_restock(self):
        try: qty = int(self.restock_qty)
        except: qty = 0
        self.is_restock_modal_open = False
        item = self.selected_item_for_restock
        return State.run_agent_task(f"Add {qty} units to inventory for item '{item}'", f"Restocking {item}")

    def submit_add_item(self):
        try: qty = int(self.new_item_qty)
        except: qty = 0
        self.is_add_modal_open = False
        name = self.new_item_name
        return State.run_agent_task(f"Add new item '{name}' with {qty} units", f"Adding {name}")

    def send_message(self):
        if not self.input_text: return
        txt = self.input_text
        self.input_text = ""
        self.chat_history.append({"role": "user", "content": txt})
        # Return the background event
        return State.run_agent_task(txt, "Support Agent Thinking...", persona="victim")

    async def handle_voice_upload(self, files: list[rx.UploadFile]):
        for file in files:
            # In background tasks, reading file bytes is tricky. 
            # For simplicity in this demo, we acknowledge receipt.
            # Real implementation requires uploading to a temp path first.
            self.chat_history.append({"role": "user", "content": "🎤 [Audio Processing Not Supported in BG Mode Yet]"})

    # --- SETTERS ---
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