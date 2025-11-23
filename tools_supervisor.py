import database
import json
from difflib import get_close_matches

def normalize_item_name_fuzzy(item_name: str) -> tuple[str, bool]:
    """
    Normalize item name with fuzzy matching for supervisor operations.
    
    Returns: (normalized_name, found_match)
    - normalized_name: The matched database key or normalized input
    - found_match: True if item exists in database, False otherwise
    
    Examples:
    - "water bottles" → ("water_bottles", True)
    - "water bootle" → ("water_bottles", True) - typo correction
    - "Medical Kits" → ("medical_kits", True)
    - "unknown_item" → ("unknown_item", False)
    """
    # Step 1: Basic normalization
    normalized = item_name.lower().replace(" ", "_").replace("-", "_")
    
    # Step 2: Get all valid items from database
    valid_items = database.get_all_item_names()
    
    # Step 3: Check for exact match
    if normalized in valid_items:
        return (normalized, True)
    
    # Step 4: Try fuzzy matching
    normalized_valid = [item.replace(" ", "_").replace("-", "_") for item in valid_items]
    matches = get_close_matches(normalized, normalized_valid, n=1, cutoff=0.6)
    
    if matches:
        # Find the original database key
        matched_normalized = matches[0]
        for i, norm_item in enumerate(normalized_valid):
            if norm_item == matched_normalized:
                return (valid_items[i], True)
    
    # Step 5: No match found
    return (normalized, False)

# ... (Previous tools remain the same: view_pending, decide_request, batch_decide, add, delete, restock) ...
def supervisor_view_pending_requests() -> str:
    # ... same as before ...
    rows = database.get_pending_requests()
    if not rows: return "No items require attention."
    result = "Attention Queue:\n"
    for r in rows:
        if r['status'] == 'ACTION_REQUIRED': result += f"- ❗ ACTION (ID {r['id']}): {r['notes']} at {r['location']}\n"
        else:
            urgency = "🔴" if r['urgency'] == 'CRITICAL' else "⚪"
            result += f"- ⏳ PENDING (ID {r['id']}) [{urgency}]: {r['quantity']}x {r['item_name']}\n"
    return result

def supervisor_mark_action_taken(task_id: int, notes: str) -> str:
    task = database.get_request_by_id(task_id)
    if not task: return f"Error: Task {task_id} not found."
    database.update_request_status(task_id, "ACTION_TAKEN", f"Human action: {notes}")
    return f"SUCCESS: Task {task_id} marked completed."

def supervisor_resolve_action_required(task_id: int, buffer_multiplier: float = 1.5) -> str:
    """
    Resolve an ACTION_REQUIRED task by automatically restocking with buffer and dispatching.
    buffer_multiplier: How much extra to restock (e.g., 1.5 = 50% buffer, 2.0 = 100% buffer)
    """
    task = database.get_request_by_id(task_id)
    if not task: 
        return f"Error: Task {task_id} not found."
    
    if task['status'] != 'ACTION_REQUIRED':
        return f"Error: Task {task_id} is not ACTION_REQUIRED (current status: {task['status']})."
    
    item_name = task['item_name']
    quantity_needed = task['quantity']
    location = task['location']
    
    # Calculate restock amount with buffer
    restock_amount = int(quantity_needed * buffer_multiplier)
    
    # Restock the item
    current_stock = database.get_item_stock(item_name)
    if current_stock == -1:
        # Item doesn't exist, create it
        database.add_new_item(item_name, restock_amount)
        result_msg = f"Created new item '{item_name}' with {restock_amount} units (needed {quantity_needed} + buffer)."
    else:
        # Item exists, add stock
        new_total = database.increment_stock(item_name, restock_amount)
        result_msg = f"Restocked '{item_name}' with {restock_amount} units. New total: {new_total}."
    
    # Dispatch the needed quantity
    current_stock = database.get_item_stock(item_name)
    if current_stock >= quantity_needed:
        # Dispatch the requested amount
        database.update_stock(item_name, current_stock - quantity_needed)
        
        # Send notification to victim
        import tools_client
        session_id = database.get_session_for_location(location)
        if session_id:
            tools_client.send_victim_chat_message(
                session_id,
                f"Hey! Great news - we just restocked and your request for {quantity_needed} {item_name.replace('_', ' ')} is now on its way to {location}! Thanks for your patience. 🙏"
            )
        
        # Log the dispatch
        tools_client.log_to_supervisor_activity(
            f"AUTO-DISPATCH: Dispatched {quantity_needed}x {item_name} to {location} (from resolve of request #{task_id})",
            "system"
        )
        
        final_stock = database.get_item_stock(item_name)
        result_msg += f"\n\nAuto-dispatched {quantity_needed} units to {location}. Buffer remaining: {final_stock}."
    else:
        result_msg += f"\n\nWarning: After restock, stock is {current_stock} but needed {quantity_needed}."
    
    # Mark this task as ACTION_TAKEN
    database.update_request_status(task_id, "ACTION_TAKEN", f"Resolved with restock: {restock_amount} units, dispatched {quantity_needed}")
    
    return result_msg

