import database
from difflib import get_close_matches
import requests
import threading
from typing import Optional

# Frontend server URL for logging supervisor activities
# On Render with Honcho, both processes run in the same container so localhost works
# But we need to use the correct port (Render assigns PORT env var to frontend)
import os
FRONTEND_PORT = os.environ.get("PORT", "5000")
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

# Global variable to store current session ID (set by agent runner)
CURRENT_SESSION_ID = None

# Thread-local storage for session context (backup method)
_session_context = threading.local()

def set_session_context(session_id: str):
    """Set the current session ID for this thread"""
    _session_context.session_id = session_id

def get_session_context(location: str = None) -> str:
    """Get the current session ID from database based on location"""
    # Session is stored in database when request is created
    # We look it up by location when we need to send notifications
    if location:
        session_id = database.get_session_for_location(location)
        print(f"🔍 DEBUG (tools_client): get_session_context({location}) returned: {session_id}")
        return session_id
    return None

def clear_session_context():
    """Clear the session context"""
    if hasattr(_session_context, 'session_id'):
        del _session_context.session_id

def log_to_supervisor_activity(action: str, log_type: str = "info"):
    """Log action to supervisor activity log via frontend API"""
    try:
        # This is a fire-and-forget log, don't block if it fails
        requests.post(f"{FRONTEND_URL}/api/log_supervisor_activity", 
                     json={"action": action, "type": log_type}, 
                     timeout=1)
    except:
        pass  # Silently fail if frontend is not available

def normalize_item_name(item_name: str) -> str:
    """
    Normalize item name to match database format with fuzzy matching.
    
    Steps:
    1. Basic normalization: lowercase, replace spaces/hyphens with underscores
    2. Check for exact match in database
    3. If no exact match, use fuzzy matching to find closest item
    4. Returns the matched database key or original normalized name
    
    Examples:
    - "water bottles" → "water_bottles" (exact match after normalization)
    - "water bootle" → "water_bottles" (fuzzy match, typo correction)
    - "first aid kits" → "first-aid kits" (fuzzy match, handles format differences)
    """
    # Step 1: Basic normalization
    normalized = item_name.lower().replace(" ", "_").replace("-", "_")
    
    # Step 2: Get all valid items from database
    valid_items = database.get_all_item_names()
    
    # Step 3: Check for exact match
    if normalized in valid_items:
        return normalized
    
    # Step 4: Try fuzzy matching against all valid items
    # Also normalize valid items for comparison
    normalized_valid = [item.replace(" ", "_").replace("-", "_") for item in valid_items]
    
    # Find closest match (cutoff=0.6 means 60% similarity required)
    matches = get_close_matches(normalized, normalized_valid, n=1, cutoff=0.6)
    
    if matches:
        # Find the original database key that corresponds to the matched normalized form
        matched_normalized = matches[0]
        for i, norm_item in enumerate(normalized_valid):
            if norm_item == matched_normalized:
                return valid_items[i]
    
    # Step 5: No match found, return original normalized name
    # (This will fail in database lookup, but preserves user input for error message)
    return normalized

def check_inventory(item_name: str) -> str:
    """Checks the current stock of a specific inventory item."""
    normalized_name = normalize_item_name(item_name)
    stock = database.get_item_stock(normalized_name)
    if stock >= 0:
        return f"SUCCESS: {item_name} has {stock} units."
    else:
        all_items = database.get_all_item_names()
        return f"ERROR: Item '{item_name}' not found. Valid items are: {', '.join(all_items)}."

def log_inventory_gap(item_name: str, quantity: int, location: str, session_id: Optional[str] = None, is_partial: bool = False) -> str:
    """
    Logs that a user requested an item not in inventory (or insufficient stock).
    - If is_partial=True (partial fulfillment): Creates ACTION_REQUIRED for supervisor to manually resolve
    - If is_partial=False (zero stock): Creates PENDING_DISPATCH for auto-fulfillment when restocked
    """
    normalized_name = normalize_item_name(item_name)
    
    if is_partial:
        # Partial fulfillment - flag for manual supervisor action
        suggestion = f"PARTIAL FULFILLMENT: Dispatched some, but still short {quantity}x '{item_name}' at {location}. Please restock with buffer."
        status = "ACTION_REQUIRED"
    else:
        # Zero stock - auto-dispatch when available
        suggestion = f"User at {location} needs {quantity}x '{item_name}'. Awaiting restock for auto-dispatch."
        status = "PENDING_DISPATCH"
    
    database.create_request(
        item_name=normalized_name,
        quantity=quantity,
        location=location,
        status=status,
        urgency="NORMAL",
        notes=suggestion,
        session_id=session_id
    )
    return f"Logged {'action required' if is_partial else 'pending request'} for {quantity}x {item_name}."

