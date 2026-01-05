---
doc_id: 05_database_schema.md
title: Database Schema
version: 0.1
owner: Justin
status: DRAFT
---

## Purpose {#meai-db-purpose}
- Summarize the known Supabase tables and RPC used by MEAI. (README.md)

## Tables {#meai-db-tables}
- RAG tables: meai_documents and meai_licenses are referenced in the engine. (meai_core/engine.py)
- Conversation tables: meai_sessions and meai_messages are used for session logging. (meai_core/engine.py)
- Feedback table: meai_feedback is written by the web API. (meai_core/engine.py) (meai_web/server.py)
- Vendor table: vendors_core is queried for vendor retrieval. (meai_core/engine.py) (README.md)
- Ingestion writes chunks to meai_chunks. (ingest_01_text_to_supabase.py)

## Relationships {#meai-db-relationships}
TODO (not found in repo)

## Indexes and RPC {#meai-db-indexes}
- RPC: match_meai_chunks(query_embedding, match_count) is required for retrieval. (README.md) (meai_core/engine.py)
- meai_documents are matched by source_url when building license blocks. (meai_core/engine.py)

## Migrations {#meai-db-migrations}
TODO (not found in repo)

## Last Verified {#meai-last-verified}
- Timestamp: 2026-01-03 16:35:09 EST
- Git branch: main
- Files referenced: README.md, meai_core/engine.py, meai_web/server.py, ingest_01_text_to_supabase.py
