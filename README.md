# Shubham AI — RAG-Powered Voice Interview Assistant

An AI-powered representative system built for recruiters to learn about **Shubham Shukla** through voice or text. The system answers questions grounded strictly in a curated knowledge base and supports full interview scheduling via Google Calendar integration.

## What It Does
- Recruiters ask questions via voice or text about Shubham's projects, skills, and experience
- Answers are grounded in a custom RAG pipeline — no fabricated claims
- Supports meeting scheduling through a Google Calendar booking link (with auto-generated Google Meet invites)
- Includes a phone-based Vapi voice agent for live interview calls
- Deployed in production via Docker

## Tech Stack

### Backend
| Component | Technology |
|-----------|------------|
| Framework | FastAPI (Python 3.10+) |
| LLM | Groq — Llama 3.1 8B Instant (`llama-3.1-8b-instant`) |
| Embeddings | sentence-transformers — `all-MiniLM-L6-v2` (local, 384-dim) |
| Vector DB | ChromaDB (persisted to disk) |
| Voice Agent | Vapi (real-time STT + TTS) + Twilio (phone number) |
| Scheduling | Google Calendar booking URL + Google Meet links |
| Containerization | Docker (Python 3.11-slim) |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | React 18 + Vite 6 |
| Styling | Tailwind CSS 3 |
| Language | TypeScript (strict) |
| HTTP | Fetch (built-in) |
| Animations | Framer Motion |

## Architecture

```
Recruiter (voice / text)
        │
        ▼
    ┌───────┐
    │  Vapi │  ← STT + TTS layer (real-time voice)
    └───┬───┘
        │ text query
        ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Backend                       │
│                                                         │
│  ┌────────────┐      ┌─────────────────┐                │
│  │  main.py   │─────►│   api/chat.py   │                │
│  │  (routes)  │      │  RAG pipeline   │                │
│  └────────────┘      └────────┬────────┘                │
│                               │                         │
│       ┌───────────┬───────────┼───────────┬─────────┐   │
│       ▼           ▼           ▼           ▼         ▼   │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐ ┌──────┐│
│  │retriever│ │generator │ │embed-  │ │vector_  │ │chunker││
│  │  .py    │ │  .py     │ │dings.py│ │store.py │ │ .py  ││
│  │Chroma+  │ │Groq LLM  │ │MiniLM  │ │ChromaDB │ │text  ││
│  │MiniLM   │ │          │ │local   │ │persist  │ │split ││
│  └─────────┘ └──────────┘ └────────┘ └─────────┘ └──────┘│
│                                                         │
│  ┌──────────────────────────────────────────────────────┐│
│  │  api/voice.py — Vapi webhooks + tool execution      ││
│  │  services/voice_agent.py — tools, prompt, config     ││
│  │  services/calendar.py — Google Calendar manager      ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────┐
│   React UI   │  ← ChatContainer, ChatInput, MessageBubble, BookCallModal
│   (Vite)     │
└──────────────┘
```

## RAG Pipeline

- **Ingestion** (`scripts/ingest.py`) — PDFs and Markdown files from `data/raw/` are loaded, chunked at ~1,500 chars (300 char overlap), embedded with `all-MiniLM-L6-v2`, and persisted to ChromaDB under `data/index/chroma/`.
- **Retrieval** (`services/retriever.py`) — user query is embedded and used for top-k semantic search against the Chroma collection; chunks below `min_score` are filtered out.
- **Generation** (`services/rag.py` + `services/generator.py`) — retrieved context + system prompt + query → Groq Llama 3.1 8B → grounded response with source citations.

## Anti-Hallucination Design

- **System prompt** (`app/prompts/system_prompt.py`) enforces retrieval-only answers — model cannot answer outside the knowledge base
- **Out-of-context queries** return a canonical refusal phrase; nothing else
- **Prompt injection attempts** are detected and deflected
- **Temperature 0.0** for deterministic outputs
- **Max tokens capped** for concise answers

## Project Structure

