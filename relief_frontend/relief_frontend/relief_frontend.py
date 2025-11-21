import reflex as rx
from .pages.supervisor import supervisor_ui
from .pages.victim import victim_ui

# Initialize App
app = rx.App(theme=rx.theme(appearance="dark"))

# Add Pages (Routes)
app.add_page(victim_ui, route="/", title="Victim Support")
app.add_page(supervisor_ui, route="/supervisor", title="HQ Supervisor")