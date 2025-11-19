import database

def supervisor_view_pending_requests() -> str:
    """Returns a list of all requests with status 'PENDING'."""
    rows = database.get_pending_requests()
    if not rows: 
        return "No pending requests found."
    
    result = "Pending Requests:\n"
    for r in rows:
        result += f"- ID {r['id']}: {r['quantity']}x {r['item_name']} for {r['location']}\n"
    return result

def supervisor_decide_request(request_id: int, decision: str) -> str:
    """
    Supervisor tool to APPROVE or REJECT a request ID.
    Decision must be 'APPROVE' or 'REJECT'.
    """
    decision = decision.upper()
    req = database.get_request_by_id(request_id)
    
    if not req: return f"Error: Request ID {request_id} not found."
    if req['status'] != 'PENDING': return f"Error: Request {request_id} is {req['status']}."

    if decision == "REJECT":
        database.update_request_status(request_id, "REJECTED")
        return f"Request {request_id} REJECTED."
    
    if decision == "APPROVE":
        # Race condition check
        current_stock = database.get_item_stock(req['item_name'])
        if current_stock < req['quantity']:
            return f"Cannot Approve: Insufficient stock. Current: {current_stock}."
        
        new_stock = current_stock - req['quantity']
        database.update_stock(req['item_name'], new_stock)
        database.update_request_status(request_id, "APPROVED")
        return f"Request {request_id} APPROVED. New stock: {new_stock}."

def admin_view_full_inventory() -> str:
    """Returns a list of ALL items and their current stock levels."""
    conn = database.get_db_connection()
    rows = conn.execute("SELECT * FROM inventory").fetchall()
    conn.close()
    
    result = "Current Inventory Levels:\n"
    for r in rows:
        result += f"- {r['item_name']}: {r['quantity']}\n"
    return result

def admin_restock_item(item_name: str, quantity: int) -> str:
    """Sets the stock level of an item to a specific quantity."""
    current = database.get_item_stock(item_name)
    if current == -1:
        return f"Error: Cannot restock '{item_name}' because it does not exist in the database."
    
    database.update_stock(item_name, quantity)
    return f"SUCCESS: {item_name} stock set to {quantity}."