import reflex as rx
from ..state import State

def victim_ui():
    return rx.fragment(
        # LOAD JS FROM ASSETS
        rx.script(src="/audio_recorder.js"),
        
        # POLLER
        rx.moment(interval=1000, on_change=State.check_job_results, display="none"),
        
        rx.container(
            rx.heading("🚑 Disaster Relief Support", size="7", margin_bottom="4", align="center"),
            
            # CHAT HISTORY
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
                        # QUEUE INDICATOR
                        rx.cond(
                            State.is_working,
                            rx.hstack(
                                rx.spinner(size="1", color_scheme="blue"),
                                rx.text("Support Agent is working...", color="gray", size="2", style={"fontStyle": "italic"}),
                                spacing="2", margin_top="2"
                            )
                        )
                    ),
                    height="60vh", padding="4",
                ),
                margin_bottom="4"
            ),

            # TEXT INPUT
            rx.hstack(
                rx.input(
                    placeholder="Type your request...",
                    value=State.input_text,
                    on_change=State.set_input_text,
                    on_key_down=lambda e: rx.cond(e == "Enter", State.send_message(), None),
                    width="100%"
                ),
                rx.button(rx.icon("send"), on_click=State.send_message),
            ),
            
            rx.divider(margin_y="4"),
            
            # --- REAL VOICE INPUT ---
            rx.center(
                rx.vstack(
                    rx.text("🎙️ Voice Mode (Gemini 2.5)", size="2", weight="bold", color="gray"),
                    
                    # HIDDEN BRIDGE INPUT
                    # JS writes base64 here -> calls State.set_audio_data_bridge
                    rx.input(
                        id="audio-bridge", 
                        value=State.audio_data_bridge, 
                        on_change=State.set_audio_data_bridge,
                        display="none"
                    ),

                    # MIC BUTTON CONTROLS
                    rx.cond(
                        State.is_recording,
                        # STOP BUTTON
                        rx.vstack(
                            rx.button(
                                rx.icon("square"), " Stop & Send", 
                                color_scheme="red", 
                                variant="surface",
                                width="200px",
                                on_click=State.stop_recording, # Calls JS stopRecording
                                cursor="pointer"
                            ),
                            rx.text("🔴 Listening...", color="red", size="2", weight="bold", class_name="animate-pulse")
                        ),
                        # START BUTTON
                        rx.button(
                            rx.icon("mic"), " Press to Speak", 
                            color_scheme="purple", 
                            variant="surface",
                            width="200px",
                            on_click=State.start_recording, # Calls JS startRecording
                            cursor="pointer"
                        ),
                    ),
                    align="center",
                    spacing="2"
                ),
                padding_y="4"
            ),
            max_width="600px", padding_y="6"
        )
    )