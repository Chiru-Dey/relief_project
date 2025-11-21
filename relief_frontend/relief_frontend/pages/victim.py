import reflex as rx
from ..state import State

# --- THEME COLORS ---
BG_COLOR = "#131314"           
INPUT_BAR_BG = "#1E1F20"       
USER_MSG_BG = "#2F2F2F"        
TEXT_COLOR = "#E3E3E3"         
ACCENT_COLOR = "#448AFF"       

# --- JS FOR ENTER KEY ---
JS_ENTER_HANDLER = """
document.addEventListener('keydown', function(e) {
    if (e.target.id === 'chat-input' && e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('send-trigger').click();
    }
});
"""

# --- SHARED TEXT STYLES ---
# Ensures the hidden replica and visible textarea match perfectly
TEXT_AREA_STYLE = {
    "padding": "20px 12px",
    "fontSize": "16px",
    "lineHeight": "1.5",
    "fontFamily": "inherit",
    "whiteSpace": "pre-wrap", 
    "wordBreak": "break-word",
    "gridColumn": "1",
    "gridRow": "1",
    "width": "100%",
    "minHeight": "24px",     
}

def message_bubble(msg: dict):
    """Renders a chat message."""
    is_user = msg["role"] == "user"
    
    return rx.flex(
        rx.cond(
            ~is_user,
            rx.box(
                rx.icon("sparkles", color=ACCENT_COLOR, size=24, stroke_width=1.5),
                margin_top="6px",
                margin_right="16px",
            )
        ),
        rx.box(
            rx.markdown(msg["content"]),
            bg=rx.cond(is_user, USER_MSG_BG, "transparent"),
            color=TEXT_COLOR,
            padding_x=rx.cond(is_user, "20px", "0"),
            padding_y=rx.cond(is_user, "12px", "0"),
            border_radius="24px",
            width="fit-content", 
            max_width="100%",
            font_size="16px",
            line_height="1.6",
        ),
        width="100%",
        justify=rx.cond(is_user, "end", "start"),
        margin_bottom="24px",
    )

def auto_expanding_input():
    """The CSS Grid Stack Trick for Auto-Expanding Input."""
    return rx.box(
        rx.grid(
            # 1. HIDDEN REPLICA (Pushes height)
            rx.text(
                State.input_text + "\u200b", 
                visibility="hidden",
                style=TEXT_AREA_STYLE,
            ),

            # 2. ACTUAL INPUT (Overlays)
            rx.text_area(
                id="chat-input",
                placeholder="Ask anything...",
                value=State.input_text,
                on_change=State.set_input_text,
                
                variant="soft",
                background="transparent",
                border="none",
                outline="none",
                color="white",
                resize="none",
                overflow="hidden",
                
                style=TEXT_AREA_STYLE,
                
                _placeholder={"color": "#888888", "opacity": 1}, 
                _focus={"border": "none", "outline": "none", "box_shadow": "none", "background": "transparent"}
            ),
            
            columns="1",
            width="100%",
            align_items="stretch"
        ),
        flex="1" 
    )

def floating_input_bar():
    """The Container for Icons + Input."""
    return rx.box(
        rx.input(id="audio-bridge", value=State.audio_data_bridge, on_change=State.set_audio_data_bridge, display="none"),
        rx.button(id="send-trigger", on_click=State.send_message, display="none"),

        # --- THE PILL CONTAINER ---
        rx.flex(
            # 1. Left Icon
            rx.box(
                rx.icon_button(
                    rx.icon("plus", size=24),
                    variant="ghost", color="#C4C7C5", 
                    border_radius="full", size="3",
                    _hover={"bg": "#333"}
                ),
                padding_bottom="12px",
                align_self="end",
                margin_right="8px"
            ),

            # 2. Input Area
            rx.box(
                rx.cond(
                    State.is_recording,
                    # Recording UI
                    rx.hstack(
                        rx.box(class_name="animate-pulse", width="10px", height="10px", bg="#ef4444", border_radius="full"),
                        rx.text("Listening...", color="#ef4444", weight="medium", font_size="16px"),
                        align="center", padding_y="20px", width="100%"
                    ),
                    # Standard Input
                    auto_expanding_input()
                ),
                flex="1", 
            ),

            # 3. Right Actions
            rx.box(
                rx.cond(
                    State.is_recording,
                    rx.icon_button(
                        rx.icon("square", size=20, fill="white"),
                        on_click=State.stop_recording,
                        bg="#ef4444", color="white", size="3", border_radius="full",
                        _hover={"bg": "#dc2626"}
                    ),
                    rx.cond(
                        State.input_text == "",
                        rx.icon_button(
                            rx.icon("mic", size=24),
                            on_click=State.start_recording,
                            variant="ghost", color="white", size="3", border_radius="full",
                            _hover={"bg": "#333"}
                        ),
                        rx.icon_button(
                            rx.icon("arrow-up", size=20),
                            on_click=State.send_message,
                            bg="white", color="black", size="3", border_radius="8px",
                            _hover={"bg": "#e5e5e5"}
                        )
                    )
                ),
                padding_bottom="12px",
                align_self="end",
                margin_left="8px"
            ),
            
            # Container Styles
            bg=INPUT_BAR_BG,
            border="1px solid #444746",
            border_radius="32px",
            width="100%",
            min_height="64px", 
            padding_x="16px",
            
            align="end",
            justify="between"
        ),
        
        rx.center(
            rx.text("Gemini can make mistakes. Double-check info.", color="#6B7280", size="1", margin_top="10px"),
            width="100%"
        ),
        
        position="fixed",
        bottom="24px",
        left="50%",
        transform="translateX(-50%)",
        width="min(92%, 750px)",
        z_index="50"
    )

def victim_ui():
    return rx.box(
        rx.script(src="/audio_recorder.js"),
        rx.script(JS_ENTER_HANDLER),
        rx.moment(interval=1000, on_change=State.check_job_results, display="none"),

        # --- MAIN CONTAINER ---
        rx.center(
            rx.vstack(
                # 1. EMPTY STATE
                rx.cond(
                    State.chat_history.length() <= 0,
                    rx.vstack(
                        rx.heading(
                            "Hello, Survivor", 
                            size="9", 
                            font_weight="bold",
                            background_image="linear-gradient(to right, #4285f4, #9b72cb, #d96570)",
                            background_clip="text",
                            color="transparent",
                            line_height="1.2",
                            padding_bottom="10px"
                        ),
                        rx.heading("How can I help you today?", size="8", color="#444746", font_weight="medium"),
                        align="start",
                        spacing="2",
                        margin_top="35vh",
                    ),
                    rx.box()
                ),

                # 2. CHAT SCROLL AREA
                rx.box(
                    rx.vstack(
                        rx.foreach(State.chat_history, message_bubble),
                        rx.cond(
                            State.is_victim_loading,
                            rx.hstack(
                                rx.icon("sparkles", color=ACCENT_COLOR, size=24, class_name="animate-pulse"),
                                rx.text("Thinking...", color="gray", size="2"),
                                spacing="3", margin_top="10px"
                            )
                        ),
                        rx.box(height="180px") 
                    ),
                    width="100%",
                    max_width="800px",
                    padding_x="20px",
                    padding_top="20px",
                    flex="1",
                    overflow_y="auto",
                    style={"scrollbarWidth": "none"},
                    id="chat-scroll"
                ),

                height="100vh",
                width="100%",
                align="center"
            ),
            bg=BG_COLOR,
            height="100vh",
            width="100%"
        ),
        
        floating_input_bar()
    )