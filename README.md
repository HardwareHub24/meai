MEAI – Mechanical Engineering AI (MVP)

MEAI is a domain-specific AI assistant for mechanical engineers.
It combines RAG over curated engineering documents with a structured vendor database in Supabase to produce practical, citation-aware engineering guidance and real vendor recommendations.

This MVP is intentionally opinionated, conservative, and engineer-first.

What MEAI Does

Answers mechanical engineering questions using licensed reference documents

Retrieves and cites relevant document chunks via vector search

Actively recommends real vendors from a Supabase vendor table (vendors_core)

Generates downloadable:

Engineering Notes (Markdown)

Product Requirements Documents (PRD)

Maintains session memory for iterative design conversations

Architecture Overview
meai/
├── meai_core/
│   ├── engine.py        # RAG + vendor logic (core brain)
│   └── logs/
├── meai_web/
│   ├── server.py        # FastAPI backend
│   ├── templates/
│   │   └── index.html   # UI
│   └── static/
│       └── app.js       # Frontend logic
├── prompts/             # System prompts (planner, validator, modes)
├── Assets/              # Logos and branding
└── README.md

Key Concepts
RAG (Retrieval-Augmented Generation)

Uses Supabase vector search (match_meai_chunks)

Embeds with text-embedding-3-small

Filters low-quality chunks

Enforces license constraints per document

Vendor Intelligence

Vendors stored in Supabase table: vendors_core

Triggered automatically when user intent implies sourcing

Never hallucinated

Vendors cited as [VENDOR_TABLE]

Modes

Modes are system prompts stored in /prompts.
The UI does not expose mode switching. The backend controls behavior.

Examples:

mode_1 – Friendly engineer / ideation

mode_2 – Requirements / design brief

mode_3 – Technical engineer-to-engineer

Supabase Tables Required

Minimum required tables:

vendors_core

meai_documents

meai_licenses

meai_sessions

meai_messages

meai_feedback

Required RPC:

match_meai_chunks(query_embedding, match_count)

Environment Variables

Create a .env file at the project root:

OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...


The service key is required for unrestricted reads and writes.

Running Locally
1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

2. Start the server
uvicorn meai_web.server:app --reload

3. Open the app
http://127.0.0.1:8000

API Endpoints
Ask a Question

POST /api/ask

{
  "message": "I need sheet metal fabrication vendors",
  "session_id": "optional-uuid"
}

Download Engineering Notes

GET /api/notes/download?session_id=UUID

Download PRD

GET /api/prd/download?session_id=UUID

Design Philosophy

No hallucinated specs

Explicit assumptions

Conservative engineering guidance

Vendor realism over generic advice

Fail loudly when data is missing

Built for iteration, not demos

Status

MVP – Active Development

Known focus areas:

Vendor ranking and scoring

Capability-aware vendor matching

Geometry-aware prompting

Export to PDF

File uploads for drawings and specs

Ownership

MEAI is part of the Hardware Hub ecosystem.
All architecture decisions favor extensibility and long-term professional use.