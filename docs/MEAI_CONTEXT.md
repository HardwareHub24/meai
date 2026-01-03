# MEAI – Mechanical Engineer AI
Single source of truth for Codex / ChatGPT context.

---

## What MEAI Is
MEAI is a Mechanical Engineer AI designed to assist with:
- Product design
- Requirements definition
- Engineering trade studies
- Conservative, real-world decision making

It is NOT a chatbot toy. It behaves like a senior mechanical engineer.

---

## Core Architecture
- Python-based RAG system
- Supabase vector store
- Explicit ingestion pipeline
- Mode-based system prompts

Key folders:
- meai_core/ → core engine logic
- meai_web/ → web UI + server
- prompts/ → system and mode prompts
- archive/ → deprecated or experimental prompts/scripts
- docs/ → project memory and decisions

---

## Locked Engineering Principles (DO NOT VIOLATE)
- Never invent material properties or standards
- Clearly label assumptions and rules of thumb
- Ask at most 3 clarifying questions
- Always provide a provisional recommendation
- Cite sources ONLY when retrieved via RAG
- Conservative > clever

---

## Modes
Modes are controlled via prompt files in /prompts.

- mode_1.txt → Ideation / friendly engineer
- mode_2.txt → Requirements / design brief
- validator.txt → Validation / critique
- planner.txt → Planning / decomposition

Prompts are considered **stable interfaces**.

---

## RAG Rules
- RAG context is injected before model reasoning
- Low-quality chunks are filtered
- Model must defer to retrieved context when present
- If no context exists, say so explicitly

---

## Non-Goals
- No autonomous agents yet
- No live Google Drive sync
- No hallucinated citations
- No overconfidence

---

## When Editing Code
Codex should:
1. Read this file
2. Read the file being edited
3. Respect locked rules above
4. Ask before refactoring architecture
