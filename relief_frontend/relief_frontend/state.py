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

GLOBAL_SESSION_SERVICE = InMemorySessionService()

class State(rx.State):
    """The shared application state and logic."""

    # --- QUEUE MANAGEMENT ---
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

    # --- CONFIG & HELPERS ---
    def _get_valid_items_string(self) -> str:
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            rows = conn.execute("SELECT item_name FROM inventory").fetchall()
            conn.close()
            return ", ".join([r[0] for r in rows])
        except:
            return "water_bottles, food_packs"

    def _get_runner(self, persona: str):
        if "GOOGLE_API_KEY" not in os.environ:
            print("❌ Error: GOOGLE_API_KEY not found.")
        
        retry = types.HttpRetryOptions(attempts=3, initial_delay=1)
        proxy = RemoteA2aAgent(name="relief_manager", description="Hub", agent_card=f"{MANAGER_URL}{AGENT_CARD_WELL_KNOWN_PATH}")
        items = self._get_valid_items_string()

        if persona == "supervisor":
            agent = LlmAgent(
                model=Gemini(model="gemini-2.5-flash", retry_options=retry),
                name="supervisor",
                instruction=f"Supervisor Agent. Valid Items: [{items}]. Delegate DB tasks to 'relief_manager'. Use Batch tools.",
                sub_agents=[proxy]
            )
        else:
            agent = LlmAgent(
                model=Gemini(model="gemini-2.5-flash", retry_options=retry),
                name="victim",
                instruction=f"Victim Support. Valid Items: [{items}]. Map terms to DB items. Delegate to 'relief_manager'.",
                sub_agents=[proxy]
            )
        return Runner(agent=agent, app_name=APP_NAME, session_service=GLOBAL_SESSION_SERVICE)

    # --- DATA ---
    inventory: list[dict] = []
    requests: list[dict] = []
    logs: list[str] = ["System initialized."]
    
    # UI Inputs
    is_add_modal_open: bool = False
    is_restock_modal_open: bool = False
    selected_item_for_restock: str = ""
    new_item_name: str = ""
    new_item_qty: str = "0" 
    restock_qty: str = "0"
    supervisor_input: str = ""
    
    # Victim Inputs
    chat_history: list[dict] = [{"role": "assistant", "content": "Hello. How can I help?"}]
    input_text: str = ""
    victim_session_id: str = "victim_session_main"

    # --- PURE ASYNC DATA FETCH ---
    async def _fetch_data_internal(self):
        """Updates local state variables from DB."""
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            conn.row_factory = sqlite3.Row
            self.inventory = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
            self.requests = [dict(r) for r in conn.execute("SELECT * FROM requests WHERE status='PENDING'").fetchall()]
            conn.close()
        except Exception as e:
            self.logs.append(f"DB Error: {e}")

    # --- 🔥 THE BACKGROUND ENGINE ---
    
    async def _run_agent_background_task(self, command: str, task_name: str, persona: str = "supervisor"):
        """
        This runs OUTSIDE the main event loop lock.
        It interacts with the LLM, then locks state briefly to update UI.
        """
        runner = self._get_runner(persona)
        session_id = f"{persona}_session_bg"
        
        # Agent Execution (Slow part - No UI Lock)
        msg = types.Content(role="user", parts=[types.Part(text=command)])
        final_text = "..."
        
        try:
            # Ensure session
            try: await runner.session_service.create_session(app_name=APP_NAME, user_id=persona, session_id=session_id)
            except: pass

            async for event in runner.run_async(user_id=persona, session_id=session_id, new_message=msg):
                if event.is_final_response() and event.content:
                    final_text = event.content.parts[0].text
        except Exception as e:
            final_text = f"Agent Error: {str(e)}"

        # UI Update (Fast part - Acquires Lock)
        async with self:
            if persona == "supervisor":
                self.logs.append(f"✅ {task_name}: {final_text}")
                await self._fetch_data_internal()
            
            # Remove from queue
            if task_name in self.task_queue:
                self.task_queue.remove(task_name)

    # --- SUPERVISOR ACTIONS (FIRE AND FORGET) ---

    async def refresh_dashboard_data(self):
        await self._fetch_data_internal()

    async def submit_supervisor_query(self):
        if not self.supervisor_input: return
        cmd = self.supervisor_input
        self.supervisor_input = "" 
        
        # 1. Update Queue UI immediately
        self.task_queue.append(f"Chat: {cmd[:10]}...")
        
        # 2. Fire background task (Does not wait)
        asyncio.create_task(self._run_agent_background_task(cmd, f"Chat: {cmd[:10]}..."))

    async def approve_request(self, req_id: int):
        task_name = f"Approving Req {req_id}"
        self.task_queue.append(task_name)
        asyncio.create_task(self._run_agent_background_task(f"Approve request ID {req_id}", task_name))

    async def reject_request(self, req_id: int):
        task_name = f"Rejecting Req {req_id}"
        self.task_queue.append(task_name)
        asyncio.create_task(self._run_agent_background_task(f"Reject request ID {req_id}", task_name))

    async def submit_restock(self):
        try: qty = int(self.restock_qty)
        except: qty = 0
        self.is_restock_modal_open = False
        item = self.selected_item_for_restock
        
        task_name = f"Restocking {item}"
        self.task_queue.append(task_name)
        
        cmd = f"Add {qty} units to inventory for item '{item}'"
        asyncio.create_task(self._run_agent_background_task(cmd, task_name))

    async def submit_add_item(self):
        try: qty = int(self.new_item_qty)
        except: qty = 0
        self.is_add_modal_open = False
        name = self.new_item_name
        
        task_name = f"Adding {name}"
        self.task_queue.append(task_name)
        
        cmd = f"Add new item '{name}' with {qty} units"
        asyncio.create_task(self._run_agent_background_task(cmd, task_name))

    # --- VICTIM ACTIONS (FIRE AND FORGET) ---

    async def _run_victim_bg(self, msg_content, task_name):
        runner = self._get_runner("victim")
        session_id = self.victim_session_id
        
        response = "..."
        try:
            try: await runner.session_service.create_session(app_name=APP_NAME, user_id="vic", session_id=session_id)
            except: pass

            async for event in runner.run_async(user_id="vic", session_id=session_id, new_message=msg_content):
                if event.is_final_response() and event.content: response = event.content.parts[0].text
        except Exception as e:
            response = f"Error: {e}"

        async with self:
            self.chat_history.append({"role": "assistant", "content": response})
            if task_name in self.task_queue:
                self.task_queue.remove(task_name)

    async def send_message(self):
        if not self.input_text: return
        txt = self.input_text
        self.input_text = ""
        
        # Update UI
        self.chat_history.append({"role": "user", "content": txt})
        self.task_queue.append("Support Agent Thinking...")
        
        # Fire Background
        msg = types.Content(role="user", parts=[types.Part(text=txt)])
        asyncio.create_task(self._run_victim_bg(msg, "Support Agent Thinking..."))

    async def handle_voice_upload(self, files: list[rx.UploadFile]):
        for file in files:
            data = await file.read()
            self.chat_history.append({"role": "user", "content": "🎤 [Audio Sent]"})
            self.task_queue.append("Processing Voice...")
            
            msg = types.Content(role="user", parts=[types.Part(inline_data=types.Blob(mime_type="audio/mp3", data=data))])
            asyncio.create_task(self._run_victim_bg(msg, "Processing Voice..."))

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