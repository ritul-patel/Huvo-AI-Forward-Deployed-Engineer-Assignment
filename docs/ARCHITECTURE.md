# Northstar Homes AI Sales Assistant Architecture

## 1. Architecture Goals

The architecture of the Northstar Homes AI Sales Assistant was designed with several strict engineering goals:
* **Stateful conversation**: Retain customer details (budget, configuration) natively on the server without relying entirely on the LLM's context window.
* **Reliable booking state**: Ensure site visits and cancellations are governed by deterministic backend logic rather than LLM hallucination.
* **Natural conversational experience**: Allow the LLM full control over the tone and exact wording of the output as long as it adheres to the prompt rules.
* **Simple backend**: Keep the FastAPI layer lightweight while relying on regex intent parsing for speed.
* **Structured analytics**: Decouple the fluid conversation from the rigid data requirements by using a separate LLM pass for post-conversation extraction.

## 2. System Context

The system consists of interconnected layers:
* **Customer**: Interacts with the frontend UI.
* **Frontend (React)**: Handles the visual chat interface and analytics dashboard.
* **FastAPI Backend**: The central orchestrator that maintains state, parses intents, and communicates with the LLM.
* **Intent Engine**: A regex-based Python module that intercepts critical intents (stop, book, cancel) before they reach the LLM.
* **Booking Logic**: A mocked integration layer simulating calendar availability and booking ID generation.
* **Groq / Prompt Layer**: The stateless LLM integration that provides human-like responses based on the backend-injected context.
* **Analytics**: A secondary LLM pipeline that converts transcripts into structured JSON data.

## 3. High-Level Architecture

```text
+-------------------+
| Customer (Web UI) |
+---------+---------+
          | (HTTP POST /chat)
          v
+-------------------+
|  FastAPI Backend  |
|  (main.py)        |
+---------+---------+
          |
          | 1. State / Intent Engine (intent.py, conversation.py)
          +--------------------------------------------+
          |                                            |
          | 2. Booking Simulator (booking.py)          |
          +--------------------------------------------+
          |                                            |
          | 3. Prompt Construction & Groq (llm.py)     |
          +--------------------------------------------+
          |
          v (HTTP POST /analytics)
+-------------------+
| Analytics Engine  |
| (analytics.py)    |
+-------------------+
```

## 4. Detailed Request Lifecycle

When a customer sends a message to the `/chat` endpoint, the following sequence occurs:

1. **Customer sends message**: The frontend sends a JSON payload containing the `session_id` and `message`.
2. **FastAPI receives request**: `main.py` handles the route.
3. **Conversation state is loaded**: The in-memory `CustomerContext` dictionary is retrieved.
4. **Intent and Entity Extraction**: `intent.py` runs regex pattern matching to extract basic intents (stop communication, site visit interest, escalation) and entities (configuration, budget, date).
5. **State is updated**: The extracted entities and intents are written to the `CustomerContext` immediately.
6. **Booking logic runs**: If the state machine detects that the customer is ready to book, the booking logic executes.
7. **Prompt/context is constructed**: A massive system prompt is assembled containing the persona instructions, the conversation history, the updated `CustomerContext`, and any tool output (e.g., booking ID or failure reason).
8. **Groq model is called**: The backend queries the `openai/gpt-oss-20b` model via the Groq API.
9. **Response is processed**: The LLM's text output is saved to the conversation history.
10. **Lead Quality updated**: A localized heuristic function updates the lead score.
11. **Response is returned to frontend**: The final JSON payload containing the LLM message and updated state is sent back to the client.

## 5. Prompt Architecture

The system relies on a single, comprehensive system prompt constructed dynamically in `prompt.py`. The prompt is divided into strict sections:
* **Persona**: Establishes the agent as a Northstar Homes representative.
* **Project Details**: Hardcoded facts about Northstar One to prevent hallucination.
* **Rules**: Strict behavioral constraints (e.g., do not ask a list of questions, do not invent prices).
* **Dynamic Context Injection**: The backend injects the `CustomerContext` JSON string directly into the prompt so the LLM is aware of what the backend already knows.
* **Tool Context Injection**: When the backend performs an action (like a booking or cancellation), it injects a highly specific command instructing the LLM on exactly how to relay the result to the user.

## 6. Conversation State and Memory

Conversation state is managed entirely in `conversation.py` using an in-memory Python dictionary keyed by `session_id`.

* **What is remembered**: configuration, budget, purpose, timeline, language, objections, site visit state, human escalation, and follow-up requirements.
* **How it is passed**: The state is serialized to a dictionary and injected into the LLM system prompt on every turn.
* **How it updates**: New entity extraction updates replace old information. For example, if a customer says "I want a 2 BHK", and later says "Actually, a 3 BHK", the intent engine replaces the configuration key with "3 BHK".

## 7. Intent Handling

Intent handling is performed through explicit Python code using regex patterns in `intent.py`. It does not rely on structured LLM output or a dedicated ML classifier. This was chosen for zero-latency execution and absolute deterministic control.

The system extracts:
* **Configuration**: e.g., "2 bhk", "3 bhk"
* **Budget**: e.g., "1.5 cr", "2 crore"
* **Purchase timeline**: e.g., "immediate", "next month"
* **Objection**: e.g., "expensive", "family", "too far"
* **Site visit / Cancellation**: e.g., "book", "visit", "cancel", "don't book"
* **Follow-up**: e.g., "call me", "remind me"
* **Stop communication**: e.g., "stop", "unsubscribe"

## 8. Site Visit State Machine

The site visit lifecycle is strictly governed by `main.py`.

```text
not_requested
     |
     v
requested
     |
     v
awaiting_date (or awaiting_time)
     |
     v
ready_to_book
     |
     +---- Valid Date/Time ----> confirmed (Booking ID Generated)
     |
     +---- Invalid Date -------> failed (Prompt asks for weekend slot)
```

