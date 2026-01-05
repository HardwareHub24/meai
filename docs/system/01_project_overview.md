---
doc_id: 01_project_overview.md
title: Project Overview
version: 0.1
owner: Justin
status: DRAFT
---

## Purpose {#meai-purpose}
- MEAI is a Mechanical Engineer AI intended to assist with product design, requirements definition, trade studies, and conservative real-world decision making. (docs/MEAI_CONTEXT.md)
- MEAI is presented as a domain-specific assistant for mechanical engineers with RAG over curated documents and vendor recommendations. (README.md)

## Scope {#meai-scope}
- Core capabilities include RAG-backed question answering with citations and vendor recommendations from Supabase. (README.md)
- The web UI uses a FastAPI backend and a static JS frontend. (meai_web/server.py) (meai_web/static/app.js)
- Session ID is displayed and notes download/clear chat buttons exist in the UI. (docs/ui_schema.md)

## Users and Stakeholders {#meai-users}
- Primary users are mechanical engineers. (README.md)
- MEAI context is intended as a single source of truth for Codex/ChatGPT usage. (docs/MEAI_CONTEXT.md)
- MEAI is part of the Hardware Hub ecosystem. (README.md)

## Problem Statement {#meai-problem}
- Provide practical, citation-aware engineering guidance grounded in licensed documents. (README.md)
- Provide conservative, real-world recommendations with explicit assumptions. (docs/MEAI_CONTEXT.md)

## Success Criteria {#meai-success}
- Avoid hallucinated material properties or standards and label assumptions. (docs/MEAI_CONTEXT.md)
- Fail loudly when data is missing and keep guidance conservative. (README.md)

## Last Verified {#meai-last-verified}
- Timestamp: 2026-01-03 16:35:09 EST
- Git branch: main
- Files referenced: docs/MEAI_CONTEXT.md, README.md, meai_web/server.py, meai_web/static/app.js, docs/ui_schema.md
