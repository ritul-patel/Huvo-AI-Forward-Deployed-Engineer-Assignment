# Northstar Homes AI Sales Assistant

## 1. Project Overview

This repository contains the Northstar Homes AI sales assistant created for the Huvo AI Forward Deployed Engineer assignment. 

The application provides a conversational chat UI where customers can interact with the AI assistant. The system is designed to understand customer requirements and gently guide them toward a simulated site visit. It specifically handles:
- Customer requirements discovery
- Configuration qualification (e.g., 2 BHK or 3 BHK)
- Budget qualification
- Purchase timeline
- Purpose of purchase (self-use or investment)
- Handling customer objections (e.g., price concerns)
- Handling follow-up requests
- Handling stop-communication requests
- Escalating unknown questions to a human agent
- Site-visit booking simulation
- Booking failure scenarios
- Booking cancellation
- Real-time conversation analytics extraction

## 2. Assignment Requirements Covered

| Requirement | Implementation |
|---|---|
| Natural conversation | Driven by the `openai/gpt-oss-20b` model via Groq, providing contextual and conversational responses. |
| Customer qualification | System prompts gently guide the LLM to extract budget, configuration, timeline, and purpose without aggressive interrogation. |
| English | Natively supported by the LLM and intent extraction engine. |
| Hindi | Supported via LLM capability and transliterated Hindi regex patterns in the intent engine. |
| Hinglish | Handled seamlessly by the LLM and specific keyword matching in the backend. |
| Conversation memory | A robust in-memory `CustomerContext` dictionary ensures the latest customer details overwrite older ones. The LLM always sees the current state. |
| Intent handling | Deterministic regex patterns intercept critical intents (e.g., Stop, Escalate, Booking) before they reach the LLM. |
| Common objections | The LLM prompt includes guidelines for handling price, location, and family-decision objections naturally without inventing discounts. |
| Busy customers | Intent engine extracts "busy" keywords and gracefully flags the conversation for follow-up. |
| Uninterested customers | Extracted via intent rules. The bot gracefully acknowledges and can stop communication. |
| Requests to contact later | Sets `follow_up_required = True` in the backend state and confirms with the customer. |
| Requests to stop communication | Sets `communication_active = False` in the backend, blocking further LLM processing and respecting user privacy. |
| Unknown questions | The LLM is strictly prompted to admit lack of knowledge for unprovided facts (like rental yields) and trigger human escalation. |
| Site-visit booking | Simulated via an internal backend state machine. The LLM is only provided the resulting booking ID to relay. |
| Booking failure | Simulated gracefully. An unresolvable date triggers a failure in the backend, and the LLM suggests alternative slots. |
| Booking cancellation | If a customer refuses a visit after confirmation, the backend cancels the active booking and updates the state. |
| Human escalation | Flagged in the backend via regex intents or LLM fallback behavior, updating the analytics payload accordingly. |
| Proper conversation ending | Handled natively by the LLM when intent extraction flags a stop or final confirmation. |
| Analytics extraction | The backend merges deterministic flags (like follow-ups) with LLM-extracted entities into a structured JSON analytics object. |

## 3. Key Features

- **LLM for natural conversation:** The application uses a Large Language Model to ensure conversations feel natural, empathetic, and human-like.
- **Deterministic backend logic for critical business state:** The LLM is strictly limited to conversation. The backend controls the actual state machine for bookings, cancellations, and opt-outs.
- **Conversation memory:** Customer context is continuously updated and injected into the system prompt at every turn, ensuring the LLM is always aware of the latest facts.
- **Intent and entity extraction:** Lightweight regex patterns identify critical paths (like stop-communication or visit interest) to ensure 100% reliable business logic routing.
- **Multilingual handling:** Code and prompts are designed to gracefully accept and respond to English, Hindi, and Hinglish inputs.
- **Site-visit state machine:** A controlled flow (Not Requested -> Awaiting Date/Time -> Confirmed/Failed) prevents the LLM from inventing fake appointments.
- **Analytics extraction:** Merges reliable backend intent flags with LLM entity extraction to generate a final, accurate JSON analytics profile.
- **Anti-hallucination rules:** The prompt strictly forbids the LLM from inventing prices, amenities, availability, or discounts. **The LLM is NOT trusted with authoritative booking state.**

## 4. How to Run the Bot

### Prerequisites

- Python 3.12 (or compatible 3.x version)
- Node.js
- Groq API key

### Backend

Open a terminal and set up the backend:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:
- On Windows: `.venv\Scripts\activate`
- On macOS/Linux: `source .venv/bin/activate`

Install dependencies:
```bash
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory by copying `.env.example`:
```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Start the FastAPI server:
```bash
uvicorn main:app --reload --port 8000
```

### Frontend

Open a second terminal and set up the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available locally at `http://localhost:5173`. Open this URL in your browser to interact with the bot.

## 5. Project Structure

```text
backend/
  main.py
  prompt.py
  intent.py
  conversation.py
  booking.py
  analytics.py
  llm.py
  models.py
  requirements.txt
  .env.example
frontend/
  package.json
  vite.config.ts
  src/
    App.tsx
    api.ts
    components/
tests/
  test_api.py
  test_booking.py
  test_conversation.py
  test_intent.py
docs/
  ARCHITECTURE.md
README.md
```

## 6. Architecture Overview

