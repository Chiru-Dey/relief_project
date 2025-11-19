import reflex as rx
from ..state import State

def supervisor_ui():
    return rx.box(
        rx.heading("👮 Relief Operations Dashboard", size="8", margin_bottom="4"),
        
        # METRICS ROW
        rx.flex(
            # CARD 1: Total Items
            rx.card(
                rx.vstack(
                    rx.text("Total Inventory Items", size="2", weight="medium", color="gray"),
                    rx.heading(
                        rx.cond(State.inventory, State.inventory.length(), 0),
                        size="7"
                    ),
                    spacing="2"
                ),
                width="30%"
            ),
            
            # CARD 2: Pending Requests
            rx.card(
                rx.vstack(
                    rx.text("Pending Approvals", size="2", weight="medium", color="gray"),
                    rx.heading(
                        rx.cond(State.requests, State.requests.length(), 0),
                        size="7",
                        color_scheme="red"
                    ),
                    spacing="2"
                ),
                width="30%"
            ),
            
            rx.button("🔄 Refresh Data", on_click=State.refresh_dashboard_data, size="4", margin_top="2"),
            spacing="4",
            width="100%",
            margin_bottom="6"
        ),

        rx.grid(
            # INVENTORY COLUMN
            rx.box(
                rx.hstack(
                    rx.heading("📦 Inventory", size="5"),
                    rx.button("➕ Add Item", on_click=lambda: State.set_is_add_modal_open(True)),
                    justify="between",
                    margin_bottom="2"
                ),
                rx.foreach(
                    State.inventory,
                    lambda item: rx.card(
                        rx.hstack(
                            rx.text(item["item_name"], weight="bold", size="4"),
                            rx.spacer(),
                            # FIX APPLIED BELOW: .to(int)
                            rx.badge(
                                f"{item['quantity']} units", 
                                color_scheme=rx.cond(item["quantity"].to(int) < 20, "red", "green"), 
                                size="3"
                            ),
                            rx.button("Restock", size="1", on_click=lambda: State.open_restock_modal(item["item_name"]))
                        ),
                        margin_bottom="2"
                    )
                ),
            ),
            
            # REQUESTS COLUMN
            rx.box(
                rx.heading("🚨 Request Queue", size="5", margin_bottom="2"),
                rx.cond(
                    State.requests.length() == 0,
                    rx.text("No pending requests.", color="gray"),
                    rx.foreach(
                        State.requests,
                        lambda req: rx.card(
                            rx.vstack(
                                rx.hstack(
                                    rx.badge(f"ID {req['id']}"),
                                    rx.badge(req['urgency'], color_scheme=rx.cond(req['urgency'] == 'CRITICAL', "red", "gray")),
                                    rx.text(f"{req['quantity']}x {req['item_name']}", weight="bold"),
                                ),
                                rx.text(f"Loc: {req['location']}", size="2"),
                                rx.hstack(
                                    rx.button("✅ Approve", color_scheme="green", on_click=lambda: State.approve_request(req["id"])),
                                    rx.button("❌ Reject", color_scheme="red", on_click=lambda: State.reject_request(req["id"])),
                                    spacing="2",
                                    margin_top="2"
                                ),
                                align="start"
                            ),
                            margin_bottom="2"
                        )
                    )
                )
            ),
            columns="2",
            spacing="6"
        ),

        # ACTIVITY LOG
        rx.divider(margin_y="4"),
        rx.text("Agent Activity Log", weight="bold"),
        rx.scroll_area(
            rx.vstack(rx.foreach(State.logs, lambda log: rx.text(log, font_family="monospace", size="1"))),
            height="150px", bg="gray.50", padding="2", border_radius="md"
        ),

        # --- MODALS ---
        
        # Restock Modal
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("Restock Item"),
                rx.text(f"Update stock for: {State.selected_item_for_restock}"),
                rx.input(placeholder="New Quantity", on_change=State.set_restock_qty, type="number"),
                rx.flex(
                    rx.dialog.close(rx.button("Cancel", color_scheme="gray")),
                    rx.dialog.close(rx.button("Update", on_click=State.submit_restock)),
                    spacing="3", margin_top="4", justify="end",
                ),
            ),
            open=State.is_restock_modal_open,
            on_open_change=State.set_is_restock_modal_open,
        ),

        # Add Item Modal
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("Add New Item"),
                rx.input(placeholder="Item Name", on_change=State.set_new_item_name),
                rx.input(placeholder="Initial Quantity", on_change=State.set_new_item_qty, type="number", margin_top="2"),
                rx.flex(
                    rx.dialog.close(rx.button("Cancel", color_scheme="gray")),
                    rx.dialog.close(rx.button("Create", on_click=State.submit_add_item)),
                    spacing="3", margin_top="4", justify="end",
                ),
            ),
            open=State.is_add_modal_open,
            on_open_change=State.set_is_add_modal_open,
        ),
        
        padding="6",
        on_mount=State.refresh_dashboard_data
    )