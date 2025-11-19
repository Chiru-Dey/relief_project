import database

def check_inventory(item_name: str) -> str:
    """Checks the current stock of a specific item."""
    stock = database.get_item_stock(item_name)
    if stock >= 0:
        return f"{item_name}: {stock} units available."
    else:
        # Helper to show what IS available
        all_items = database.get_all_items()
        names = ", ".join([r['item_name'] for r in all_items])
        return f"Error: '{item_name}' not found. We stock: {names}."

def request_relief(item_name: str, quantity: int, location: str, is_critical: bool = False) -> str:
    """
    Processes a relief request.
    Args:
        is_critical: Set to True if this is a life-threatening emergency.
    """
    current_stock = database.get_item_stock(item_name)
    urgency = "CRITICAL" if is_critical else "NORMAL"
    
    # Validation
    if current_stock == -1: 
        return f"Error: Item '{item_name}' does not exist."
    if current_stock < quantity: 
        return f"Error: Insufficient stock. Only {current_stock} available."

    # Logic: 
    # 1. If Critical, ALWAYS queue for supervisor (so they see the emergency flag), unless small stock auto-approve logic applies?
    #    Let's say Critical large orders jump the queue in visualization but still need approval.
    # 2. Standard > 10 rule applies.
    
    needs_approval = quantity > 10
    
    if needs_approval:
        req_id = database.create_request(item_name, quantity, location, "PENDING", urgency, "Awaiting Approval")
        return f"Request ID {req_id} created. Status: PENDING ({urgency} priority)."
    else:
        new_stock = current_stock - quantity
        database.update_stock(item_name, new_stock)
        database.create_request(item_name, quantity, location, "APPROVED", urgency, "Auto-approved")
        return f"APPROVED. Dispatched {quantity} {item_name}. New Stock: {new_stock}."

def check_request_status(request_id: int) -> str:
    """Allows a user to check the status of a previous request ID."""
    req = database.get_request_by_id(request_id)
    if not req:
        return f"Error: Request ID {request_id} not found."
    
    return f"Request {request_id} Status: {req['status']} (Item: {req['item_name']}, Location: {req['location']})"