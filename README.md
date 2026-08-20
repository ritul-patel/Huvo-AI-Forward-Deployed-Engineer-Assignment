# Northstar Homes AI Sales Assistant

Northstar Homes AI Sales Assistant is a FastAPI-based conversational sales agent designed to qualify property buyers, answer supported project questions, handle objections, and simulate site-visit booking.

## 1. Project Overview

The application is an intelligent chat interface built for prospective real estate buyers exploring the Northstar One project. It solves the problem of providing 24/7, high-quality initial sales engagements without requiring immediate human intervention. 

Customers can ask questions, provide their property requirements, and book site visits directly through the chat. The agent acts as a Northstar Homes representative, naturally guiding the conversation to qualify the lead and collect necessary information. After the conversation ends, the system automatically processes the transcript to extract structured analytics and lead qualification scores for the sales team.

## 2. Assignment Requirements

| Requirement | Implementation |
| --- | --- |
| Natural conversation | Driven by Groq LLM with a strict persona prompt |
| Customer qualification | Extracts configuration, budget, purpose, and timeline |
| English, Hindi, Hinglish | Handled natively by the prompt and intent extraction regex |
| Conversation memory | Stateful dictionary (`CustomerContext`) stored per session |
| Intent handling | Deterministic regex-based engine for critical operations |
| Site visit booking | Simulated booking function with date/time parsing |
| Booking failure | Simulated weekday failure logic with fallback prompting |
| Human escalation | Detects requests to speak with a real person |
| Analytics extraction | Dedicated low-temperature LLM pipeline for JSON extraction |
| Proper conversation ending | Handles opt-outs and explicit follow-up requests |

## 3. Key Features

### Conversational Sales Agent
The assistant behaves strictly as a Northstar Homes representative. It avoids generic chatbot responses, refuses to invent property details, and focuses on understanding the customer's needs before attempting to close a booking.

### Customer Qualification
As the customer speaks, the backend deterministically extracts and remembers:
* configuration (e.g., 2 BHK, 3 BHK)
* budget (e.g., 2 crore)
* purpose (self-use vs investment)
* timeline (e.g., immediate, within 3 months)

### Objection Handling
The prompt instructs the LLM to identify and gracefully handle common objections, specifically price concerns, family discussion hesitation, and general indecision.

### Multilingual Conversation
The agent can process and respond in English, Hindi, and Hinglish. The intent engine uses multilingual regular expressions (e.g., "baad mein", "nahi chahiye") to ensure state transitions work accurately regardless of the language used.

### Conversation Memory
All extracted entities and state transitions are stored in a session-specific context dictionary on the backend. This context is injected into the system prompt on every turn, allowing the LLM to remember past statements without needing to parse the entire history repeatedly.

### Site Visit Booking
When the customer expresses interest and provides a date and time, the backend intercepts the state and attempts to generate a booking ID. If successful, the booking ID is injected into the LLM's context to relay to the customer.

### Booking Failure
If the customer requests an invalid slot (simulated as weekday visits), the backend returns a failure reason. The LLM is then instructed to politely explain the restriction and ask for an alternative weekend slot.

### Booking Cancellation
If a customer explicitly refuses or cancels a visit after a booking ID has been generated, the backend intercepts the intent, cancels the slot, and retains the cancelled booking ID in the analytics history.

### Follow-up
If the customer explicitly requests a callback (e.g., "Call me tomorrow"), the system flags `follow_up_required` as true for the sales team.

### Stop Communication
If the customer explicitly opts out, the backend halts further LLM generation and returns a standardized polite farewell.

### Analytics
An offline pipeline processes the chat transcript to generate structured JSON containing the final lead status, objections, and conversation outcome.

## 4. Customer Conversation Flow

The conversation is adaptive and does not force the customer through a rigid form. A typical successful interaction flows as follows:

Customer
  |
  v
Initial requirement
  |
  v
Configuration & Budget
  |
  v
Timeline / purpose / preferences
  |
  v
Questions and objections
  |
  +---- Site visit
  |        |
  |        +---- Available -> Booking
  |        |
  |        +---- Unavailable -> Failure handling
  |        |
  |        +---- Cancelled -> Cancellation handling
  |
  +---- Follow-up
  |
  +---- Stop communication
  |
  v
Conversation analytics

## 5. Architecture Overview

The system uses a decoupled architecture where the backend maintains absolute control over the state machine, and the LLM acts purely as a stateless conversational engine.

Customer
   |
   v
Frontend Chat UI
   |
   v
FastAPI Backend
   |
   +--> Conversation State
   |
   +--> Intent Engine
   |
   +--> Site Visit Logic
   |
   +--> Prompt Construction
   |
   +--> Groq LLM
   |
   +--> Analytics Extraction
   |
   v
Frontend Response + Analytics

For detailed architectural decisions, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 6. Technology Stack

* **Python**: Core programming language.
* **FastAPI**: Provides robust, asynchronous REST APIs and dependency injection.
* **Groq**: Provides low-latency inference for the conversational agent.
* **openai/gpt-oss-20b**: The specific model used for both chat and analytics extraction.
* **React / Vite / TypeScript**: Powers the frontend user interface and analytics dashboard.

## 7. Project Structure

