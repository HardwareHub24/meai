# meai_web/server.py
import os
import uuid
import time
import logging
from typing import Optional, Dict, Any, List, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel, Field

from meai_web.math_engine import solve_expr, simplify_expr
from meai_web.routers.chat_history import router as chat_history_router
from meai_core.engine import rag_answer, sb, FEEDBACK_TABLE_NAME, build_engineering_notes_md

# -----------------------------
# App setup
# -----------------------------
app = FastAPI(title="ME AI")

logger = logging.getLogger("meai_web.server")

print(f"DEBUG_RAG={os.getenv('DEBUG_RAG')}", flush=True)

HERE = os.path.dirname(__file__)  # .../meai/meai_web
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
START_TIME = time.monotonic()

templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))

app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

assets_dir = os.path.join(PROJECT_ROOT, "Assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

app.include_router(chat_history_router)


# -----------------------------
# Request tracing
# -----------------------------
@app.middleware("http")
async def request_tracing(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request completed method=%s path=%s status=%s duration_ms=%s request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


# -----------------------------
# Utilities
# -----------------------------
def get_git_sha() -> Optional[str]:
    head_path = os.path.join(PROJECT_ROOT, ".git", "HEAD")
    try:
        with open(head_path, "r", encoding="utf-8") as f:
            head = f.read().strip()
    except OSError:
        return None

    if head.startswith("ref:"):
        ref = head.split(" ", 1)[1].strip()
        ref_path = os.path.join(PROJECT_ROOT, ".git", ref)
        try:
            with open(ref_path, "r", encoding="utf-8") as f:
                return f.read().strip() or None
        except OSError:
            packed = os.path.join(PROJECT_ROOT, ".git", "packed-refs")
            try:
                with open(packed, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or line.startswith("^"):
                            continue
                        sha, name = line.split(" ", 1)
                        if name == ref:
                            return sha
            except OSError:
                return None
        return None

    return head or None


# -----------------------------
# Health checks
# -----------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": "meai"}

@app.get("/api/health")
def api_health():
    uptime_seconds = time.monotonic() - START_TIME
    return {"status": "ok", "service": "meai", "git_sha": get_git_sha(), "uptime_seconds": uptime_seconds}


# -----------------------------
# Web UI
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# -----------------------------
# API models
# -----------------------------
Mode = Literal["mode_1", "mode_2"]


class AskRequest(BaseModel):
    mode: Mode
    message: str = Field(min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class AskResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]] = []
    debug: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: Optional[str] = None
    score: Optional[int] = None
    comment: Optional[str] = None


class MathRequest(BaseModel):
    task: str  # "solve" or "simplify"
    expr: str
    var: Optional[str] = "x"


# -----------------------------
# API routes
# -----------------------------
@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request):
    try:
        request_id = getattr(request.state, "request_id", None)
        answer, citations, debug = rag_answer(
            mode=req.mode,
            message=req.message,
            session_id=req.session_id,
        )
        return AskResponse(
            answer=answer,
            citations=citations or [],
            debug=debug or {},
            request_id=request_id,
        )
    except Exception as e:
        logger.exception("ASK ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feedback")
def feedback(req: FeedbackRequest, request: Request):
    if req.score is not None and req.score not in (-1, 0, 1):
        raise HTTPException(status_code=422, detail="score must be -1, 0, or 1")

    fid = str(uuid.uuid4())
    try:
        sb.table(FEEDBACK_TABLE_NAME).insert(
            {
                "id": fid,
                "session_id": req.session_id,
                "message_id": req.message_id,
                "score": req.score,
                "comment": req.comment,
            }
        ).execute()
        return {"ok": True, "id": fid, "request_id": getattr(request.state, "request_id", None)}
    except Exception as e:
        logger.exception("FEEDBACK ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/math")
def run_math(req: MathRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)
    if req.task == "solve":
        result = solve_expr(req.expr, req.var)
        if isinstance(result, dict):
            result["request_id"] = request_id
            return result
        return {"result": result, "request_id": request_id}
    if req.task == "simplify":
        result = simplify_expr(req.expr)
        if isinstance(result, dict):
            result["request_id"] = request_id
            return result
        return {"result": result, "request_id": request_id}
    raise HTTPException(status_code=400, detail="Invalid math task")


@app.get("/api/notes/download")
def download_notes(session_id: str, request: Request):
    try:
        md = build_engineering_notes_md(session_id=session_id)
        filename = f"meai_engineering_notes_{session_id}.md"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        response = PlainTextResponse(content=md, media_type="text/markdown", headers=headers)
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "")
        return response
    except Exception as e:
        logger.exception("NOTES ERROR")
        raise HTTPException(status_code=500, detail=str(e))
