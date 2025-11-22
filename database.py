import sqlite3

DB_FILE = "relief_logistics.db"

def init_db():
    """Initializes the database with all necessary tables and seed data."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    
    # Inventory
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (item_name TEXT PRIMARY KEY, quantity INTEGER)''')
    
    # Requests
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, quantity INTEGER,
                    location TEXT, status TEXT, urgency TEXT, notes TEXT
                )''')
    
    # Seed Data
    c.execute("SELECT count(*) FROM inventory")
    if c.fetchone()[0] == 0:
        print("🌱 Seeding database...")
        seed_data = [
            ("Water bottles", 100), ("Food packs", 50), ("Medical kits", 10), 
            ("Blankets", 30), ("Batteries", 200), ("Tents", 60), ("Flashlights", 60)
        ]
        normalized_seed = [(name.lower().replace(" ", "_").replace("-", "_"), qty) for name, qty in seed_data]
        c.executemany("INSERT INTO inventory (item_name, quantity) VALUES (?, ?)", normalized_seed)
        conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- Operations ---
def get_item_stock(item_name: str) -> int:
    conn = get_db_connection()
    row = conn.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item_name,)).fetchone()
    conn.close()
    return row['quantity'] if row else -1

def get_all_item_names() -> list[str]:
    conn = get_db_connection()
    rows = conn.execute("SELECT item_name FROM inventory").fetchall()
    conn.close()
    return [r['item_name'] for r in rows]

def get_all_items() -> list[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM inventory").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_new_item(item_name: str, quantity: int):
    conn = get_db_connection()
    conn.execute("INSERT INTO inventory (item_name, quantity) VALUES (?, ?)", (item_name, quantity))
    conn.commit()
    conn.close()

def delete_item(item_name: str):
    conn = get_db_connection()
    conn.execute("DELETE FROM inventory WHERE item_name = ?", (item_name,))
    conn.commit()
    conn.close()

def update_stock(item_name: str, new_quantity: int):
    conn = get_db_connection()
    conn.execute("UPDATE inventory SET quantity = ? WHERE item_name = ?", (new_quantity, item_name))
    conn.commit()
    conn.close()
    
def increment_stock(item_name: str, amount_to_add: int) -> int:
    conn = get_db_connection()
    conn.execute("UPDATE inventory SET quantity = quantity + ? WHERE item_name = ?", (amount_to_add, item_name))
    conn.commit()
    row = conn.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item_name,)).fetchone()
    conn.close()
    return row['quantity'] if row else 0

def create_request(item_name: str, quantity: int, location: str, status: str, urgency: str, notes: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO requests (item_name, quantity, location, status, urgency, notes) VALUES (?, ?, ?, ?, ?, ?)", 
                   (item_name, quantity, location, status, urgency, notes))
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return req_id

def get_pending_requests() -> list[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM requests WHERE status = 'PENDING' OR status = 'ACTION_REQUIRED' ORDER BY urgency DESC, id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_request_by_id(request_id: int) -> dict:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_request_status(request_id: int, status: str, notes: str = None):
    conn = get_db_connection()
    if notes:
        conn.execute("UPDATE requests SET status = ?, notes = ? WHERE id = ?", (status, notes, request_id))
    else:
        conn.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
    conn.commit()
    conn.close()

def get_recent_completed_requests(limit: int = 10) -> list[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM requests WHERE status NOT IN ('PENDING', 'ACTION_REQUIRED') ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_system_log(notes: str):
    """Creates a non-actionable log for supervisor review."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO requests (item_name, quantity, location, status, urgency, notes) VALUES (?, ?, ?, ?, ?, ?)", 
                   ("SYSTEM_NOTE", 0, "N/A", "FLAGGED", "NORMAL", notes))
    conn.commit()
    conn.close()