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
    
    # --- LOADING STATES (NEW) ---
    is_victim_loading: bool = False
    is_supervisor_loading: bool = False

    def _get_valid_items_string(self) -> str:
        try:
            abs_db_path = os.path.abspath(os.path.join(os.getcwd(), DB_PATH))
            conn = sqlite3.connect(abs_db_path)
            rows = conn.execute("SELECT item_name FROM inventory").fetchall()
            conn.close()
            return ", ".join([r[0] for r in rows])
        except:
            return "water_bottles, food_packs, medical_kits"

    def _get_runner(self, persona: str):
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
                CRITICAL RULES:
                1. Delegation: You have NO direct DB access. Ask 'relief_manager'.
                2. Batch Operations Preferred: Use batch tools for multiple items.
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
                2. INTELLIGENT MAPPING: Map generic terms to specific DB items automatically.
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
    supervisor_input: str = ""

    async def refresh_dashboard_data(self):
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
        """
        Run command with Loading State logic.
        Note the 'yield' statements - this updates UI progressively.
        """
        # 1. Start Loading
        self.is_supervisor_loading = True
        yield 

        self.logs.append(f"👮 CMD: {command}")
        runner = self._get_runner("supervisor")
        
        session_id = "supervisor_session_main"
        try: await runner.session_service.create_session(app_name=APP_NAME, user_id="sup", session_id=session_id)
        except: pass
        
        msg = types.Content(role="user", parts=[types.Part(text=command)])
        response_text = "..."
        
        # 2. Run Agent (Time consuming part)
        async for event in runner.run_async(user_id="sup", session_id=session_id, new_message=msg):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        # Optional: Show tool calls in logs for "working" effect
                        # self.logs.append(f"⚙️ Calling Tool: {part.function_call.name}")
                        pass

            if event.is_final_response() and event.content:
                response_text = event.content.parts[0].text
        
        self.logs.append(f"🤖 AGENT: {response_text}")
        
        # 3. Refresh Data
        await self.refresh_dashboard_data()
        
        # 4. Stop Loading
        self.is_supervisor_loading = False
        yield

    async def submit_supervisor_query(self):
        if not self.supervisor_input: return
        cmd = self.supervisor_input
        self.supervisor_input = "" 
        async for update in self._run_supervisor_command(cmd):
            yield update

    async def approve_request(self, req_id: int): 
        async for update in self._run_supervisor_command(f"Approve request ID {req_id}"):
            yield update
            
    async def reject_request(self, req_id: int): 
        async for update in self._run_supervisor_command(f"Reject request ID {req_id}"):
            yield update
    
    def open_restock_modal(self, item_name: str):
        self.selected_item_for_restock = item_name
        self.is_restock_modal_open = True

    async def submit_restock(self):
        try: qty = int(self.restock_qty)
        except ValueError: qty = 0
        
        self.is_restock_modal_open = False # Close modal first
        yield
        
        async for update in self._run_supervisor_command(f"Restock {self.selected_item_for_restock} to {qty}"):
            yield update

    async def submit_add_item(self):
        try: qty = int(self.new_item_qty)
        except ValueError: qty = 0
        
        self.is_add_modal_open = False # Close modal first
        yield

        async for update in self._run_supervisor_command(f"Add new item '{self.new_item_name}' with {qty} units"):
            yield update

    # ==========================
    # VICTIM LOGIC
    # ==========================
    chat_history: list[dict] = [{"role": "assistant", "content": "Hello. You can type or upload a voice message."}]
    input_text: str = ""
    victim_session_id: str = "victim_session_main"

    async def handle_voice_upload(self, files: list[rx.UploadFile]):
        # 1. Start Loading
        self.is_victim_loading = True
        yield

        runner = self._get_runner("victim")
        try: await runner.session_service.create_session(app_name=APP_NAME, user_id="vic", session_id=self.victim_session_id)
        except: pass

        for file in files:
            upload_data = await file.read()
            self.chat_history.append({"role": "user", "content": "🎤 [Audio Message Sent]"})
            yield # Update UI to show user message

            msg = types.Content(
                role="user", 
                parts=[types.Part(inline_data=types.Blob(mime_type="audio/mp3", data=upload_data))]
            )
            
            response_text = ""
            async for event in runner.run_async(user_id="vic", session_id=self.victim_session_id, new_message=msg):
                if event.is_final_response() and event.content:
                    response_text = event.content.parts[0].text
            
            self.chat_history.append({"role": "assistant", "content": response_text})
        
        # 2. Stop Loading
        self.is_victim_loading = False
        yield

    async def send_message(self):
        if not self.input_text: return
        
        # 1. Start Loading & Update UI
        text = self.input_text
        self.chat_history.append({"role": "user", "content": text})
        self.input_text = ""
        self.is_victim_loading = True
        yield
        
        runner = self._get_runner("victim")
        try: await runner.session_service.create_session(app_name=APP_NAME, user_id="vic", session_id=self.victim_session_id)
        except: pass

        msg = types.Content(role="user", parts=[types.Part(text=text)])
        response_text = ""
        async for event in runner.run_async(user_id="vic", session_id=self.victim_session_id, new_message=msg):
            if event.is_final_response() and event.content:
                response_text = event.content.parts[0].text
        
        self.chat_history.append({"role": "assistant", "content": response_text})
        
        # 2. Stop Loading
        self.is_victim_loading = False
        yield

    # ==========================
    # EXPLICIT SETTERS
    # ==========================
    def set_input_text(self, val: str): self.input_text = val
    def set_is_add_modal_open(self, val: bool): self.is_add_modal_open = val
    def set_is_restock_modal_open(self, val: bool): self.is_restock_modal_open = val
    def set_restock_qty(self, val: str): self.restock_qty = val
    def set_new_item_name(self, val: str): self.new_item_name = val
    def set_new_item_qty(self, val: str): self.new_item_qty = val
    def set_supervisor_input(self, val: str): self.supervisor_input = val