Cancellation flow:
```text
confirmed
    |
    v
cancelled
```

If the customer provides a date/time and confirms the booking, the backend generates an ID in the format `NS-<number>`. The LLM is forced to use this ID. If the customer subsequently requests a cancellation, the backend changes the status to `cancelled` and intercepts the LLM to confirm the cancellation.

## 9. Failure Handling

The architecture is designed to handle failure paths gracefully:
* **Unavailable weekday**: The mock booking engine explicitly rejects weekdays. The backend injects a "BOOKING FAILED" tool context instructing the LLM to apologize and ask for a weekend.
* **Invalid slot**: Similar to weekdays, invalid formats reject at the backend and prompt the LLM to ask for a specific date.
* **Unsupported information**: The prompt explicitly forces the LLM to escalate to a human representative when asked about unprovided property details.
* **Stop communication**: If the intent engine detects a stop command, the backend short-circuits the entire request. The LLM is bypassed, and a hardcoded polite response is returned.

## 10. Analytics Pipeline

Analytics extraction is an offline pipeline triggered via the `/analytics` endpoint.

Conversation Transcript
|
v
Information extraction (Low-temperature LLM Prompt)
|
v
Structured JSON (Lead data)
|
v
State Merge (Backend overrides LLM with authoritative IDs and flags)
|
v
Analytics Panel

The pipeline extracts fields such as customer name, language, budget, objections, and timeline. The backend merges this LLM JSON with its own deterministic state (e.g., ensuring `follow_up_required` exactly matches the backend flag) to prevent hallucinations.

## 11. Frontend Architecture

The frontend is a lightweight React/Vite application. It relies entirely on the FastAPI backend for logic.

* **Chat Interface**: Renders the conversation.
* **MessageBubble**: Displays individual user or assistant messages.
* **ChatInput**: Handles text submission and loading states.
* **AnalyticsPanel**: A hidden administrative view that calls the `/analytics` endpoint and renders the structured lead JSON into a dashboard format.
* **api.ts**: Centralizes all Axios HTTP calls to the FastAPI server.

## 12. Backend Architecture

The Python backend is organized into distinct functional modules:
* **`main.py`**: FastAPI entry point, route definitions, and the orchestrator of the chat lifecycle.
* **`models.py`**: Pydantic schemas for request/response validation.
* **`conversation.py`**: In-memory session and state storage.
* **`intent.py`**: Deterministic regex extraction engine.
* **`booking.py`**: The mock external booking integration.
* **`prompt.py`**: System prompt templates.
* **`llm.py`**: The Groq API client integration.
* **`analytics.py`**: The analytics JSON extraction pipeline.

## 13. LLM Integration

* **Provider**: Groq.
* **Model**: `openai/gpt-oss-20b`.
* **API Request Flow**: The backend uses the official Python Groq SDK.
* **Error Handling**: The backend catches `RateLimitError` and general exceptions, returning clean HTTP 429 or 502 error codes to the frontend.

## 14. Data Flow

```text
Customer Message
       |
       v
Frontend (api.ts)
       |
       v
FastAPI (main.py /chat)
       |
       +---- Intent Engine (Regex parsing)
       |
       +---- Conversation State (Update entities)
       |
       +---- Booking Logic (Attempt booking if ready)
       |
       +---- Prompt Construction (Inject state and tool results)
       |
       v
Groq LLM (Generate Response)
       |
       v
FastAPI (Store Response)
       |
       v
Frontend (Update UI)
```

## 15. Security and Configuration

The application is configured via environment variables.

* **`GROQ_API_KEY`**: Stored securely in a local `.env` file.
* **`.env.example`**: Provided in the repository with placeholder values to instruct developers.
* **`.gitignore`**: Ensures that `.env` files containing real API keys are never committed to version control.

## 16. Design Decisions

* **Why FastAPI?**: Chosen for its high performance, native async support, and excellent Pydantic data validation.
* **Why Prompt-Driven Agent Behavior?**: Using a carefully tuned system prompt allows the assistant to handle complex linguistic nuances (Hinglish, varying tones) much more naturally than a rigid dialogue tree.
* **Why Deterministic Intents over LLM Function Calling?**: Regex-based intent extraction was chosen for absolute reliability and zero latency. Critical paths like "stop communication" or "cancel booking" cannot rely on probabilistic LLM function calls.
* **Why Structured Analytics via LLM?**: Extracting analytics offline allows the main chat loop to remain extremely fast, while still harnessing the LLM's power to summarize and structure messy conversational data.

## 17. Failure and Edge Case Strategy

* **Customer changes requirements**: The intent engine overwrites old entities with new ones (e.g., 2 BHK becomes 3 BHK).
* **Customer objects to price**: The LLM acknowledges the concern politely based on prompt rules.
* **Booking is cancelled**: The deterministic backend recognizes the cancellation intent, updates the state, and forces the LLM to confirm the cancellation.
* **Stop communication**: The backend short-circuits the LLM, ensuring the customer is not bothered further.

## 18. Current Limitations

* **In-Memory State**: Session data is lost if the FastAPI server restarts.
* **Mocked Availability**: The booking engine simulates availability via code logic rather than checking a real database.

## 19. Future Architecture

Future iterations of this system could implement:
* **Persistent Database**: Migrating session state to PostgreSQL or Redis.
* **CRM Integration**: Pushing structured analytics data directly into Salesforce or HubSpot.
* **Calendar Integration**: Connecting `booking.py` to Google Calendar or a proprietary inventory system.
* **Human Handoff**: Opening a websocket connection to a live agent dashboard when the escalation intent is detected.
