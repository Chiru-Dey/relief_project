import streamlit as st
import asyncio
import uuid
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# --- CONFIGURATION ---
st.set_page_config(page_title="Disaster Relief Support", page_icon="🚑")
retry_config = types.HttpRetryOptions(attempts=5, exp_base=7, initial_delay=1, http_status_codes=[429, 500, 503])

# --- AGENT SETUP (Cached to avoid reloading on every interaction) ---
@st.cache_resource
def get_runner():
    print("🔌 Connecting to Relief Manager Hub...")
    remote_manager_proxy = RemoteA2aAgent(
        name="relief_manager",
        description="The central hub that has inventory data and can dispatch supplies.",
        agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}"
    )

    support_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="victim_support",
        instruction="""
        You are a compassionate Disaster Relief Support agent. 
        Your goal is to help victims get water, food, or medical kits.
        
        1. Ask for their location if not provided.
        2. Use the 'relief_manager' tool to check if items are available or to place a request.
        3. If the manager says it needs approval, explain that to the user gently.
        """,
        sub_agents=[remote_manager_proxy]
    )
    
    runner = Runner(
        agent=support_agent, 
        app_name="relief_support_app", 
        session_service=InMemorySessionService()
    )
    return runner

runner = get_runner()

# --- SESSION STATE ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    # Initialize session in ADK
    asyncio.run(runner.session_service.create_session(
        app_name=runner.app_name, 
        user_id="web_victim", 
        session_id=st.session_state.session_id
    ))

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello. I am the Disaster Relief Support. Please tell me what supplies you need and your location."}
    ]

# --- UI LAYOUT ---
st.title("🚑 Disaster Relief Support")
st.markdown("Use this chat to request **Food**, **Water**, or **Medical Kits**.")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Logic
if prompt := st.chat_input("I need water at Sector 7..."):
    # 1. Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Get Agent Response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        with st.spinner("Contacting Logistics Hub..."):
            user_msg = types.Content(role="user", parts=[types.Part(text=prompt)])
            
            # Run async loop in sync Streamlit environment
            async def get_response():
                response_text = ""
                async for event in runner.run_async(
                    user_id="web_victim", 
                    session_id=st.session_state.session_id, 
                    new_message=user_msg
                ):
                    if event.is_final_response() and event.content:
                        response_text = event.content.parts[0].text
                return response_text

            full_response = asyncio.run(get_response())
            message_placeholder.markdown(full_response)
    
    # 3. Save Assistant message
    st.session_state.messages.append({"role": "assistant", "content": full_response})