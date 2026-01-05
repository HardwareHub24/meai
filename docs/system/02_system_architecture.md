---
doc_id: 02_system_architecture.md
title: System Architecture
version: 0.1
owner: Justin
status: DRAFT
---

## Purpose {#meai-arch-purpose}
- Describe the MEAI system layout, including RAG core, web UI, and prompts. (docs/MEAI_CONTEXT.md)

## System Overview {#meai-arch-overview}
- The system is a Python-based RAG application using Supabase as a vector store. (docs/MEAI_CONTEXT.md)
- The core engine lives in `meai_core/engine.py` and the web backend in `meai_web/server.py`. (README.md)

## Components {#meai-arch-components}
- Core RAG logic, vendor retrieval, and prompt assembly are implemented in `meai_core/engine.py`. (meai_core/engine.py)
- The FastAPI server defines web endpoints and serves templates/static assets. (meai_web/server.py)
- Frontend chat behavior and client-side routing are in `meai_web/static/app.js`. (meai_web/static/app.js)
- System prompts live in `prompts/` and are treated as stable interfaces. (docs/MEAI_CONTEXT.md)

## Data Flow {#meai-arch-dataflow}
- Requests are routed through `rag_answer`, which runs planning, retrieval, and LLM completion. (meai_core/engine.py)
- Retrieval uses Supabase RPC `match_meai_chunks` to fetch candidate chunks. (meai_core/engine.py)
- Retrieved chunks are filtered, assembled into a context block, and combined with license and vendor blocks. (meai_core/engine.py)
- The UI sends chat requests to `/api/ask` and math shortcuts to `/api/math`. (meai_web/static/app.js)

## Interfaces {#meai-arch-interfaces}
- HTTP: `POST /api/ask`, `POST /api/feedback`, `POST /api/math`, and `GET /api/notes/download`. (meai_web/server.py)
- Prompt interfaces: `prompts/mode_1.txt`, `prompts/mode_2.txt`, `prompts/planner.txt`, `prompts/validator.txt`. (docs/MEAI_CONTEXT.md) (prompts/mode_1.txt) (prompts/mode_2.txt) (prompts/planner.txt) (prompts/validator.txt)

## Non-Goals {#meai-arch-nongoals}
- No autonomous agents yet. (docs/MEAI_CONTEXT.md)
- No live Google Drive sync. (docs/MEAI_CONTEXT.md)
- No hallucinated citations or overconfidence. (docs/MEAI_CONTEXT.md)

## Last Verified {#meai-last-verified}
- Timestamp: 2026-01-03 16:35:09 EST
- Git branch: main
- Files referenced: docs/MEAI_CONTEXT.md, README.md, meai_core/engine.py, meai_web/server.py, meai_web/static/app.js, prompts/mode_1.txt, prompts/mode_2.txt, prompts/planner.txt, prompts/validator.txt
