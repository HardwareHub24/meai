from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from meai_core.engine import sb

router = APIRouter()


class CreateChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    title: Optional[str] = None


class CreateMessageRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: str
    content: str = Field(min_length=1)


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def _get_chat_or_404(chat_id: str, user_id: str) -> Dict[str, Any]:
    resp = (
        sb.table("chats")
        .select("*")
        .eq("id", chat_id)
        .eq("user_id", user_id)
        .eq("is_deleted", False)
        .single()
        .execute()
    )
    chat = resp.data if hasattr(resp, "data") else None
    if not chat:
        raise HTTPException(status_code=404, detail="chat not found")
    return chat


@router.post("/api/chats")
def create_chat(req: CreateChatRequest):
    payload = {"user_id": req.user_id}
    if req.title:
        payload["title"] = req.title
    resp = sb.table("chats").insert(payload).execute()
    chat = resp.data[0] if resp.data else None
    if not chat:
        raise HTTPException(status_code=400, detail="unable to create chat")
    return {"chat": chat}


@router.get("/api/chats")
def list_chats(user_id: str):
    resp = (
        sb.table("chats")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_deleted", False)
        .order("last_message_at", desc=True, nullsfirst=False)
        .order("created_at", desc=True)
        .execute()
    )
    return {"chats": resp.data or []}


@router.get("/api/chats/{chat_id}/messages")
def list_messages(chat_id: str, user_id: str):
    chat = _get_chat_or_404(chat_id, user_id)
    resp = (
        sb.table("chat_messages")
        .select("*")
        .eq("chat_id", chat_id)
        .order("created_at", desc=False)
        .execute()
    )
    return {"chat": chat, "messages": resp.data or []}


@router.post("/api/chats/{chat_id}/messages")
def create_message(chat_id: str, req: CreateMessageRequest):
    chat = _get_chat_or_404(chat_id, req.user_id)
    role = req.role
    if role not in ("user", "assistant", "system"):
        raise HTTPException(status_code=400, detail="invalid role")

    msg_payload = {
        "chat_id": chat_id,
        "role": role,
        "content": req.content,
    }
    resp = sb.table("chat_messages").insert(msg_payload).execute()
    message = resp.data[0] if resp.data else None
    if not message:
        raise HTTPException(status_code=400, detail="unable to create message")

    update_payload = {
        "updated_at": _utc_now(),
        "last_message_at": _utc_now(),
    }
    if role == "user" and (chat.get("title") or "New chat") == "New chat":
        trimmed = (req.content or "").strip()[:40]
        update_payload["title"] = trimmed if trimmed else "Chat"

    sb.table("chats").update(update_payload).eq("id", chat_id).execute()
    return {"message": message}