def log_new_item_request(item_name: str, quantity: int, location: str) -> str:
    """
    Logs when a victim requests an item that doesn't exist in inventory at all.
    Flags supervisor to consider adding this item.
    """
    database.create_request(
        item_name=item_name,
        quantity=quantity,
        location=location,
        status="ACTION_REQUIRED",
        urgency="NORMAL",
        notes=f"NEW ITEM REQUEST: User at {location} requested {quantity}x '{item_name}' which is not in our inventory. Consider adding this item if demand is high.",
        session_id=None
    )
    
    # Also log to activity log
    log_to_supervisor_activity(
        f"NEW ITEM REQUESTED: {item_name} (qty: {quantity}) at {location} - Not in inventory",
        "info"
    )
    
    return f"Logged new item request for supervisor review: {item_name}"

def send_victim_chat_message(session_id: str, message: str):
    """Send a chat message to victim's conversation (appears as AI message)"""
    if not session_id:
        return
    try:
        requests.post(
            f"{FRONTEND_URL}/api/send_victim_notification",
            json={"session_id": session_id, "message": message},
            timeout=1
        )
    except:
        pass

def process_pending_dispatches(item_name: str) -> list[str]:
    """
    After a restock, check for pending dispatch requests and fulfill them.
    Handles both PENDING_DISPATCH (auto-dispatch) and ACTION_REQUIRED (from manual resolve).
    Returns list of messages about dispatched items.
    """
    normalized_name = normalize_item_name(item_name)
    conn = database.get_db_connection()
    
    # Get all pending dispatch requests for this item (both PENDING_DISPATCH and ACTION_REQUIRED), ordered by ID (FIFO)
    pending = conn.execute(
        "SELECT * FROM requests WHERE item_name = ? AND status IN ('PENDING_DISPATCH', 'ACTION_REQUIRED') ORDER BY id ASC",
        (normalized_name,)
    ).fetchall()
    
    if not pending:
        conn.close()
        return []
    
    messages = []
    current_stock = database.get_item_stock(normalized_name)
    
    for req in pending:
        req_id = req['id']
        quantity_needed = req['quantity']
        location = req['location']
        # Handle session_id - it might be None/NULL in database
        try:
            victim_session = req['session_id']
        except (KeyError, IndexError):
            victim_session = None
        
        if current_stock <= 0:
            # No more stock available
            break
        
        if current_stock >= quantity_needed:
            # Can fulfill completely
            database.update_stock(normalized_name, current_stock - quantity_needed)
            database.update_request_status(req_id, "ACTION_TAKEN", f"Auto-dispatched after restock")
            
            log_to_supervisor_activity(
                f"AUTO-DISPATCH: Fulfilled {quantity_needed}x {normalized_name} to {location} (from request #{req_id})",
                "system"
            )
            
            # Send chat message to victim
            send_victim_chat_message(
                victim_session,
                f"Hey! Great news - we just restocked and your request for {quantity_needed} {item_name} is now on its way to {location}! Thanks for your patience. 🙏"
            )
            
            messages.append(f"✅ Auto-dispatched {quantity_needed}x {item_name} to {location} (Request #{req_id})")
            current_stock -= quantity_needed
        else:
            # Can only fulfill partially
            amount_sent = current_stock
            remaining = quantity_needed - current_stock
            
            database.update_stock(normalized_name, 0)
            database.update_request_status(req_id, "PARTIAL", f"Dispatched {amount_sent}, still need {remaining}")
            
            log_to_supervisor_activity(
                f"AI_APPROVED: Auto-dispatched {amount_sent}x {normalized_name} to {location} (Partial from request #{req_id}, {remaining} remaining)",
                "system"
            )
            
            # Send chat message to victim about partial fulfillment
            send_victim_chat_message(
                victim_session,
                f"Quick update - we were able to send {amount_sent} {item_name} to {location} from what we had available. Still working on getting the remaining {remaining} units to you. We're doing our best to help!"
            )
            
            # Create new pending request for the remainder (keep same session_id)
            database.create_request(
                normalized_name,
                remaining,
                location,
                "PENDING_DISPATCH",
                "NORMAL",
                f"Remaining from request #{req_id}",
                session_id=victim_session
            )
            
            messages.append(f"⚠️ Partially dispatched {amount_sent}x {item_name} to {location} (Request #{req_id}), {remaining} still pending")
            current_stock = 0
            break
    
    conn.close()
    return messages

