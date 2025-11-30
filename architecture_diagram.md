# 🏗️ Disaster Relief Management System - Architecture Diagram

## System Architecture Visual

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                         DISASTER RELIEF MANAGEMENT SYSTEM                          ┃
┃                         Hierarchical Multi-Agent Architecture                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              👥 USER INTERFACES                                  │
├─────────────────────────────────┬───────────────────────────────────────────────┤
│  🆘 VICTIM CHAT INTERFACE       │   📊 SUPERVISOR DASHBOARD                     │
│  (Port 5000)                    │   (Port 5000)                                 │
│  ├─ Natural Language Input      │   ├─ Real-time Inventory View                │
│  ├─ Request Submission          │   ├─ Pending Request Approvals               │
│  ├─ Status Updates              │   ├─ Low Stock Alerts                        │
│  └─ Session Management          │   └─ Action Item Management                  │
└─────────────────────────────────┴───────────────────────────────────────────────┘
                                    │
                                    │ HTTP/WebSocket
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        🌐 FLASK FRONTEND SERVER (frontend_app.py)               │
│                                 Port 5000                                        │
│  ├─ Route: /victim (Victim Interface)                                           │
│  ├─ Route: /supervisor (Supervisor Dashboard)                                   │
│  ├─ Session Management (Flask-Session)                                          │
│  └─ API Communication with Backend                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP POST Requests
                                    │ (A2A Protocol)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ⚡ FASTAPI BACKEND SERVER (manager_server.py)               │