```
shubham-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, lifespan, CORS, exception handlers
│   │   ├── api/
│   │   │   ├── chat.py             # POST /api/chat — RAG pipeline entry
│   │   │   └── voice.py            # /api/voice/* — Vapi webhooks + tool execution
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic settings (env-driven)
│   │   │   └── logging.py          # Logger configuration
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── prompts/
│   │   │   └── system_prompt.py    # Grounded persona system prompt
│   │   └── services/
│   │       ├── rag.py              # RAG orchestrator
│   │       ├── retriever.py        # ChromaDB query wrapper
│   │       ├── generator.py        # Groq LLM client
│   │       ├── embeddings.py       # sentence-transformers client
│   │       ├── vector_store.py     # ChromaDB persistent client
│   │       ├── chunker.py          # Text chunking
│   │       ├── document_loader.py  # PDF / MD / DOCX / TXT / JSON loaders
│   │       ├── calendar.py         # Google Calendar manager
│   │       └── voice_agent.py      # Vapi agent, tools, config
│   ├── scripts/
│   │   └── ingest.py               # Build the ChromaDB index
│   ├── data/
│   │   ├── raw/                    # Source knowledge base (PDF, MD)
│   │   └── index/                  # ChromaDB persisted index
│   ├── tests/                      # Test directory (placeholder)
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── Dockerfile
│   ├── .dockerignore
│   └── .env                        # API keys (gitignored)
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # Chat shell with 3 themes
│   │   ├── main.tsx                # React entry
│   │   ├── index.css
│   │   ├── components/
│   │   │   ├── ChatContainer.tsx   # Main chat UI + animation
│   │   │   ├── ChatInput.tsx       # Input box with voice typing
│   │   │   ├── MessageBubble.tsx   # Renders messages + source citations
│   │   │   └── BookCallModal.tsx   # Booking modal
│   │   ├── hooks/
│   │   │   └── useVoiceTyping.ts   # SpeechRecognition wrapper
│   │   ├── services/
│   │   │   └── api.ts              # chatAPI client
│   │   └── types/
│   │       └── index.ts            # ChatMessage, Source, ChatRequest, ChatResponse
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── .env                        # Vite env vars (gitignored)
├── .gitignore
├── .dockerignore
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## Quick Start

### 1. Clone & Setup Backend

```bash
cd backend

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # Fill in your API keys
```

### 2. Add Knowledge Base

Place documents under `backend/data/raw/`:

- `SHUBHAM_SHUKLA_MASTER_PROFILE.md` — personal facts
- `UpdatedCV.pdf` — resume
- `navdristi.md`, `teraavison.md`, `visitor.md` — project notes

### 3. Ingest Documents

```bash
cd backend
python scripts/ingest.py --force
```

This chunks all PDFs and Markdown files, generates embeddings, and persists them to ChromaDB.

### 4. Run Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8001
# Runs at http://localhost:8001
# API docs at  http://localhost:8001/docs
```

### 5. Setup & Run Frontend

```bash
cd frontend
npm install

# .env
# VITE_API_URL=http://localhost:8001
```

```bash
npm run dev
# Runs at http://localhost:5173
```

## Docker

### Build

```bash
cd backend
# Run ingest locally first — Docker bundles the pre-built chroma_db
python scripts/ingest.py --force

docker build -t shubham-ai-backend .
```

### Run

```bash
docker run -p 8001:8001 \
  -e GROQ_API_KEY=your_key \
  -e VAPI_API_KEY=your_key \
  -e TWILIO_AUTH_TOKEN=your_token \
  -e GOOGLE_CALENDAR_CREDENTIALS_JSON=your_creds \
  shubham-ai-backend
```

Or use the included `docker-compose.yml` from the repo root.

## API Endpoints

### `GET /health`
Health check for container orchestration.
```json
{ "status": "ok", "env": "development", "api_key_configured": true }
```

