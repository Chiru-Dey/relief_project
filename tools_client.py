import database

def check_inventory(item_name: str) -> str:
    """Checks the current stock of a specific inventory item."""
    stock = database.get_item_stock(item_name)
    if stock >= 0:
        return f"SUCCESS: {item_name} has {stock} units."
    else:
        all_items = database.get_all_item_names()
        return f"ERROR: Item '{item_name}' not found. Valid items are: {', '.join(all_items)}."

def log_inventory_gap(item_name: str, quantity: int, location: str) -> str:
    """
    Logs that a user requested an item not in inventory (or insufficient stock).
    """
    suggestion = f"User at {location} needs {quantity}x '{item_name}'. Suggestion: Restock/Add '{item_name}'."
    database.create_request(
        item_name="INVENTORY_GAP",
        quantity=quantity,
        location=location,
        status="ACTION_REQUIRED",
        urgency="NORMAL",
        notes=suggestion
    )
    return f"Logged inventory gap for {quantity}x {item_name}."

def request_relief(item_name: str, quantity: int, location: str, is_critical: bool = False) -> str:
    """
    Processes a relief request. Handles Partial Fulfillment automatically.
    """
    current_stock = database.get_item_stock(item_name)
    
    # 1. Item doesn't exist
    if current_stock == -1: 
        log_inventory_gap(item_name, quantity, location)
        return f"ERROR: Item '{item_name}' does not exist. I have logged this gap for the supervisor."

    urgency = "CRITICAL" if is_critical else "NORMAL"

    # 2. Partial Fulfillment (The Fix)
    if current_stock < quantity:
        amount_sent = current_stock
        shortfall = quantity - current_stock
        
        # Send what we have (if any)
        if amount_sent > 0:
            database.update_stock(item_name, 0) # Empty the stock
            database.create_request(item_name, amount_sent, location, "AI_APPROVED", urgency, "Partial fulfillment (Stock exhausted)")
        
        # Log the rest
        log_inventory_gap(item_name, shortfall, location)
        
        if amount_sent > 0:
            return f"PARTIAL SUCCESS: We only had {amount_sent} {item_name}. These have been dispatched. The remaining {shortfall} have been logged as a priority gap for the supervisor."
        else:
            return f"FAILURE: We have 0 {item_name}. Logged as a gap for supervisor."

    # 3. Full Fulfillment
    else:
        new_stock = current_stock - quantity
        database.update_stock(item_name, new_stock)
        req_id = database.create_request(item_name, quantity, location, "AI_APPROVED", urgency, "Auto-approved")
        return f"SUCCESS: Request ID {req_id} approved. Dispatched {quantity} {item_name}. Remaining Stock: {new_stock}."

def check_request_status(request_id: int) -> str:
    """Allows a user to check the status of a previous request ID."""
    req = database.get_request_by_id(request_id)
    if not req: return f"ERROR: Request ID {request_id} not found."
    return f"SUCCESS: Request ID {req['id']} Status: {req['status']}."