def request_relief(item_name: str, quantity: int, location: str, is_critical: bool = False) -> str:
    """
    Processes a relief request. Handles Partial Fulfillment automatically.
    """
    normalized_name = normalize_item_name(item_name)
    current_stock = database.get_item_stock(normalized_name)
    
    # Get the most recent ACTIVE session and update it with the location
    import sqlite3
    conn = sqlite3.connect('relief_logistics.db')
    cursor = conn.cursor()
    
    # Get the most recent session marked as ACTIVE
    cursor.execute('SELECT session_id FROM active_sessions WHERE location = "ACTIVE" ORDER BY timestamp DESC LIMIT 1')
    row = cursor.fetchone()
    session_id = row[0] if row else None
    
    # Update this session with the actual location for future lookups
    if session_id:
        database.register_active_session(session_id, location)
        print(f"[BACKEND] 🔍 DEBUG: Updated session {session_id} with location: {location}")
    
    conn.close()
    print(f"[BACKEND] 🔍 DEBUG: request_relief - location: {location}, session_id: {session_id}")
    
    # 1. Item doesn't exist
    if current_stock == -1: 
        log_inventory_gap(item_name, quantity, location, session_id)
        return f"ERROR: Item '{item_name}' does not exist. I have logged this gap for the supervisor."

    urgency = "CRITICAL" if is_critical else "NORMAL"

    # 2. Insufficient Stock (Zero or Negative) - Don't allow negative inventory!
    if current_stock <= 0:
        # Don't dispatch anything - stock is already at or below zero
        log_inventory_gap(item_name, quantity, location, session_id)
        return f"I'm really sorry, but we're completely out of {item_name} right now. I've put in a request for {quantity} units to {location}, and our team will work on getting them to you as soon as we can restock. I'll let you know once they're on the way!"

    # 3. Partial Fulfillment
    if current_stock < quantity:
        amount_sent = current_stock
        shortfall = quantity - current_stock
        
        # Send what we have
        database.update_stock(normalized_name, 0) # Empty the stock (set to 0, not negative)
        
        # Log to supervisor activity log
        log_to_supervisor_activity(
            f"AI_APPROVED: Dispatched {amount_sent}x {normalized_name} to {location} (Partial - Stock exhausted)", 
            "system"
        )
        
        # Log the shortfall as ACTION_REQUIRED (partial fulfillment needs manual supervisor action)
        log_inventory_gap(item_name, shortfall, location, session_id, is_partial=True)
        
        return f"Good news - I found {amount_sent} {item_name} and they're on their way to {location} right now! Unfortunately that's all we have at the moment. I've flagged your request for the remaining {shortfall} units with our supervisor, and they'll get those to you as soon as possible. Hang in there!"

    # 4. Full Fulfillment
    else:
        new_stock = current_stock - quantity
        database.update_stock(normalized_name, new_stock)
        
        # Log to supervisor activity log
        log_to_supervisor_activity(
            f"AI_APPROVED: Dispatched {quantity}x {normalized_name} to {location}. Remaining: {new_stock}", 
            "system"
        )
        return f"Great news! I've got your {quantity} {item_name} approved and they're being dispatched to {location} right now. They should arrive soon. Stay safe!"

def check_request_status(request_id: int) -> str:
    """Allows a user to check the status of a previous request ID."""
    req = database.get_request_by_id(request_id)
    if not req: return f"ERROR: Request ID {request_id} not found."
    return f"SUCCESS: Request ID {req['id']} Status: {req['status']}."