```text
project/
├── backend/
│   ├── .env.example
│   ├── analytics.py        (Transcript to JSON extraction)
│   ├── booking.py          (Simulated booking integration)
│   ├── conversation.py     (In-memory session state)
│   ├── intent.py           (Regex intent and entity engine)
│   ├── llm.py              (Groq API integration)
│   ├── main.py             (FastAPI routes and orchestration)
│   ├── models.py           (Pydantic schemas)
│   ├── prompt.py           (System prompts)
│   └── requirements.txt
├── docs/
│   └── ARCHITECTURE.md
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   └── main.tsx
│   ├── index.html
│   └── package.json
├── .gitignore
└── README.md
```

## 8. Setup and Running

### Prerequisites
* Python 3.10+
* Node.js 18+
* A valid Groq API Key with access to `openai/gpt-oss-20b`

### Installation

**Backend**
```bash
cd backend
python -m venv .venv
# Activate virtual environment (Windows: .venv\Scripts\activate, Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

**Frontend**
```bash
cd frontend
npm install
```

### Environment Variables
Create a `.env` file in the `backend/` directory:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Create a `.env` file in the `frontend/` directory:

```env
VITE_API_URL=http://localhost:8000
```

### Start Backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Start Frontend
```bash
cd frontend
npm run dev
```

### Open Application
Navigate to `http://localhost:5173` in your browser.

## 9. Prompt Engineering

### Northstar Homes Persona
The system prompt strictly defines the assistant as a representative of Northstar Homes. It is instructed to be polite, professional, and entirely focused on real estate sales without breaking character.

### Conversation Behavior
The agent is constrained to write 1 to 3 concise sentences per response. It is explicitly instructed to avoid interrogation-style behavior. Instead of asking a list of questions, it organically integrates qualification questions into natural conversational flow.

### Grounded Information
The prompt contains strict anti-hallucination guardrails. The agent is forbidden from inventing prices, amenities, availability, discounts, or possession dates. If a customer asks a question outside the provided project context, the agent gracefully deflects and offers to connect them with a human representative.

### Objections
The agent is trained to recognize price objections (e.g., "That is out of my budget") and hesitation (e.g., "I need to discuss with my family"). It acknowledges these concerns politely rather than aggressively pushing for a sale.

### Conversation Ending
The agent supports natural goodbyes, acknowledging follow-up requests ("I will have someone call you next week"), and confirming successful or cancelled site visits.

## 10. Testing

| # | Scenario | Input / Action | Expected Behavior | Result |
| - | -------- | -------------- | ----------------- | ------ |
| 1 | Basic qualification | "I want a 3 BHK" | Extracts configuration = 3 BHK | PASS |
| 2 | Budget extraction | "My budget is 2 crore" | Extracts budget = 2 crore | PASS |
| 3 | Requirements change | "Actually make it a 2 BHK" | Updates configuration = 2 BHK | PASS |
| 4 | Price objection | "That is too expensive" | Logs price objection, handles politely | PASS |
| 5 | Unknown info | "Do you have a swimming pool?" | Deflects to a human representative | PASS |
| 6 | Hinglish conversation | "Site visit baad mein karunga" | Extracts timeline/intent without crashing | PASS |
| 7 | Successful site visit | "Saturday at 11 AM" | Triggers booking, returns NS- booking ID | PASS |
| 8 | Invalid weekday booking | "Monday at 11 AM" | Booking fails, prompts for weekend slot | PASS |
| 9 | Booking cancellation | "Actually don't book it" | Cancels existing ID, sets status to cancelled | PASS |
| 10 | Explicit callback | "Call me tomorrow" | Sets follow_up_required = true | PASS |
| 11 | Stop communication | "Stop messaging me" | Halts LLM generation, sets stopped status | PASS |

## 11. Example Conversation

**Customer:** Hi, I am looking for a 3 BHK.  
**Assistant:** Welcome to Northstar Homes! We do have 3 BHK apartments available at Northstar One starting from ₹1.75 crore. Do you have a specific budget in mind?  
**Customer:** My budget is exactly 1.75 crore. Can I see it?  
**Assistant:** That fits perfectly. I would be happy to arrange a site visit for you. What day and time works best for you this weekend?  
**Customer:** Saturday at 11 AM.  
**Assistant:** Fantastic. Your site visit is confirmed for Saturday at 11 AM (Booking ID: NS-1). We look forward to showing you the property!  
**Customer:** Actually, cancel that. I need to check my schedule.  
**Assistant:** Not a problem, I have cancelled your booking. Take your time, and just let me know when you are ready to reschedule.

## 12. Limitations

* **Simulated Availability:** The booking engine uses simulated logic (e.g., rejecting weekdays) rather than checking a real database.
* **In-Memory State:** Conversation history is stored in memory (`conversation.py`). Restarting the server clears active sessions.
* **Regex Extraction:** Initial intent extraction relies on regular expressions. While fast and deterministic, highly unusual phrasing might bypass the regex and rely purely on the LLM.

## 13. Future Improvements

* **Persistent Database:** Migrate `CustomerContext` and conversation history to PostgreSQL or Redis.
* **Real CRM Integration:** Push final analytics JSON directly into Salesforce or HubSpot.
* **Real Inventory Validation:** Connect `booking.py` to a real calendar or availability API.
* **Live Human Handoff:** Route the chat session to a live agent dashboard when `human_escalation` is triggered.

## 14. Assignment Summary

The Northstar Homes AI Sales Assistant demonstrates a production-style approach to conversational AI. By strictly decoupling deterministic state management (FastAPI) from natural language generation (Groq LLM), the system achieves reliable lead qualification, robust booking simulation, and structured analytics extraction while maintaining a natural, multilingual customer experience.
