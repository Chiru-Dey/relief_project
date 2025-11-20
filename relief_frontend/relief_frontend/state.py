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

# --- LOAD ENV VARS ---
load_dotenv()

# --- CONFIG ---
DB_PATH = "../relief_logistics.db"
MANAGER_URL = "http://localhost:8001"
APP_NAME = "relief_app"

# Global Memory Service for persistence
GLOBAL_SESSION_SERVICE = InMemorySessionService()

class State(rx.State):
    """The shared application state and logic."""

    def _get_valid_items_string(self) -> str:
        # ... (Keep existing logic) ...
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            rows = conn.execute("SELECT item_name FROM inventory").fetchall()
            conn.close()
            return ", ".join([r[0] for r in rows])
        except:
            return "water_bottles, food_packs, medical_kits"

    def _get_runner(self, persona: str):
        # ... (Keep existing logic) ...
        # (Ensure your instructions mentioned delegation as per previous fix)
        if "GOOGLE_API_KEY" not in os.environ:
            print("❌ Error: GOOGLE_API_KEY not found.")

        retry_config = types.HttpRetryOptions(attempts=3, initial_delay=1)
        
        remote_proxy = RemoteA2aAgent(
            name="relief_manager",
            description="Central hub.",
            agent_card=f"{MANAGER_URL}{AGENT_CARD_WELL_KNOWN_PATH}"
        )

        valid_items = self._get_valid_items_string()

        if persona == "supervisor":
            agent = LlmAgent(
                model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
                name="supervisor",
                instruction=f"""
                You are a Relief Operation Supervisor.
                Current Valid Inventory Items: [{valid_items}]
                
                Your Job: Manage inventory and approvals efficiently.
                
                CRITICAL RULES:
                1. **Delegation**: You have NO direct DB access. Ask 'relief_manager' to do everything.
                
                2. **BATCH OPERATIONS (PREFERRED)**:
                   - If the user wants to approve/reject multiple items (e.g., "Approve all", "Reject IDs 1, 2, and 5"):
                     a. First, call `supervisor_view_pending_requests` to get the IDs.
                     b. Then, use `supervisor_batch_decide_requests` with a JSON list of IDs (e.g., "[1, 2, 5]").
                   
                   - If the user wants to restock/add multiple items (e.g., "Restock everything to 100", "Add tents and heaters"):
                     a. If "all", call `admin_view_full_inventory` to get names.
                     b. Use `admin_batch_update_inventory` with a JSON dictionary (e.g., '{{"water_bottles": 100, "food": 100}}').
                     c. This tool handles both updating existing items and creating new ones.
                
                3. **Single Operations**:
                   - Use single tools (approve_request, restock_item) only for individual tasks.
                """,
                sub_agents=[remote_proxy]
            )
        else:
            agent = LlmAgent(
                model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
                name="victim_support",
                instruction=f"""
                You are a compassionate Disaster Relief Support agent. 
                Current Valid Inventory Items: [{valid_items}]
                
                Your Job:
                1. Help victims get supplies immediately.
                2. INTELLIGENT MAPPING: Map generic terms (e.g. "water") to valid items ("water_bottles").
                3. Ask 'relief_manager' to fulfill requests.
                """,
                sub_agents=[remote_proxy]
            )

        return Runner(agent=agent, app_name=APP_NAME, session_service=GLOBAL_SESSION_SERVICE)

    # ==========================
    # SUPERVISOR LOGIC
    # ==========================
    inventory: list[dict] = []
    requests: list[dict] = []
    logs: list[str] = ["System initialized."]
    
    is_add_modal_open: bool = False
    is_restock_modal_open: bool = False
    selected_item_for_restock: str = ""
    
    new_item_name: str = ""
    new_item_qty: str = "0" 
    restock_qty: str = "0"
    
    # --- NEW: Supervisor Chat Input ---
    supervisor_input: str = ""

    async def refresh_dashboard_data(self):
        # ... (Keep existing logic) ...
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            conn.row_factory = sqlite3.Row
            inv_rows = conn.execute("SELECT * FROM inventory").fetchall()
            self.inventory = [dict(r) for r in inv_rows]
            req_rows = conn.execute("SELECT * FROM requests WHERE status='PENDING'").fetchall()
            self.requests = [dict(r) for r in req_rows]
            conn.close()
        except Exception as e:
            self.logs.append(f"DB Error: {str(e)}")

    async def _run_supervisor_command(self, command: str):
        self.logs.append(f"👮 CMD: {command}")
        runner = self._get_runner("supervisor")
        
        session_id = "supervisor_session_main"
        try:
            await runner.session_service.create_session(app_name=APP_NAME, user_id="sup", session_id=session_id)
        except: pass
        
        msg = types.Content(role="user", parts=[types.Part(text=command)])
        response_text = "..."
        
        async for event in runner.run_async(user_id="sup", session_id=session_id, new_message=msg):
            if event.is_final_response() and event.content:
                response_text = event.content.parts[0].text
        
        self.logs.append(f"🤖 AGENT: {response_text}")
        await self.refresh_dashboard_data()

    # --- NEW: Supervisor Chat Handler ---
    async def submit_supervisor_query(self):
        if not self.supervisor_input: return
        cmd = self.supervisor_input
        self.supervisor_input = "" # Clear input immediately
        await self._run_supervisor_command(cmd)

    # Actions (Buttons)
    async def approve_request(self, req_id: int): await self._run_supervisor_command(f"Approve request ID {req_id}")
    async def reject_request(self, req_id: int): await self._run_supervisor_command(f"Reject request ID {req_id}")
    
    def open_restock_modal(self, item_name: str):
        self.selected_item_for_restock = item_name
        self.is_restock_modal_open = True

    async def submit_restock(self):
        try: qty = int(self.restock_qty)
        except ValueError: qty = 0
        await self._run_supervisor_command(f"Restock {self.selected_item_for_restock} to {qty}")
        self.is_restock_modal_open = False

    async def submit_add_item(self):
        try: qty = int(self.new_item_qty)
        except ValueError: qty = 0
        await self._run_supervisor_command(f"Add new item '{self.new_item_name}' with {qty} units")
        self.is_add_modal_open = False

    # ==========================
    # VICTIM LOGIC (Keep as is)
    # ==========================
    chat_history: list[dict] = [{"role": "assistant", "content": "Hello. You can type or upload a voice message."}]
    input_text: str = ""
    victim_session_id: str = "victim_session_main"

    async def handle_voice_upload(self, files: list[rx.UploadFile]):
        runner = self._get_runner("victim")
        try: await runner.session_service.create_session(app_name=APP_NAME, user_id="vic", session_id=self.victim_session_id)
        except: pass

        for file in files:
            upload_data = await file.read()
            self.chat_history.append({"role": "user", "content": "🎤 [Audio Message Sent]"})
            msg = types.Content(role="user", parts=[types.Part(inline_data=types.Blob(mime_type="audio/mp3", data=upload_data))])
            
            response_text = ""
            async for event in runner.run_async(user_id="vic", session_id=self.victim_session_id, new_message=msg):
                if event.is_final_response() and event.content:
                    response_text = event.content.parts[0].text
            self.chat_history.append({"role": "assistant", "content": response_text})

    async def send_message(self):
        if not self.input_text: return
        text = self.input_text
        self.chat_history.append({"role": "user", "content": text})
        self.input_text = ""
        
        runner = self._get_runner("victim")
        try: await runner.session_service.create_session(app_name=APP_NAME, user_id="vic", session_id=self.victim_session_id)
        except: pass

        msg = types.Content(role="user", parts=[types.Part(text=text)])
        response_text = ""
        async for event in runner.run_async(user_id="vic", session_id=self.victim_session_id, new_message=msg):
            if event.is_final_response() and event.content:
                response_text = event.content.parts[0].text
        self.chat_history.append({"role": "assistant", "content": response_text})

    # ==========================
    # EXPLICIT SETTERS
    # ==========================
    def set_input_text(self, val: str): self.input_text = val
    def set_is_add_modal_open(self, val: bool): self.is_add_modal_open = val
    def set_is_restock_modal_open(self, val: bool): self.is_restock_modal_open = val
    def set_restock_qty(self, val: str): self.restock_qty = val
    def set_new_item_name(self, val: str): self.new_item_name = val
    def set_new_item_qty(self, val: str): self.new_item_qty = val
    
    # --- NEW SETTER ---
    def set_supervisor_input(self, val: str): self.supervisor_input = val