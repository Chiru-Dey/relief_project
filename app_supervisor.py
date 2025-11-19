import streamlit as st
import asyncio
import uuid
import pandas as pd
import sqlite3
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# --- CONFIGURATION ---
st.set_page_config(page_title="Relief HQ Supervisor", page_icon="👮", layout="wide")
retry_config = types.HttpRetryOptions(attempts=5, exp_base=7, initial_delay=1, http_status_codes=[429, 500, 503])

# --- DIRECT DB ACCESS (For Dashboard Viz only) ---
# Note: The Agent doesn't use this, but the UI uses it for read-only charts.
def get_inventory_df():
    conn = sqlite3.connect("relief_logistics.db")
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    return df

def get_pending_requests_df():
    conn = sqlite3.connect("relief_logistics.db")
    df = pd.read_sql_query("SELECT * FROM requests WHERE status='PENDING'", conn)
    conn.close()
    return df

# --- AGENT SETUP ---
@st.cache_resource
def get_runner():
    remote_manager_proxy = RemoteA2aAgent(
        name="relief_manager",
        description="The central hub that has inventory data and can dispatch supplies.",
        agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}"
    )

    supervisor_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="relief_supervisor",
        instruction="""
        You are the Relief Operation Supervisor.
        You manage logistics, approve requests, and modify inventory.
        Be concise and direct.
        """,
        sub_agents=[remote_manager_proxy]
    )
    
    runner = Runner(
        agent=supervisor_agent, 
        app_name="relief_supervisor_app", 
        session_service=InMemorySessionService()
    )
    return runner

runner = get_runner()

# --- SESSION STATE ---
if "sup_session_id" not in st.session_state:
    st.session_state.sup_session_id = str(uuid.uuid4())
    asyncio.run(runner.session_service.create_session(
        app_name=runner.app_name, 
        user_id="web_admin", 
        session_id=st.session_state.sup_session_id
    ))

if "sup_messages" not in st.session_state:
    st.session_state.sup_messages = [
        {"role": "assistant", "content": "HQ Supervisor Terminal Online. Waiting for commands."}
    ]

# --- UI LAYOUT ---
st.title("👮 Relief Operations Command Center")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📊 Live Inventory")
    try:
        inv_df = get_inventory_df()
        st.dataframe(inv_df, use_container_width=True)
        st.bar_chart(inv_df.set_index("item_name")["quantity"])
    except Exception as e:
        st.error("Database not found. Is manager_server.py running?")

with col2:
    st.subheader("🚨 Pending Approvals")
    try:
        req_df = get_pending_requests_df()
        if not req_df.empty:
            st.dataframe(req_df[["id", "item_name", "quantity", "location", "urgency"]], use_container_width=True)
            st.warning(f"{len(req_df)} requests waiting for approval.")
        else:
            st.success("No pending requests.")
    except:
        pass

st.divider()

# --- CHAT INTERFACE ---
st.subheader("💬 Command Interface")

for message in st.session_state.sup_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("E.g., 'Approve request 5', 'Add 50 tents', 'Restock water to 200'"):
    # 1. Display User Message
    st.session_state.sup_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Get Agent Response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("Processing Command..."):
            user_msg = types.Content(role="user", parts=[types.Part(text=prompt)])
            
            async def get_response():
                response_text = ""
                async for event in runner.run_async(
                    user_id="web_admin", 
                    session_id=st.session_state.sup_session_id, 
                    new_message=user_msg
                ):
                    if event.is_final_response() and event.content:
                        response_text = event.content.parts[0].text
                return response_text

            full_response = asyncio.run(get_response())
            message_placeholder.markdown(full_response)
            
            # Force refresh of charts after command execution
            st.rerun()
    
    # 3. Save history
    st.session_state.sup_messages.append({"role": "assistant", "content": full_response})