# UI Schema (Current)

Session ID:
- Displayed in the UI via element id `sessionId`.

Buttons:
- Download notes: `downloadNotesBtn`
- Clear chat: `clearChatBtn`

Download behavior:
- Notes download uses `GET /api/notes/download?session_id=...` and returns Markdown (text/markdown).