```text
Customer
   |
   v
Frontend
   |
   v
FastAPI (backend/main.py)
   |
   +--> Conversation memory (conversation.py)
   +--> Intent/entity extraction (intent.py)
   +--> Prompt construction (prompt.py)
   +--> Groq LLM (llm.py)
   +--> Booking state machine (booking.py)
   +--> Analytics (analytics.py)
   |
   v
Response
```

The most important architectural principle of this system is separation of concerns. The LLM handles natural language generation and conversational empathy, while deterministic backend logic remains the absolute source of truth for critical state such as:
- booking
- cancellation
- communication stop
- structured customer state where applicable

For a deeper dive into the system design, please see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 7. Key Assumptions

- Northstar One information available to the agent is intentionally limited.
- The known project information includes:
  - Project: Northstar One
  - Location: Sector 79, Gurugram
  - 2 BHK and 3 BHK options
  - 2 BHK starting price: Rs 1.35 crore
  - 3 BHK starting price: Rs 1.75 crore
- The agent must not invent unavailable project information.
- Site visits are simulated entirely in memory.
- There is no real calendar integration.
- There is no real CRM integration.
- Conversation state is stored in memory for the assignment demo (it will reset if the server restarts).
- Booking IDs are simulated and sequential.

## 8. Known Limitations

These are intentional assignment-scope limitations, not implementation failures:
- Limited project knowledge (the bot only knows what is explicitly defined in its prompt).
- No live inventory or pricing database.
- No real calendar API integration for bookings.
- No real CRM integration for lead capture.
- In-memory conversation state (sessions do not persist across server reboots).
- Booking simulation only (no actual emails or calendar invites are sent).
- Booking IDs are not persistent in a database.
- Human escalation is represented by application logic and analytics flags rather than a real-time agent handoff.

## 9. AI Tools Used

- **Groq API**: Used as the inference engine for extreme low-latency responses.
- **Model**: `openai/gpt-oss-20b` (Configured via the `.env` file).
- **LLM Usage**: Used for LLM-based conversational generation and LLM-based analytics extraction.
- **Prompt Engineering**: Core behavior is shaped by detailed persona rules located in `backend/prompt.py`.
- **Backend Rules**: Deterministic regex intent/entity extraction is implemented in `backend/intent.py` to augment LLM capabilities.

*Note: Antigravity IDE and Claude 3.5 Sonnet were used strictly as development tooling to assist in writing and structuring the application code. They are not part of the runtime application.*

## 10. Testing

Automated tests are written using `pytest`. The current automated test result is:

**11 passed**
**0 failed**

The automated suite covers core behavior such as:
- qualification
- budget/configuration extraction
- Hinglish parsing
- conversation memory updates
- follow-up requests
- stop communication triggers
- successful booking
- booking failure
- cancellation
- API behavior
- unknown information handling
- price objection handling

Major manual scenarios tested through the UI include:
- normal qualification flow
- 2 BHK to 3 BHK change mid-conversation
- budget changes
- price objection
- family decision delays
- investment intent
- unknown project questions
- English, Hindi, and Hinglish dialogue
- successful site visit
- failed site visit
- cancellation
- callback request
- stop communication

## 11. Prompt Engineering Approach

### Persona
The assistant behaves strictly as a Northstar Homes representative rather than presenting itself as a generic AI assistant. It maintains a professional, sales-oriented, but helpful tone.

### Natural conversation
The prompt encourages short, contextual responses and avoids repetitive interrogation. It reads like a WhatsApp chat rather than a robotic form.

### Qualification
The assistant gathers information such as configuration, budget, purpose, and timeline gently over the course of the conversation without repeatedly asking for information already provided.

### Language
The prompt explicitly supports and responds natively to English, Hindi, and Hinglish.

### Objections
Handles price concerns, family discussion, hesitation, being busy, lack of interest, requests to contact later, and requests to stop communication through empathetic, pre-defined behavioral guardrails.

### Grounding
The prompt strictly prevents the model from inventing prices, discounts, availability, amenities, possession dates, rental yield, investment returns, or unsupported project facts.

### Booking safety
The model does not independently create authoritative booking IDs. Booking state is controlled entirely by backend logic, and the LLM simply relays the exact success or failure context injected into its prompt.

### Analytics
Analytics are generated from the conversation context, while critical backend state (like follow-up status or escalation) remains authoritative and overrides the LLM if conflicts occur.

## 12. Example Conversation

**Customer**: Hi, I'm looking for a flat in Gurgaon.
**Assistant**: Hello! Welcome to Northstar Homes. We have a premium residential project, Northstar One, located in Sector 79, Gurugram. Are you looking for a 2 BHK or a 3 BHK?
**Customer**: 3 BHK. What is the price?
**Assistant**: Our 3 BHK apartments start at Rs 1.75 crore. Does this fit within your budget?
**Customer**: Yes, that works. I want to move in soon.
**Assistant**: That sounds great. To help you experience the property, would you like to schedule a site visit? 
**Customer**: Yes, book it for Saturday at 11 AM.
**Assistant**: Excellent! Your site visit for Saturday at 11 AM is confirmed. Your booking ID is NS-1001. We look forward to seeing you at Northstar One!

## 13. Submission Notes

The current booking implementation supports site visits on any resolvable day of the week, including weekdays. Booking failure is demonstrated deterministically in the test suite using an unresolvable date format (`2099-01-01`).