def supervisor_decide_request(request_id: int, decision: str) -> str:
    # ... same as before ...
    decision = decision.upper()
    req = database.get_request_by_id(request_id)
    if not req: return f"Error: Request {request_id} not found."
    if decision == "REJECT":
        database.update_request_status(request_id, "REJECTED", "Rejected")
        return f"Request {request_id} REJECTED."
    if decision == "APPROVE":
        current = database.get_item_stock(req['item_name'])
        if current < req['quantity']: return "Cannot Approve: Insufficient stock."
        new_stock = current - req['quantity']
        database.update_stock(req['item_name'], new_stock)
        database.update_request_status(request_id, "APPROVED_MANUAL", "Approved")
        return f"Request {request_id} APPROVED."

def supervisor_batch_decide_requests(request_ids_json: str, decision: str) -> str:
    try: ids = json.loads(request_ids_json)
    except: return "Error: Invalid JSON list."
    return "\n".join([supervisor_decide_request(i, decision) for i in ids])

def admin_add_new_item(item_name: str, initial_quantity: int) -> str:
    # Use fuzzy matching to check if item already exists
    normalized_name, exists = normalize_item_name_fuzzy(item_name)
    
    if exists:
        return f"ERROR: Item '{normalized_name}' already exists in inventory. Use restock instead. (Did you mean to restock '{normalized_name}'?)"
    
    # For new items, just use basic normalization (no fuzzy match needed)
    new_item_name = item_name.lower().replace(" ", "_").replace("-", "_")
    database.add_new_item(new_item_name, initial_quantity)
    return f"SUCCESS: Added '{new_item_name}' with {initial_quantity} units."

def admin_delete_item(item_name: str) -> str:
    # Use fuzzy matching to find the item
    normalized_name, exists = normalize_item_name_fuzzy(item_name)
    
    if not exists:
        # Provide helpful suggestions
        all_items = database.get_all_item_names()
        return f"ERROR: Item '{item_name}' not found in inventory. Cannot delete. Available items: {', '.join(all_items[:5])}..."
    
    database.delete_item(normalized_name)
    return f"SUCCESS: Deleted '{normalized_name}' from inventory."

def admin_restock_item(item_name: str, quantity_to_add: int) -> str:
    # Use fuzzy matching to find the item
    normalized_name, exists = normalize_item_name_fuzzy(item_name)
    
    if not exists:
        # Provide helpful suggestions
        all_items = database.get_all_item_names()
        return f"ERROR: Item '{item_name}' not found in inventory. Cannot restock. Available items: {', '.join(all_items[:5])}... (Did you mean one of these?)"
    
    total = database.increment_stock(normalized_name, quantity_to_add)
    return f"SUCCESS: Added {quantity_to_add} to '{normalized_name}'. Total: {total}."

# 🔥 FIXED: ROBUST JSON PARSING
def admin_batch_update_inventory(updates_json: str) -> str:
    """
    Batch update inventory. Handles both Dict {"item": qty} and List [{"item": "x", "qty": 1}]
    """
    try:
        data = json.loads(updates_json)
    except:
        return "Error: Invalid JSON format."

    updates = {}
    
    # Logic to normalize input to a dictionary
    if isinstance(data, dict):
        updates = data
    elif isinstance(data, list):
        # Handle list of dicts or lists
        for entry in data:
            if isinstance(entry, dict):
                # Try different key variations common with LLMs
                key = entry.get("item") or entry.get("item_name") or entry.get("name")
                val = entry.get("qty") or entry.get("quantity") or entry.get("amount")
                if key and val is not None:
                    updates[key] = val
    
    if not updates:
        return "Error: Could not parse items from JSON."

    log = []
    for item, qty in updates.items():
        if database.get_item_stock(item) == -1:
            database.add_new_item(item, qty)
            log.append(f"Created {item} = {qty}")
        else:
            database.update_stock(item, qty)
            log.append(f"Updated {item} = {qty}")
            
    return "\n".join(log)

# ... (View tools remain same) ...
def admin_view_full_inventory() -> str:
    rows = database.get_all_items()
    return "Inventory:\n" + "\n".join([f"- {r['item_name']}: {r['quantity']}" for r in rows])

def admin_get_low_stock_report(threshold: int = 20) -> str:
    rows = [r for r in database.get_all_items() if r['quantity'] < threshold]
    return "Low Stock:\n" + "\n".join([f"- {r['item_name']}: {r['quantity']}" for r in rows]) if rows else "All OK."

def supervisor_view_audit_log(limit: int = 10) -> str:
    rows = database.get_recent_completed_requests(limit)
    return "Audit Log:\n" + "\n".join([f"- ID {r['id']} [{r['status']}]: {r['item_name']}" for r in rows]) if rows else "No logs."

def log_user_complaint(complaint_text: str) -> str:
    if not complaint_text: return "Error: Empty complaint."
    database.create_system_log(complaint_text)
    return "SUCCESS: Complaint logged."