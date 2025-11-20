import reflex as rx
from ..state import State

# --- THEME COLORS ---
BG_COLOR = "#131314"       
CARD_BG = "#1E1F20"        
USER_BUBBLE = "#2F2F2F"    
USER_MSG_COLOR = "#2563EB" 
AI_MSG_COLOR = "#F3F4F6"   

def message_bubble(msg: dict):
    """Renders a chat message. User = Bubble, AI = Clean Text."""
    is_user = msg["role"] == "user"
    
    return rx.flex(
        # Avatar / Icon
        rx.cond(
            ~is_user,
            rx.box(
                rx.icon("sparkles", color="#448AFF", size=20), 
                margin_top="10px",
                margin_right="12px"
            )
        ),
        
        # Content Bubble
        rx.box(
            rx.markdown(msg["content"]),
            color=rx.cond(is_user, "white", "black"),
            bg=rx.cond(is_user, USER_MSG_COLOR, AI_MSG_COLOR),
            padding_x=rx.cond(is_user, "20px", "0"),
            padding_y=rx.cond(is_user, "12px", "0"),
            border_radius="24px",
            max_width="100%",
            font_size="16px",
            line_height="1.6"
        ),
        
        justify=rx.cond(is_user, "end", "start"),
        margin_bottom="24px",
        width="100%"
    )

def input_bar():
    """The floating 'Pill' input bar mimicking Gemini/ChatGPT."""
    return rx.box(
        # Hidden Audio Bridge for JS
        rx.input(
            id="audio-bridge", 
            value=State.audio_data_bridge, 
            on_change=State.set_audio_data_bridge,
            display="none"
        ),

        rx.hstack(
            # 1. ATTACHMENT ICON (Plus)
            rx.icon_button(
                rx.icon("plus", size=20),
                variant="ghost",
                color="gray",
                border_radius="full",
                size="3"
            ),

            # 2. DYNAMIC CENTER
            rx.cond(
                State.is_recording,
                # Recording State
                rx.hstack(
                    rx.box(class_name="animate-pulse", width="12px", height="12px", bg="red.500", border_radius="full"),
                    rx.text("Listening...", color="white", weight="medium"),
                    rx.spacer(),
                    width="100%",
                    align="center",
                    padding_x="4"
                ),
                # Text Input State
                rx.input(
                    placeholder="Ask for help, supplies, or status...",
                    value=State.input_text,
                    on_change=State.set_input_text,
                    on_key_down=lambda e: rx.cond(e == "Enter", State.send_message(), None),
                    variant="surface",
                    background="transparent",
                    border="none",
                    outline="none",
                    color="white",
                    width="100%",
                    font_size="16px",
                    _placeholder={"color": "#9CA3AF"}
                ),
            ),

            # 3. ACTIONS
            rx.cond(
                State.is_recording,
                # Stop Button
                rx.icon_button(
                    rx.icon("square", size=18, fill="white"),
                    on_click=State.stop_recording,
                    color_scheme="red",
                    size="3",
                    border_radius="full"
                ),
                # Mic / Send Toggle
                rx.cond(
                    State.input_text == "",
                    # Show Mic if empty
                    rx.icon_button(
                        rx.icon("mic", size=20),
                        on_click=State.start_recording,
                        variant="ghost",
                        color="white",
                        size="3",
                        border_radius="full"
                    ),
                    # Show Send if has text
                    rx.icon_button(
                        rx.icon("arrow-up", size=20),
                        on_click=State.send_message,
                        # 🔥 FIX: Use bg/color instead of color_scheme="white"
                        bg="white", 
                        color="black",
                        size="3",
                        border_radius="full"
                    )
                )
            ),
            
            bg=CARD_BG,
            border="1px solid #333",
            border_radius="full",
            padding="8px",
            width="100%",
            max_width="750px",
            box_shadow="0 4px 20px rgba(0,0,0,0.4)"
        ),
        
        rx.center(
            rx.text(
                "Gemini 2.5 Agent can make mistakes. Double-check important info.", 
                color="#6B7280", 
                size="1",
                margin_top="12px"
            ),
            width="100%"
        ),
        
        position="fixed",
        bottom="20px",
        left="0",
        right="0",
        padding_x="20px",
        z_index="50"
    )

def victim_ui():
    return rx.box(
        # SCRIPTS
        rx.script(src="/audio_recorder.js"),
        # Poller from State
        rx.moment(interval=1000, on_change=State.check_job_results, display="none"),

        # MAIN CONTAINER
        rx.center(
            rx.vstack(
                # 1. HEADER / EMPTY STATE
                rx.cond(
                    State.chat_history.length() <= 1,
                    rx.vstack(
                        rx.heading("Hello, Survivor", size="9", weight="medium", color="#6b6b6b"),
                        rx.heading("How can I help you today?", size="9", weight="medium", color="#444746"),
                        spacing="2",
                        margin_top="20vh",
                        opacity="0.4"
                    ),
                    rx.box()
                ),

                # 2. CHAT SCROLL AREA
                rx.box(
                    rx.vstack(
                        rx.foreach(State.chat_history, message_bubble),
                        
                        # Floating Spinner
                        rx.cond(
                            State.is_victim_loading,
                            rx.hstack(
                                rx.spinner(size="1", color="white"),
                                rx.text("Thinking...", color="gray", size="2"),
                                margin_top="10px"
                            )
                        ),
                        
                        rx.box(height="150px") 
                    ),
                    width="100%",
                    max_width="750px",
                    padding_x="4",
                    padding_top="40px",
                    flex="1",
                    overflow_y="auto",
                    style={"scrollbarWidth": "none"},
                    id="chat-container"
                ),

                height="100vh",
                width="100%",
                align="center"
            ),
            width="100%",
            height="100vh",
            bg=BG_COLOR
        ),
        
        # 3. FLOATING INPUT
        input_bar()
    )