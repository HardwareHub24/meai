---
doc_id: 03_tech_stack.md
title: Tech Stack
version: 0.1
owner: Justin
status: DRAFT
---

## Purpose {#meai-tech-purpose}
- Summarize the runtime, backend, frontend, and key dependencies used in MEAI. (README.md)

## Core Runtime {#meai-tech-runtime}
- Python is the primary runtime for the backend and ingestion scripts. (README.md) (meai_core/engine.py) (ingest_01_text_to_supabase.py)

## Backend {#meai-tech-backend}
- FastAPI serves the web backend. (meai_web/server.py) (requirements.txt)
- OpenAI SDK is used for embeddings and chat completions. (meai_core/engine.py) (requirements.txt)
- Supabase Python client is used for vector search and storage. (meai_core/engine.py) (requirements.txt)

## Frontend {#meai-tech-frontend}
- The UI is an HTML template served by FastAPI with JavaScript in `meai_web/static/app.js`. (meai_web/server.py) (meai_web/static/app.js)
- Client rendering uses `marked` and MathJax if present in the page. (meai_web/static/app.js)

## Infrastructure {#meai-tech-infra}
- Supabase provides the vector store and database layer. (meai_core/engine.py)
- OpenAI API provides embeddings and chat completions. (meai_core/engine.py)

## Dependencies {#meai-tech-deps}
- Key Python packages include fastapi, uvicorn, openai, supabase, python-dotenv, and pypdf. (requirements.txt) (ingest_01_text_to_supabase.py)

## Last Verified {#meai-last-verified}
- Timestamp: 2026-01-03 16:35:09 EST
- Git branch: main
- Files referenced: README.md, meai_core/engine.py, meai_web/server.py, meai_web/static/app.js, ingest_01_text_to_supabase.py, requirements.txt
