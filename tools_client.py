import database

def check_inventory(item_name: str) -> str:
    stock = database.get_item_stock(item_name)
    if stock >= 0: return f"SUCCESS: {item_name} has {stock} units."
    else:
        all_items = database.get_all_item_names()
        return f"ERROR: Item '{item_name}' not found. Valid items: {', '.join(all_items)}."

def request_relief(item_name: str, quantity: int, location: str, is_critical: bool = False) -> str:
    current_stock = database.get_item_stock(item_name)
    if current_stock == -1: return f"ERROR: Item '{item_name}' does not exist."
    if current_stock < quantity: return f"ERROR: Insufficient stock. Only {current_stock} available."

    urgency = "CRITICAL" if is_critical else "NORMAL"
    new_stock = current_stock - quantity
    database.update_stock(item_name, new_stock)
    req_id = database.create_request(item_name, quantity, location, "AI_APPROVED", urgency, "Auto-approved")
    return f"SUCCESS: Request ID {req_id} approved. Dispatched {quantity} {item_name}."

def check_request_status(request_id: int) -> str:
    req = database.get_request_by_id(request_id)
    if not req: return f"ERROR: Request ID {request_id} not found."
    return f"SUCCESS: Request {req['id']} Status: {req['status']}."

def log_inventory_gap(item_name: str, location: str) -> str:
    suggestion = f"User at {location} requested '{item_name}'. Suggestion: Add '{item_name}' to inventory."
    database.create_request("INVENTORY_GAP", 0, location, "ACTION_REQUIRED", "NORMAL", suggestion)
    return f"SUCCESS: Logged gap for '{item_name}'."