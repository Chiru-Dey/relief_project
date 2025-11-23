from google.adk.agents import Agent
from google.adk.tools import AgentTool
from .smart_model import SmartGemini # <--- USE CUSTOM MODEL
import tools_supervisor

# --- WORKERS ---

inventory_manager_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="inventory_manager_agent",
    instruction="""Manage inventory operations with precision:

CRITICAL RESTOCK LOGIC:
- "restock X by Y" = ADD Y to current stock of X (use admin_restock_item)
- "restock all items below N by Y" = find items with quantity < N, then ADD Y to each
- NEVER use admin_batch_update_inventory for "by" operations (it sets values)

PROCESS for bulk conditional restock:
1. Use admin_view_full_inventory to see current stock levels
2. Identify items with quantity < threshold
3. For each qualifying item: call admin_restock_item(item_name, amount_to_add)
4. Confirm results by showing old_quantity + added_amount = new_quantity

EXAMPLE: "restock all items below 100 by 500"
- Find items with qty < 100: [water_bottles: 90, medical_kits: 50]
- Call admin_restock_item("water_bottles", 500) → 90 + 500 = 590
- Call admin_restock_item("medical_kits", 500) → 50 + 500 = 550

AUTONOMOUS DELETION LOGIC:
When asked to "delete N low-priority items" or similar:
1. Use admin_view_full_inventory to see all items
2. Apply smart prioritization:
   - LOW priority: items with very high stock (>500), non-essential items
   - HIGH priority: critical supplies (water, medical, food, shelter items)
3. Select N items based on criteria
4. Delete each using admin_delete_item
5. Confirm which items were deleted and why

NAME NORMALIZATION & FUZZY MATCHING:
- All functions now use fuzzy matching with 60% similarity threshold
- "water bottles" and "water_bottles" both work
- Handles typos: "water bootle" → "water_bottles"
- "Medical Kits" → "medical_kits" (case insensitive)
- Functions return helpful ERROR messages with suggestions if items not found
- Exact matches are prioritized over fuzzy matches""",
    tools=[
        tools_supervisor.admin_add_new_item, tools_supervisor.admin_delete_item,
        tools_supervisor.admin_restock_item, tools_supervisor.admin_batch_update_inventory,
        tools_supervisor.admin_view_full_inventory, tools_supervisor.admin_get_low_stock_report
    ]
)

approval_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="approval_agent",
    instruction="Handle approvals and resolve ACTION_REQUIRED tasks with automatic restocking.",
    tools=[
        tools_supervisor.supervisor_view_pending_requests, tools_supervisor.supervisor_decide_request,
        tools_supervisor.supervisor_batch_decide_requests, tools_supervisor.supervisor_view_audit_log,
        tools_supervisor.supervisor_mark_action_taken, tools_supervisor.supervisor_resolve_action_required
    ]
)

action_item_strategist = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="action_item_strategist",
    instruction="Analyze ACTION_REQUIRED tasks and resolve them by restocking with appropriate buffer.",
    tools=[
        tools_supervisor.supervisor_view_pending_requests,
        tools_supervisor.supervisor_resolve_action_required,
        tools_supervisor.admin_view_full_inventory
    ]
)

# --- ORCHESTRATOR ---
supervisor_orchestrator = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="supervisor_orchestrator",
    instruction="""Delegate tasks appropriately:
    - For inventory operations (add, delete, restock, view): Use inventory_manager_agent
    - For approvals/rejections of pending requests: Use approval_agent
    - For 'resolve', 'fix', or handling ACTION_REQUIRED tasks: Use action_item_strategist
    
    CRITICAL: For "restock X by Y" commands that ADD quantities:
    - Use inventory_manager_agent with admin_restock_item() function
    - "restock by" means ADD to existing stock, not SET to new value
    - For bulk operations: call admin_restock_item() multiple times for each qualifying item
    
    When user says 'resolve' or 'fix' an action item, delegate to action_item_strategist 
    which will automatically restock with buffer and dispatch to victims.""",
    tools=[
        AgentTool(agent=inventory_manager_agent),
        AgentTool(agent=approval_agent),
        AgentTool(agent=action_item_strategist)
    ]
)