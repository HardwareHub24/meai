---
doc_id: 08_runbook.md
title: Runbook
version: 0.1
owner: Justin
status: DRAFT
---

## Purpose {#meai-runbook-purpose}
- Provide operational steps for local development and common tasks. (README.md)

## Startup {#meai-runbook-startup}
- Create a venv and install requirements per README. (README.md)
- Start the server with `uvicorn meai_web.server:app --reload`. (README.md)
- Makefile provides setup and web targets. (Makefile)

## Health Checks {#meai-runbook-health}
TODO (not found in repo)

## Common Tasks {#meai-runbook-tasks}
- Run the RAG CLI: `python ask_03_rag_cli.py` via Makefile. (Makefile) (ask_03_rag_cli.py)
- Run ingestion: `python ingest_01_text_to_supabase.py`. (ingest_01_text_to_supabase.py)
- Generate system PDFs: `make system-pdfs`. (Makefile)

## Incident Response {#meai-runbook-incident}
TODO (not found in repo)

## Shutdown {#meai-runbook-shutdown}
TODO (not found in repo)

## Last Verified {#meai-last-verified}
- Timestamp: 2026-01-03 16:35:09 EST
- Git branch: main
- Files referenced: README.md, Makefile, ask_03_rag_cli.py, ingest_01_text_to_supabase.py
