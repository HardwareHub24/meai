# meai_web/server.py
import os, uuid, traceback
from typing import Optional, Dict, Any, List, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel, Field

from meai_core.engine import rag_answer, sb, FEEDBACK_TABLE_NAME, build_engineering_notes_md

app = FastAPI()

HERE = os.path.dirname(__file__)  # .../meai/meai_web
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))

templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

assets_dir = os.path.join(PROJECT_ROOT, "Assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

Mode = Literal["mode_1", "mode_2"]

class AskRequest(BaseModel):
    mode: Mode
    message: str = Field(min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class AskResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]] = []
    debug: Optional[Dict[str, Any]] = None

class FeedbackRequest(BaseModel):
    session_id: str
    message_id: Optional[str] = None
    score: Optional[int] = None
    comment: Optional[str] = None

@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    try:
        answer, citations, debug = rag_answer(mode=req.mode, message=req.message, session_id=req.session_id)
        return AskResponse(answer=answer, citations=citations or [], debug=debug or {})
    except Exception as e:
        print("ASK ERROR:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    if req.score is not None and req.score not in (-1, 0, 1):
        raise HTTPException(status_code=422, detail="score must be -1, 0, or 1")
    fid = str(uuid.uuid4())
    try:
        sb.table(FEEDBACK_TABLE_NAME).insert({
            "id": fid, "session_id": req.session_id, "message_id": req.message_id,
            "score": req.score, "comment": req.comment,
        }).execute()
        return {"ok": True, "id": fid}
    except Exception as e:
        print("FEEDBACK ERROR:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes/download")
def download_notes(session_id: str):
    try:
        md = build_engineering_notes_md(session_id=session_id)
        filename = f"meai_engineering_notes_{session_id}.md"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return PlainTextResponse(content=md, media_type="text/markdown", headers=headers)
    except Exception as e:
        print("NOTES ERROR:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