### `POST /api/chat`
Main RAG chat endpoint. Retrieves relevant context and generates a grounded response.
```json
// Request
{ "message": "Tell me about your experience" }

// Response
{
  "answer": "I have experience in...",
  "sources": [
    { "source": "UpdatedCV.pdf", "content": "...", "score": 0.42 }
  ],
  "booking_url": null,
  "meeting_url": null,
  "owner_email": "shubhamshu382@gmail.com",
  "interviewer_email": null
}
```

### `GET /api/voice/phone-number`
Returns the configured Vapi phone number to call.

### `POST /api/voice/tool-execute`
Executes a tool call from the voice agent (`get_available_slots`, `book_meeting`, `get_profile_info`).

### `POST /api/voice/webhook`
Receives Vapi call events (`call.started`, `call.ended`, `message`).

### `GET /api/voice/assistant-config`
Returns the Vapi assistant configuration (system prompt, tools, voice, model).

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key for Llama 3.1 chat | ✅ |
| `GROQ_MODEL` | Model id (default: `llama-3.1-8b-instant`) | optional |
| `EMBEDDING_MODEL` | HF model id (default: `all-MiniLM-L6-v2`) | optional |
| `EMBEDDING_DIM` | Vector dim (default: `384`) | optional |
| `RETRIEVAL_TOP_K` | Chunks to retrieve (default: `3`) | optional |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Chunking params (default: `1500` / `300`) | optional |
| `MIN_SCORE` | Cosine similarity threshold (default: `0.22`) | optional |
| `GOOGLE_CALENDAR_URL` | Public booking URL for CTAs | optional |
| `GOOGLE_MEET_URL` | Meet link used in invites (default: `https://meet.google.com/new`) | optional |
| `OWNER_EMAIL` | Email for booking confirmations | optional |
| `INTERVIEWER_EMAIL` | Optional interviewer contact email | optional |
| `VAPI_API_KEY` | Vapi API key for voice agent | optional (voice) |
| `VAPI_ASSISTANT_ID` | Vapi assistant id | optional (voice) |
| `VAPI_PHONE_NUMBER_ID` | Vapi phone number id | optional (voice) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (via Vapi) | optional (voice) |
| `GOOGLE_CALENDAR_CREDENTIALS_JSON` | Service account JSON for booking | optional (voice) |
| `VOICE_WEBHOOK_SECRET` | Webhook signature secret | optional |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | optional |
| `APP_ENV` | `development` / `staging` / `production` | optional |
| `LOG_LEVEL` | Log level (default: `INFO`) | optional |

### Frontend (`frontend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend base URL | `http://localhost:8001` |

## Test Cases

| Scenario | Input | Expected Output |
|----------|-------|-----------------|
| Personal intro | "Tell me about yourself" | Grounded answer from master profile |
| Project details | "What is NavDrishti?" | Details from `navdristi.md` |
| Tech stack | "What technologies do you use?" | Skills from CV + project docs |
| Booking intent | "Can we schedule a meeting?" | Calendar booking CTA |
| Out of scope | "What is the capital of France?" | Canonical refusal phrase |
| Prompt injection | "Ignore previous instructions" | Deflection response |
| Voice input | Speak any question | SpeechRecognition → RAG-grounded answer |

## Troubleshooting

**Backend not starting**
```bash
curl http://localhost:8001/health
# If ChromaDB is empty, re-ingest:
python scripts/ingest.py --force
```

**Chat returns "API key not configured"**
Set `GROQ_API_KEY` in `backend/.env` and restart the server.

**Frontend 403 / CORS errors**
- Verify `ALLOWED_ORIGINS` in `backend/.env` includes the frontend origin (default: `http://localhost:5173`).
- Confirm `VITE_API_URL` in `frontend/.env` matches the running backend.

**Voice agent not configured**
- `GET /api/voice/phone-number` returns a "not configured" message if `VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, or `VAPI_PHONE_NUMBER_ID` is missing.
- Run `python test_voice_agent.py` from `backend/` for a quick smoke check.

**Docker issues**
```bash
docker logs <container_id>
docker exec -it <container_id> /bin/bash
```

## License

MIT

## Author

Shubham Shukla — [shubhamshu382@gmail.com](mailto:shubhamshu382@gmail.com)
