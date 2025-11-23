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
    instruction="Call `log_inventory_gap`.",
    tools=[tools_client.log_inventory_gap]
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
    instruction=f"""You orchestrate relief requests. YOU MUST PRESERVE CONTEXT FROM ALL PREVIOUS MESSAGES.

CRITICAL RULE: When user provides location/clarification, look at PREVIOUS messages for items and quantities!

Step-by-step process:
1. Call `strategist_agent` to extract ALL info from conversation history
2. If strategist found items, quantities, AND location → proceed to step 3
3. If missing info → ask ONLY for what's missing (don't ask for info already mentioned)
4. For each item: Call `item_finder_agent` to normalize item name
5. For each item: Call `request_dispatcher_agent` with (normalized_name, quantity, location)
6. Summarize results naturally

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