│                          A2A Protocol - Port 8001                                │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │              🧠 MANAGER ORCHESTRATOR (Top-Level Brain)                 │    │
│  │                    Powered by Gemini 2.5 Flash                         │    │
│  │                                                                         │    │
│  │  Role: Routes all incoming requests to appropriate orchestrator        │    │
│  │  Intelligence: Analyzes user type and intent                           │    │
│  │                                                                         │    │
│  │  Decision Logic:                                                       │    │
│  │    "victim" keyword → Route to Victim Orchestrator                     │    │
│  │    "supervisor" keyword → Route to Supervisor Orchestrator             │    │
│  │    Default → Error handling                                            │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                    │                                             │
│                   ┌────────────────┴────────────────┐                           │
│                   │                                  │                           │
│                   ▼                                  ▼                           │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐      │
│  │  🆘 VICTIM ORCHESTRATOR         │  │  📋 SUPERVISOR ORCHESTRATOR      │      │
│  │  (agents_victim.py)             │  │  (agents_supervisor.py)          │      │
│  │  Gemini 2.5 Flash              │  │  Gemini 2.5 Flash                │      │
│  │                                 │  │                                   │      │
│  │  Manages 4 Specialized Agents: │  │  Manages 3 Specialized Agents:   │      │
│  │                                 │  │                                   │      │
│  │  ┌─────────────────────────┐   │  │  ┌─────────────────────────┐     │      │
│  │  │ 1️⃣  STRATEGIST AGENT    │   │  │  │ 1️⃣  INVENTORY MANAGER   │     │      │
│  │  │     (victim_strategist) │   │  │  │    (inventory_manager)   │     │      │
│  │  │                         │   │  │  │                          │     │      │
│  │  │  Extracts:              │   │  │  │  Capabilities:           │     │      │
│  │  │  • Item names           │   │  │  │  • View inventory        │     │      │
│  │  │  • Quantities           │   │  │  │  • Check stock levels    │     │      │
│  │  │  • Locations            │   │  │  │  • Restock items         │     │      │
│  │  │  • Context & intent     │   │  │  │  • Update quantities     │     │      │
│  │  │                         │   │  │  │                          │     │      │
│  │  │  Tools:                 │   │  │  │  Tools:                  │     │      │
│  │  │  • extract_info()       │   │  │  │  • get_inventory()       │     │      │
│  │  └─────────────────────────┘   │  │  │  • restock_item()        │     │      │
│  │              │                  │  │  │  • update_inventory()    │     │      │
│  │              ▼                  │  │  └─────────────────────────┘     │      │
│  │  ┌─────────────────────────┐   │  │              │                    │      │
│  │  │ 2️⃣  ITEM FINDER AGENT   │   │  │              ▼                    │      │
│  │  │     (item_finder)       │   │  │  ┌─────────────────────────┐     │      │
│  │  │                         │   │  │  │ 2️⃣  APPROVAL AGENT      │     │      │
│  │  │  Fuzzy Matching (60%):  │   │  │  │    (approval_agent)      │     │      │
│  │  │  • Search inventory     │   │  │  │                          │     │      │
│  │  │  • Handle typos         │   │  │  │  Manages Requests:       │     │      │
│  │  │  • Suggest alternatives │   │  │  │  • View pending requests │     │      │
│  │  │  • Check availability   │   │  │  │  • Approve requests      │     │      │
│  │  │                         │   │  │  │  • Deny requests         │     │      │
│  │  │  Tools:                 │   │  │  │  • View history          │     │      │
│  │  │  • fuzzy_find_item()    │   │  │  │                          │     │      │
│  │  └─────────────────────────┘   │  │  │  Tools:                  │     │      │
│  │              │                  │  │  │  • get_pending_requests()│     │      │
│  │              ▼                  │  │  │  • approve_request()     │     │      │
│  │  ┌─────────────────────────┐   │  │  │  • deny_request()        │     │      │
│  │  │ 3️⃣  REQUEST DISPATCHER  │   │  │  └─────────────────────────┘     │      │
│  │  │    (request_dispatcher) │   │  │              │                    │      │
│  │  │                         │   │  │              ▼                    │      │
│  │  │  Request Processing:    │   │  │  ┌─────────────────────────┐     │      │
│  │  │  • Create requests      │   │  │  │ 3️⃣  ACTION STRATEGIST   │     │      │
│  │  │  • Auto-approve (<50)   │   │  │  │    (action_strategist)   │     │      │
│  │  │  • Pending (≥50)        │   │  │  │                          │     │      │
│  │  │  • Deduct inventory     │   │  │  │  Critical Decision-Making:│    │      │
│  │  │                         │   │  │  │  • Analyze shortages     │     │      │
│  │  │  Tools:                 │   │  │  │  • Resolve with buffer   │     │      │
│  │  │  • dispatch_request()   │   │  │  │  • Contact suppliers     │     │      │
│  │  └─────────────────────────┘   │  │  │  • Update victims        │     │      │
│  │              │                  │  │  │                          │     │      │
│  │              ▼                  │  │  │  Tools:                  │     │      │
│  │  ┌─────────────────────────┐   │  │  │  • resolve_shortage()    │     │      │
│  │  │ 4️⃣  ESCALATION AGENT    │   │  │  └─────────────────────────┘     │      │
│  │  │    (escalation_agent)   │   │  │                                   │      │
│  │  │                         │   │  └───────────────────────────────────┘      │
│  │  │  Issue Management:      │   │                                             │
│  │  │  • Flag critical issues │   │                                             │
│  │  │  • Notify supervisors   │   │                                             │
│  │  │  • Create action items  │   │                                             │
│  │  │  • Track escalations    │   │                                             │
│  │  │                         │   │                                             │
│  │  │  Tools:                 │   │                                             │
│  │  │  • flag_to_supervisor() │   │                                             │
│  │  └─────────────────────────┘   │                                             │
│  └─────────────────────────────────┘                                             │
│                                                                                  │
│  All agents communicate via:                                                    │
│  • Google ADK (Agent Development Kit)                                           │
│  • A2A Protocol (Agent-to-Agent Communication)                                  │
│  • Smart retry logic with exponential backoff                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Database Operations
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         💾 SQLITE DATABASE (database.py)                        │
│                              disaster_relief.db                                  │
│                                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────────┐  │
│  │  📦 INVENTORY      │  │  📝 REQUESTS       │  │  🚨 ACTION_ITEMS         │  │
│  │                    │  │                    │  │                          │  │
│  │  • id              │  │  • id              │  │  • id                    │  │
│  │  • name            │  │  • victim_name     │  │  • issue                 │  │
│  │  • category        │  │  • item_names      │  │  • severity              │  │
│  │  • quantity        │  │  • quantities      │  │  • status                │  │
│  │  • unit            │  │  • location        │  │  • created_at            │  │
│  │  • threshold       │  │  • status          │  │  • resolved_at           │  │
│  │  • buffer_stock    │  │  • priority        │  │                          │  │
│  │                    │  │  • created_at      │  │                          │  │
│  └────────────────────┘  │  • approved_at     │  └──────────────────────────┘  │
│                          │  • approved_by     │                                 │
│                          └────────────────────┘                                 │
│                                                                                  │
│  Real-time synchronization across all agents                                    │
│  Automatic stock deduction and replenishment                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                          🔧 SUPPORTING COMPONENTS                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  📦 CLIENT AGENTS (client_agents.py)                                            │
│     • VictimAgent: Client-side wrapper for victim interactions                 │
│     • SupervisorAgent: Client-side wrapper for supervisor interactions         │
│     • Handles A2A communication with backend                                    │
│                                                                                  │
│  🧰 TOOLS                                                                        │
│     • tools_client.py: Victim-side tools (extract, find, dispatch, escalate)   │
│     • tools_supervisor.py: Supervisor tools (inventory, approve, resolve)      │
│                                                                                  │
│  🧠 SMART MODEL (backend/smart_model.py)                                        │
│     • Custom retry logic with exponential backoff                               │
│     • Rate limit handling (ResourceExhausted errors)                            │
│     • Automatic fallback mechanisms                                             │
│     • Content filtering and safety settings                                     │
│                                                                                  │
│  🔐 ENVIRONMENT & CONFIGURATION                                                  │
│     • GOOGLE_API_KEY: Gemini AI authentication                                  │
│     • BACKEND_PORT: 8001 (A2A server)                                           │
│     • FRONTEND_PORT: 5000 (Flask UI)                                            │
│     • SESSION_SECRET_KEY: Flask session encryption                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                           📊 DATA FLOW EXAMPLE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Victim Request Flow:                                                           │
│  ────────────────────                                                           │
│  1. Victim: "I need 20 water bottles at Delhi"                                 │
│       ↓                                                                          │
│  2. Flask Frontend → A2A POST to Manager Orchestrator                           │
│       ↓                                                                          │
│  3. Manager: Detects "victim" → Routes to Victim Orchestrator                   │
│       ↓                                                                          │
│  4. Victim Orchestrator → Strategist Agent: Extract info                        │
│       ↓                                                                          │
│  5. Strategist: {item: "water bottles", quantity: 20, location: "Delhi"}       │
│       ↓                                                                          │
│  6. Item Finder: Fuzzy search → "Bottled Water" (95% match)                    │
│       ↓                                                                          │
│  7. Request Dispatcher: Check quantity (20 < 50) → Auto-approve                │
│       ↓                                                                          │
│  8. Database: Deduct 20 from "Bottled Water" inventory                         │
│       ↓                                                                          │
│  9. Response: "✅ Request approved! 20 Bottled Water dispatched to Delhi"      │
│                                                                                  │
│  Supervisor Action Flow:                                                        │
│  ──────────────────────                                                         │
│  1. Supervisor: "Show pending requests"                                         │
│       ↓                                                                          │
│  2. Manager → Supervisor Orchestrator → Approval Agent                          │
│       ↓                                                                          │
│  3. Approval Agent: Query database for status="pending"                         │
│       ↓                                                                          │
│  4. Return: List of 5 pending requests with details                             │
│       ↓                                                                          │
│  5. Supervisor: "Approve request 3"                                             │
│       ↓                                                                          │
│  6. Approval Agent: Update request status, deduct inventory, log approver       │
│       ↓                                                                          │
│  7. Response: "✅ Request #3 approved by admin_user"                            │
│                                                                                  │
│  Low Stock Alert Flow:                                                          │
│  ─────────────────────                                                          │
│  1. Inventory Manager: Detects "Tents" quantity (8) < threshold (10)           │
│       ↓                                                                          │
│  2. Escalation: Create action_item with severity="high"                         │
│       ↓                                                                          │
│  3. Supervisor Dashboard: Shows alert "⚠️ Tents low stock"                      │
│       ↓                                                                          │
│  4. Action Strategist: "Resolve shortage with buffer"                           │
│       ↓                                                                          │
│  5. Add buffer_stock (50) to current (8) → New quantity: 58                    │
│       ↓                                                                          │
│  6. Update action_item status="resolved"                                        │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                        🎯 KEY ARCHITECTURAL FEATURES                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ✅ Hierarchical Organization: 3-tier agent structure (Manager → Orchestrators  │
│     → Workers) enables intelligent delegation and specialization                │
│                                                                                  │
│  ✅ Context Preservation: Session management + conversation history maintains   │
│     full context across multi-turn interactions                                 │
│                                                                                  │
│  ✅ Autonomous Decision-Making: Agents make intelligent decisions based on      │
│     business rules (auto-approve < 50 items, escalate critical issues)          │
│                                                                                  │
│  ✅ Fuzzy Matching: 60% threshold allows typo-tolerant item search              │
│     ("waterbotles" → "Water Bottles")                                           │
│                                                                                  │
│  ✅ Real-time Synchronization: All agents share same SQLite database for        │
│     instant updates across supervisor and victim interfaces                     │
│                                                                                  │
│  ✅ Smart Retry Logic: Exponential backoff + rate limit handling ensures        │
│     reliability under high load or API throttling                               │
│                                                                                  │
│  ✅ Role-based Access: Victims can request, supervisors can manage inventory    │
│     and approve requests - clear separation of concerns                         │
│                                                                                  │
│  ✅ Audit Trail: Every request tracked with timestamps, approver names,         │
│     quantities, and status for full accountability                              │
│                                                                                  │
│  ✅ Proactive Alerts: Low stock detection + action items prevent stockouts      │
│     before they become critical                                                 │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                          🚀 TECHNOLOGY STACK                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  🤖 AI/ML:          Google Gemini 2.5 Flash (gemini-2.0-flash-exp)             │
│  🏗️  Framework:     Google ADK (Agent Development Kit)                          │
│  🔧 Backend:        FastAPI (async A2A server) + Uvicorn                        │
│  🎨 Frontend:       Flask (dual interfaces) + Jinja2 templates                  │
│  💾 Database:       SQLite (lightweight, file-based)                            │
│  🌐 Protocol:       A2A (Agent-to-Agent Communication)                          │
│  🔒 Security:       Flask-Session + environment variables                       │
│  ☁️  Deployment:    Render.com (auto-scaling, zero-downtime)                    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Architecture Highlights for Video

### Visual Flow Representation:
1. **User Layer**: Two interfaces (victim chat + supervisor dashboard)
2. **Web Layer**: Flask handling routes and sessions
3. **Intelligence Layer**: Manager orchestrator routing to specialized orchestrators
4. **Worker Layer**: 7 specialized agents with specific tools and capabilities
5. **Data Layer**: SQLite database with 3 core tables

### Key Message Points:
- **Hierarchical**: Manager → Orchestrators → Workers (clear chain of command)
- **Intelligent**: Agents understand context, make decisions, escalate when needed
- **Real-time**: All components synchronized via shared database
- **Scalable**: Each agent handles specific domain, can scale independently
- **Resilient**: Smart retry logic + error handling ensures reliability

---

This diagram shows the complete end-to-end architecture from user interfaces down to the database, highlighting the hierarchical agent structure that makes disaster relief coordination intelligent and efficient.
