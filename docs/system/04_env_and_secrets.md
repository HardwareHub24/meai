---
doc_id: 04_env_and_secrets.md
title: Environment and Secrets
version: 0.1
owner: Justin
status: DRAFT
---

## Purpose {#meai-env-purpose}
- Document required environment variables and secret handling used by MEAI. (meai_core/engine.py)

## Required Environment Variables {#meai-env-vars}
- OPENAI_API_KEY is required for LLM usage. (meai_core/engine.py) (.env.example)
- SUPABASE_URL is required to connect to Supabase. (meai_core/engine.py) (.env.example)
- SUPABASE_SERVICE_KEY is required for Supabase access. (meai_core/engine.py) (.env.example)
- CORE_LIBRARY_DIR is required for ingestion input scanning. (ingest_01_text_to_supabase.py)
- DEBUG_RAG is read at runtime to enable RAG logging. (meai_core/engine.py) (meai_web/server.py)

## Secrets Handling {#meai-env-secrets}
- Environment variables are loaded from a .env file using python-dotenv. (meai_core/engine.py)
- Supabase service key is asserted to look like a JWT before use. (meai_core/engine.py)

## Local Development {#meai-env-local}
- README specifies creating a venv and installing `requirements.txt`. (README.md)
- README starts the server with `uvicorn meai_web.server:app --reload`. (README.md)
- Makefile provides `setup` and `web` targets. (Makefile)

## Rotation and Revocation {#meai-env-rotation}
TODO (not found in repo)

## Last Verified {#meai-last-verified}
- Timestamp: 2026-01-03 16:35:09 EST
- Git branch: main
- Files referenced: meai_core/engine.py, ingest_01_text_to_supabase.py, meai_web/server.py, .env.example, README.md, Makefile
