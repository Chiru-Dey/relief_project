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

# Global Service for session persistence
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

    def _get_runner_instance(self, persona: str):
        """Helper to create a Runner instance. Safe to call from background threads."""
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

    # --- SYNC DATA FETCH ---
    async def _fetch_data_now(self):
        """Updates local state from DB. Must be called inside a lock."""
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            conn.row_factory = sqlite3.Row
            self.inventory = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
            self.requests = [dict(r) for r in conn.execute("SELECT * FROM requests WHERE status='PENDING'").fetchall()]
            conn.close()
        except Exception as e:
            self.logs.append(f"DB Error: {e}")

    async def refresh_dashboard_data(self):
        """Public handler for manual refresh."""
        await self._fetch_data_now()


    # --- 🔥 BACKGROUND WORKER (THE FIX) ---
    
    @rx.background
    async def handle_background_command(self, command: str, task_name: str):
        """
        Runs in the background. Does NOT block the UI.
        Uses 'async with self' only when it needs to update the screen.
        """
        # 1. Update Queue UI (Start)
        async with self:
            self.task_queue.append(task_name)
            self.logs.append(f"⏳ Started: {task_name}")

        # 2. Run Agent Logic (Heavy lifting - No UI Lock here)
        runner = self._get_runner_instance("supervisor")
        session_id = "supervisor_session_bg"
        
        # Create session if needed (safe to ignore error)
        try: await runner.session_service.create_session(app_name=APP_NAME, user_id="sup", session_id=session_id)
        except: pass
        
        msg = types.Content(role="user", parts=[types.Part(text=command)])
        final_text = "..."
        
        try:
            async for event in runner.run_async(user_id="sup", session_id=session_id, new_message=msg):
                if event.is_final_response() and event.content:
                    final_text = event.content.parts[0].text
        except Exception as e:
            final_text = f"Agent Error: {str(e)}"

        # 3. Update UI (Finish)
        async with self:
            self.logs.append(f"✅ {task_name}: {final_text}")
            if task_name in self.task_queue:
                self.task_queue.remove(task_name)
            
            # Refresh data to show results (e.g. removed request / updated stock)
            await self._fetch_data_now()


    # --- SUPERVISOR ACTIONS (Non-Blocking Triggers) ---

    def submit_supervisor_query(self):
        if not self.supervisor_input: return
        cmd = self.supervisor_input
        self.supervisor_input = "" # Clear UI immediately
        # Fire background task
        return State.handle_background_command(cmd, f"Chat: {cmd[:10]}...")

    def approve_request(self, req_id: int):
        return State.handle_background_command(f"Approve request ID {req_id}", f"Approving Req {req_id}")

    def reject_request(self, req_id: int):
        return State.handle_background_command(f"Reject request ID {req_id}", f"Rejecting Req {req_id}")

    def submit_restock(self):
        try: qty = int(self.restock_qty)
        except: qty = 0
        self.is_restock_modal_open = False # Close UI immediately
        item = self.selected_item_for_restock
        return State.handle_background_command(f"Add {qty} units to inventory for item '{item}'", f"Restocking {item}")

    def submit_add_item(self):
        try: qty = int(self.new_item_qty)
        except: qty = 0
        self.is_add_modal_open = False # Close UI immediately
        name = self.new_item_name
        return State.handle_background_command(f"Add new item '{name}' with {qty} units", f"Adding {name}")

    
    # --- VICTIM BACKGROUND WORKER ---

    @rx.background
    async def handle_victim_chat_bg(self, user_text: str = None, audio_data = None):
        """Background handler for victim chat."""
        async with self:
            self.is_victim_loading = True
            if user_text:
                self.chat_history.append({"role": "user", "content": user_text})
            else:
                self.chat_history.append({"role": "user", "content": "🎤 [Audio Sent]"})

        runner = self._get_runner_instance("victim")
        try: await runner.session_service.create_session(app_name=APP_NAME, user_id="vic", session_id=self.victim_session_id)
        except: pass

        if audio_data:
             msg = types.Content(role="user", parts=[types.Part(inline_data=types.Blob(mime_type="audio/mp3", data=audio_data))])
        else:
             msg = types.Content(role="user", parts=[types.Part(text=user_text)])

        response = "..."
        try:
            async for event in runner.run_async(user_id="vic", session_id=self.victim_session_id, new_message=msg):
                if event.is_final_response() and event.content: response = event.content.parts[0].text
        except Exception as e:
            response = f"Error: {e}"

        async with self:
            self.chat_history.append({"role": "assistant", "content": response})
            self.is_victim_loading = False


    def send_message(self):
        if not self.input_text: return
        txt = self.input_text
        self.input_text = ""
        return State.handle_victim_chat_bg(user_text=txt)

    async def handle_voice_upload(self, files: list[rx.UploadFile]):
        for file in files:
            data = await file.read()
            return State.handle_victim_chat_bg(audio_data=data)

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