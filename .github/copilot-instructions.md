# GitHub Copilot / AI-Agent Instructions — MEAI

Purpose: concise, actionable guidance for AI coding agents working on this repository.

- Read `docs/MEAI_CONTEXT.md` first — it contains the project's intent, locked engineering principles, and mode contracts.

- Big picture:
  - Core RAG engine: `meai_core/engine.py` (embeddings, retrieval, prompt assembly, Supabase persistence).
  - Web API: `meai_web/server.py` (FastAPI endpoints: `/api/ask`, `/api/feedback`, notes export).
  - Prompts: `prompts/` (stable interfaces: `mode_1.txt`, `mode_2.txt`, `planner.txt`, `validator.txt`).
  - Ingestion/CLI: `ingest_01_text_to_supabase.py`, `ask_03_rag_cli.py` (scripts that exercise the engine).

- Key integration points to check before edits:
  - Environment variables used in `meai_core/engine.py`: `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (the code asserts the service key format).
  - Supabase dependencies: DB tables and RPCs referenced in `engine.py` — `meai_documents`, `vendors_core`, `match_meai_chunks` RPC.
  - Models: `EMBED_MODEL = text-embedding-3-small`, `LLM_MODEL = gpt-4o-mini` (change deliberately).

- Project-specific patterns and conventions:
  - Prompts are stable public interfaces. Changes to `prompts/*.txt` are behavioral changes and must be treated like API changes.
  - RAG context is assembled by `embed()` → `retrieve_chunks()` → `build_context()`; citations use tags of the form `[source_file:chunk_index]`.
  - License and vendor handling are explicit: `build_license_block()` and `vendor_context_block()` inject constraints into the final prompt; do not remove them.
  - Logging and session persistence are performed via Supabase and a local file: messages persist to `meai_messages` (DB) and session logs to `meai_core/logs/sessions.jsonl`.

- Common developer workflows (commands/examples):
  - Create virtualenv and install deps (project has no manifest checked in):
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install fastapi uvicorn supabase openai python-dotenv pydantic pytest
    ```
  - Run the FastAPI app locally:
    ```bash
    uvicorn meai_web.server:app --reload --port 8000
    ```
  - Run the CLI or ingestion script:
    ```bash
    python ask_03_rag_cli.py
    python ingest_01_text_to_supabase.py
    ```
  - Run retrieval test (if `pytest` installed):
    ```bash
    pytest -q test_02_retrieval.py
    ```

- Editing guidance (safe edits and what to verify):
  - Before changing prompt-driven behavior, read `prompts/planner.txt` and `prompts/validator.txt` and run a `plan()`/`validate()` cycle via `ask_03_rag_cli.py` or HTTP `/api/ask`.
  - If you modify retrieval, ensure the Supabase RPC `match_meai_chunks` and document schema (`meai_documents`) still support the new contract.
  - When changing DB table names or schemas, update constants at the top of `meai_core/engine.py` (`DOCUMENTS_TABLE_NAME`, `VENDOR_TABLE_NAME`, etc.).
  - When adding information that will be cited by the model, ensure `source_file` and `chunk_index` metadata are present so the existing citation format works.

- Safety and policy constraints (from `docs/MEAI_CONTEXT.md`):
  - Never invent material properties or standards.
  - Explicitly label assumptions and rules of thumb.
  - Ask at most 3 clarifying questions.
  - Cite sources only when retrieved via RAG.

If anything here looks incomplete or you want specific examples (e.g., a short integration test or example RPC payload), tell me which area to expand. 
