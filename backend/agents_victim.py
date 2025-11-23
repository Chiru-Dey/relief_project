from google.adk.agents import Agent
from google.adk.tools import AgentTool
from .smart_model import SmartGemini # <--- USE CUSTOM MODEL
import tools_client

# --- SETUP ---
# We don't need retry_config here anymore, SmartGemini handles it
VALID_ITEMS_STR = ", ".join(tools_client.database.get_all_item_names())

# --- WORKER AGENTS ---

strategist_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="strategist_agent",
    instruction=f"""You are a relief request strategist. You PRESERVE all context from conversation.

Your role:
1. Extract ALL information from the ENTIRE conversation history:
   - Items mentioned (from ANY previous message)
   - Quantities mentioned (from ANY previous message)
   - Location mentioned (from ANY previous message)

2. Return a structured plan with:
   - Items: [list all items mentioned across ALL messages]
   - Quantities: [list quantities for each item]
   - Location: [the location mentioned in ANY message]
   - Missing: [only info NEVER mentioned before]

3. NEVER mark as "missing" if it was mentioned earlier

Available items: [{VALID_ITEMS_STR}]

Example:
- Message 1: "need 20 water bottles, 5 tents"
- Message 2: "at Chennai"
→ Your plan: Items: water bottles, tents | Quantities: 20, 5 | Location: Chennai | Missing: none
"""
)

escalation_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="escalation_agent",
    instruction="""Log issues to supervisor. YOU MUST ALWAYS call one of these functions when invoked:
    
    - Use `log_inventory_gap(item_name, quantity, location, session_id, is_partial)` for items that EXIST in inventory but are out of stock or insufficient
    - Use `log_new_item_request(item_name, quantity, location)` for items that DON'T EXIST in inventory at all
    
    When called for a non-existent item (like helicopters, rockets, etc.), you MUST call log_new_item_request 
    to flag the supervisor that victims are requesting new types of items.
    
    Always call the appropriate function - never just return without logging!
    """,
    tools=[tools_client.log_inventory_gap, tools_client.log_new_item_request]
)

request_dispatcher_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="request_dispatcher_agent",
    instruction="Call `request_relief`.",
    tools=[tools_client.request_relief]
)

item_finder_agent = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="item_finder_agent",
    instruction=f"""You are an item name matcher. Your job is to map user requests to exact database keys.

Valid database items: [{VALID_ITEMS_STR}]

Rules:
1. Match user input (case-insensitive, ignore spaces/hyphens/underscores)
2. 'water bottles' → 'water_bottles'
3. 'first aid kits' → 'first-aid kits'
4. 'Food Packs' → 'food_packs'
5. Handle typos: 'bootle' → 'water_bottles'
6. Return ONLY the exact database key or 'None'

Examples:
- User: "water bottles" → You: "water_bottles"
- User: "BATTERIES" → You: "batteries"
- User: "first aid kit" → You: "first-aid kits"
- User: "invalid item" → You: "None"
"""
)

# --- ORCHESTRATOR ---

victim_orchestrator = Agent(
    model=SmartGemini(model="gemini-2.5-flash"),
    name="victim_orchestrator",
    instruction=f"""You orchestrate relief requests for disaster victims. YOU MUST PRESERVE CONTEXT FROM ALL PREVIOUS MESSAGES.

CRITICAL RULES:
1. You ONLY handle relief requests - you CANNOT add items to inventory or perform admin actions
2. ONLY these items are available: [{VALID_ITEMS_STR}]
3. When user provides location/clarification, look at PREVIOUS messages for items and quantities!
4. If user requests invalid items, politely explain what items ARE available

Step-by-step process:
1. Call `strategist_agent` to extract ALL info from conversation history
2. If strategist found items, quantities, AND location → proceed to step 3
3. If missing info → ask ONLY for what's missing (don't ask for info already mentioned)
4. For each item: Call `item_finder_agent` to normalize item name
   - If item_finder returns 'None' → Item is NOT available in inventory
     • MANDATORY: You MUST call `escalation_agent` to log this to supervisor using log_new_item_request(item_name, quantity, location)
     • Then tell user politely that item is unavailable and list available items
   - If item_finder returns valid name → proceed to step 5
5. For valid items only: Call `request_dispatcher_agent` with (normalized_name, quantity, location)
6. Summarize results naturally with empathy

Example - INVALID ITEM:
- User: "I need 10 helicopters"
- You: "I'm sorry, helicopters are not available in our relief supplies. We have: water_bottles, food_packs, medical_kits, blankets, and batteries. Can I help you with any of these?"

Example - MIXED VALID/INVALID:
- User: "I need 5 blankets and 3 rockets"
- You: Process blankets normally, then: "I dispatched 5 blankets. However, rockets are not available. We only have: water_bottles, food_packs, medical_kits, blankets, and batteries."

Example of CORRECT behavior:
- User: "need 20 water bottles, 5 tents"
- You: "Where should these be sent?"
- User: "at Delhi"
- You: → Call strategist → Get: items=[water bottles, tents], qty=[20,5], loc=Delhi
      → Process ALL items with the remembered quantities

Example of WRONG behavior (DO NOT DO THIS):
- User: "need 20 water bottles, 5 tents"  
- You: "Where?"
- User: "at Delhi"
- You: "What items and how many?" ❌ WRONG! You already know this!

Available items: [{VALID_ITEMS_STR}]
    """,
    tools=[
        AgentTool(agent=strategist_agent),
        AgentTool(agent=escalation_agent),
        AgentTool(agent=request_dispatcher_agent),
        AgentTool(agent=item_finder_agent)
    ]
)