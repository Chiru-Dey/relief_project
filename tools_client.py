import database

def check_inventory(item_name: str) -> str:
    """Checks the current stock of a specific item."""
    stock = database.get_item_stock(item_name)
    if stock >= 0:
        return f"{item_name}: {stock} units available."
    else:
        available = ", ".join(database.get_all_item_names())
        return f"Error: '{item_name}' not found. We stock: {available}."

def request_relief(item_name: str, quantity: int, location: str) -> str:
    """
    Processes a relief request. 
    If quantity > 10, it queues for Supervisor approval.
    If quantity <= 10, it auto-approves.
    """
    current_stock = database.get_item_stock(item_name)
    
    # Validation
    if current_stock == -1: 
        return f"Error: Item '{item_name}' does not exist."
    if current_stock < quantity: 
        return f"Error: Insufficient stock. Only {current_stock} available."

    # Business Logic
    if quantity > 10:
        req_id = database.create_request(item_name, quantity, location, "PENDING", "Requires Supervisor Approval")
        return f"Request ID {req_id} created. Status: PENDING (Large quantity requires Supervisor approval)."
    else:
        new_stock = current_stock - quantity
        database.update_stock(item_name, new_stock)
        database.create_request(item_name, quantity, location, "APPROVED", "Auto-approved small batch")
        return f"APPROVED. Dispatched {quantity} {item_name}. New Stock: {new_stock}."