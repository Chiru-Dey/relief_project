import reflex as rx
from ..state import State

def victim_ui():
    return rx.container(
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
                        State.is_victim_loading,
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

        # INPUT
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
        max_width="600px", padding_y="6"
    )