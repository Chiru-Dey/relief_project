import reflex as rx
from ..state import State

def victim_ui():
    return rx.container(
        rx.heading("🚑 Disaster Relief Support", size="7", margin_bottom="4", align="center"),
        
        # CHAT HISTORY AREA
        rx.card(
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(
                        State.chat_history,
                        lambda msg: rx.box(
                            rx.text(msg["content"], 
                                    bg=rx.cond(msg["role"] == "user", "blue.100", "gray.100"),
                                    padding="3",
                                    border_radius="lg"),
                            align_self=rx.cond(msg["role"] == "user", "end", "start"),
                            margin_bottom="2",
                            max_width="80%"
                        )
                    ),
                    # LOADING INDICATOR INSIDE CHAT
                    rx.cond(
                        State.is_victim_loading,
                        rx.hstack(
                            rx.spinner(size="1"),
                            rx.text("Support Agent is contacting HQ...", color="gray", size="2", style={"fontStyle": "italic"}),
                            spacing="2",
                            margin_top="2"
                        )
                    )
                ),
                height="60vh",
                padding="4",
            ),
            margin_bottom="4"
        ),

        # INPUT AREA
        rx.hstack(
            rx.input(
                placeholder="Type your request...",
                value=State.input_text,
                on_change=State.set_input_text,
                on_key_down=lambda e: rx.cond(e == "Enter", State.send_message(), None),
                width="100%",
                # DISABLE INPUT IF LOADING
                disabled=State.is_victim_loading 
            ),
            rx.button(
                rx.cond(State.is_victim_loading, rx.spinner(size="1"), rx.icon("send")), 
                on_click=State.send_message,
                # DISABLE BUTTON IF LOADING
                disabled=State.is_victim_loading
            ),
        ),
        
        rx.divider(margin_y="4"),
        
        # VOICE INPUT AREA
        rx.box(
            rx.text("🎙️ Voice Mode (Gemini 2.5)", size="2", weight="bold", color="gray", margin_bottom="2"),
            rx.cond(
                State.is_victim_loading,
                rx.center(rx.spinner(), padding="4", border="1px dotted gray", border_radius="md"),
                rx.upload(
                    rx.button(rx.icon("mic"), "Upload Voice Message / Recording", color_scheme="purple", variant="surface", width="100%"),
                    id="upload1",
                    multiple=False,
                    accept={"audio/*": [".mp3", ".wav", ".m4a", ".ogg"]},
                    max_files=1,
                    on_drop=State.handle_voice_upload,
                    border="1px dotted gray",
                    padding="2"
                ),
            )
        ),

        max_width="600px",
        padding_y="6"
    )