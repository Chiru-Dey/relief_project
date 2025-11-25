# 🆘 Disaster Relief Management System

An intelligent, AI-powered disaster relief coordination platform that uses **Google's Gemini AI** and the **Agent Development Kit (ADK)** to create a sophisticated multi-agent system for managing relief operations during disasters.

![Python](https://img.shields.io/badge/python-3.13.5-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-red.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---


## 🌟 Overview

This system provides a complete disaster relief management solution with two primary interfaces:

1. **Victim Interface** - A conversational AI chat for disaster victims to request relief supplies
2. **Supervisor Dashboard** - An administrative control panel for managing inventory, approving requests, and coordinating relief operations

The system uses a hierarchical multi-agent architecture powered by Google's Gemini AI to intelligently process requests, manage inventory, and coordinate between victims and supervisors.

---

## ✨ Features

### 🤖 **Intelligent AI Agents**

- **Multi-Agent Orchestration** - Hierarchical agent system with specialized workers
- **Natural Language Processing** - Understands conversational requests in plain English
- **Context Preservation** - Remembers conversation history across multiple messages
- **Smart Item Matching** - Fuzzy matching with 60% similarity threshold handles typos
- **Automatic Escalation** - Flags insufficient stock and unavailable items for supervisor action

### 👥 **Dual User Interfaces**

#### Victim Chat Interface (`/`)
- Dark-themed, mobile-friendly design
- Text and voice input support
- Real-time AI responses
- Session persistence across page reloads
- Automatic notifications when requests are fulfilled

#### Supervisor Dashboard (`/supervisor`)
- Real-time inventory monitoring
- Request queue management with filtering
- One-click approve/reject/resolve actions
- Direct inventory management (add, delete, restock)
- Activity log with color-coded event tracking
- Batch operations support

### 📊 **Smart Request Processing**

- **Full Fulfillment** - Immediate dispatch when stock is available
- **Partial Fulfillment** - Automatically sends available quantity and escalates remainder
- **Auto-Dispatch** - Pending requests fulfilled automatically when items are restocked
- **Buffer Management** - Supervisors can resolve shortages with configurable buffer multipliers
- **Session Tracking** - Victims receive notifications for their specific requests

### 🔄 **Real-Time Operations**

- Live inventory updates
- Instant request status changes
- Automatic victim notifications
- Activity log streaming
- Cross-interface synchronization

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interfaces                          │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │  Victim Chat     │         │   Supervisor     │         │
│  │  (Port 5000)     │         │   Dashboard      │         │
│  └────────┬─────────┘         └────────┬─────────┘         │
└───────────┼──────────────────────────────┼──────────────────┘
            │                              │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │   Frontend Server (Flask)     │
            │   - Session Management        │
            │   - Task Queue                │
            │   - Activity Logging          │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │   Backend Server (FastAPI)    │
            │   - Agent Orchestration       │
            │   - A2A Communication         │
            └──────────────┬───────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                      │
┌───────▼────────┐                  ┌─────────▼─────────┐
│ Manager        │                  │  Database         │
│ Orchestrator   │                  │  (SQLite)         │
│                │                  │  - Inventory      │
│  Routes to:    │                  │  - Requests       │
│  ├─ Victim     │                  │  - Sessions       │
│  └─ Supervisor │                  └───────────────────┘
└────────┬───────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼────┐
│Victim│  │Super- │
│Agent │  │visor  │
│      │  │Agent  │
└──┬───┘  └───┬───┘
   │          │
   │   ┌──────┴─────────┐
   │   │                │
   │ ┌─▼──────┐  ┌─────▼────┐
   │ │Approval│  │Inventory │
   │ │Agent   │  │Manager   │
   │ └────────┘  └──────────┘
   │
   ├─ Item Finder
   ├─ Request Dispatcher
   └─ Strategist
```

### Technology Stack

**Backend:**
- **FastAPI** - High-performance API framework
- **Uvicorn** - ASGI server
- **Google ADK** - Agent Development Kit for A2A communication
- **Google Gemini 2.5 Flash** - AI model with retry logic

**Frontend:**
- **Flask** - Web framework with async support
- **Vanilla JavaScript** - No framework dependencies
- **WebAudio API** - Voice input support

**Database:**
- **SQLite** - Lightweight, file-based database

**AI & ML:**
- **Google Gemini AI** - Natural language processing
- **Fuzzy Matching** (difflib) - Typo correction
- **Multi-Agent System** - Hierarchical task delegation

---

## 🔧 Prerequisites

- **Python 3.11+** (tested with 3.13.5)
- **Google API Key** for Gemini AI models
- **pip** package manager
- **Git** (for cloning the repository)

---

## 📦 Installation

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd disaster-relief-system
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
GOOGLE_API_KEY=your_google_api_key_here
```

**Get your Google API Key:**
1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Create a new API key
4. Copy the key to your `.env` file

---

## ⚙️ Configuration

### Database Initialization

The database is automatically initialized on first run with seed data:

- **Inventory Items**: water_bottles, food_packs, medical_kits, blankets, batteries, tents, flashlights
- **Initial Stock Levels**: Varied quantities for testing

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Your Google Gemini API key | Required |
| `PORT` | Frontend server port | 5000 |
| `BACKEND_PORT` | Backend server port | 8001 |
| `FLASK_ENV` | Flask environment (production/development) | development |

---

## 🚀 Usage

### Starting the Application

You need to run **two servers** simultaneously:

#### Option 1: Manual (Development)

**Terminal 1 - Backend Server:**
```bash
python manager_server.py
```

**Terminal 2 - Frontend Server:**
```bash
python frontend_app.py
```

#### Option 2: Using Honcho (Recommended)

```bash
pip install honcho
honcho start
```

### Accessing the Interfaces

**Local Development:**
- **Victim Interface**: http://localhost:5000
- **Supervisor Dashboard**: http://localhost:5000/supervisor

**Production (Render):**
- **Victim Interface**: https://disaster-relief-app-ouof.onrender.com
- **Supervisor Dashboard**: https://disaster-relief-app-ouof.onrender.com/supervisor

---

## 🎮 User Guide

### For Disaster Victims

1. **Open the victim chat** at http://localhost:5000
2. **Type or speak your request** in natural language:
   - "I need 20 water bottles at Mumbai"
   - "Can I get 5 tents and 10 blankets in Delhi?"
   - "We need medical supplies in Chennai"
3. **Receive immediate response** with:
   - Confirmation of available items being dispatched
   - Information about items awaiting supervisor approval
   - Estimated wait times for out-of-stock items
4. **Get automatic notifications** when your requests are fulfilled

### For Supervisors

1. **Open the supervisor dashboard** at http://localhost:5000/supervisor
2. **Monitor inventory** in real-time
   - View current stock levels
   - Low-stock alerts
   - Quick restock actions
3. **Manage requests**
   - Review pending requests
   - Approve or reject requests
   - Resolve ACTION_REQUIRED items with one click
4. **Perform bulk operations**
   - Add new items to inventory
   - Restock multiple items
   - Use command center for advanced operations
5. **Track activity**
   - View all system actions in real-time
   - Color-coded event logging
   - Filter by type (success, error, system)


## 📚 API Documentation

### REST Endpoints

#### Victim Endpoints

**Submit Task**
```http
POST /api/submit_task
Content-Type: application/json

{
  "text": "I need 20 water bottles",
  "session_id": "session_123",
  "persona": "victim"
}
```

**Get Chat History**
```http
GET /api/victim_history/{session_id}

Response:
{
  "history": [
    {"sender": "user", "text": "I need water"},
    {"sender": "ai", "text": "Great news! ..."}
  ]
}
```

#### Supervisor Endpoints

**Get Supervisor Data**
```http
GET /api/supervisor_data

Response:
{
  "inventory": [...],
  "requests": [...]
}
```

**Restock Item**
```http
POST /api/admin/restock
Content-Type: application/json

{
  "item_name": "water_bottles",
  "quantity": 100
}
```

**Resolve Action Required**
```http
POST /api/admin/resolve/{request_id}

Response:
{
  "success": true,
  "message": "...",
  "dispatches": [...]
}
```

### Automated Testing

Coming soon: Unit tests and integration tests.

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 style guide for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Test your changes thoroughly
- Update documentation as needed

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Gemini AI** - Natural language processing
- **Google ADK** - Agent Development Kit
- **FastAPI** - High-performance API framework
- **Flask** - Web framework
- **SQLite** - Database engine

---


## 🗺️ Roadmap

### Upcoming Features

- [ ] PostgreSQL support for production deployment
- [ ] Docker containerization
- [ ] User authentication and authorization
- [ ] SMS/Email notifications for victims
- [ ] Real-time map visualization of requests
- [ ] Analytics dashboard for relief operations
- [ ] Multi-language support
- [ ] Mobile app (iOS/Android)
- [ ] Export reports (PDF, CSV)
- [ ] Integration with external logistics APIs

---

## 📊 Project Stats

- **AI Agents**: 8 specialized agents
- **Supported Items**: Unlimited (dynamic inventory)
- **Request Processing**: Real-time with <2s latency
- **Deployment**: Single-command deploy to Render

---

**Built with ❤️ for disaster relief operations**

*Making a difference, one request at a time* 🌍
