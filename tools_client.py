import database

def check_inventory(item_name: str) -> str:
    """Checks the current stock of a specific item."""
    stock = database.get_item_stock(item_name)
    if stock >= 0:
        return f"SUCCESS: {item_name} has {stock} units available."
    else:
        # Give the agent a list of valid options to recover from hallucinations
        all_items = database.get_all_item_names()
        return f"ERROR: Item '{item_name}' not found. Valid items are: {', '.join(all_items)}."

def request_relief(item_name: str, quantity: int, location: str, is_critical: bool = False, force_manual_approval: bool = False) -> str:
    """
    Processes a relief request for a SINGLE item.
    The status is determined by the calling agent's logic.
    """
    # 1. Validation
    current_stock = database.get_item_stock(item_name)
    urgency = "CRITICAL" if is_critical else "NORMAL"
    
    if current_stock == -1: 
        return f"ERROR: Item '{item_name}' does not exist in the database."
    if current_stock < quantity: 
        return f"ERROR: Insufficient stock for {item_name}. Only {current_stock} available."

    # 2. Execute based on agent's decision
    if force_manual_approval:
        req_id = database.create_request(
            item_name, quantity, location, "PENDING", urgency, "Flagged for manual review by Triage Agent"
        )
        return f"SUCCESS: Request ID {req_id} created and sent for manual approval."
    
    else:
        # Auto-approve path
        new_stock = current_stock - quantity
        database.update_stock(item_name, new_stock)
        req_id = database.create_request(
            item_name, quantity, location, "AI_APPROVED", urgency, "Auto-approved by Triage Agent."
        )
        return f"SUCCESS: Request ID {req_id} automatically approved. Dispatched {quantity} {item_name} to {location}. New Stock: {new_stock}."

def check_request_status(request_id: int) -> str:
    """Allows a user to check the status of a previous request ID."""
    req = database.get_request_by_id(request_id)
    if not req:
        return f"ERROR: Request ID {request_id} not found."
    
    return f"SUCCESS: Request ID {req['id']} has status: {req['status']}."