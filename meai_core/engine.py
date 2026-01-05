# meai_core/engine.py
import os, re, json, uuid, traceback
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

# ========= logging =========
LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "sessions.jsonl")

def _ensure_log_dir() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def log_event(event: Dict[str, Any]) -> None:
    _ensure_log_dir()
    event["ts"] = datetime.utcnow().isoformat()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

# ========= env + clients =========
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
assert OPENAI_API_KEY and SUPABASE_URL and SUPABASE_SERVICE_KEY, "Missing env vars"
assert SUPABASE_SERVICE_KEY, "SUPABASE_SERVICE_KEY missing"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ========= tables =========
VENDOR_TABLE_NAME = "vendors_core"
DOCUMENTS_TABLE_NAME = "meai_documents"
LICENSES_TABLE_NAME = "meai_licenses"
SESSIONS_TABLE_NAME = "meai_sessions"
MESSAGES_TABLE_NAME = "meai_messages"
FEEDBACK_TABLE_NAME = "meai_feedback"

# prompts folder is at project root: meai/prompts/
PROMPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts"))
PINNED_FACTS_PATH = os.path.join(os.path.dirname(__file__), "prompts", "pinned_facts_hardwarehub.txt")

LLM_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"

# Must match meai_documents schema column containing the chunk source identifier
DOC_SOURCE_COL = "source_url"
DEBUG_RAG = None
SYSTEM_DOC_ALLOWLIST = {
    "01_Project_Overview.pdf",
    "02_System_Architecture.pdf",
    "03_Tech_Stack.pdf",
    "04_Env_and_Secrets.pdf",
    "05_Database_Schema.pdf",
    "06_Ingestion_Pipeline.pdf",
    "07_Known_Issues.pdf",
    "08_Runbook.pdf",
    "09_Future_Roadmap.pdf",
    "10_Glossary.pdf",
}

# ========= prompts =========
def load_prompt(name: str) -> str:
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing prompt file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_pinned_facts() -> str:
    if not os.path.exists(PINNED_FACTS_PATH):
        raise FileNotFoundError(f"Missing pinned facts file: {PINNED_FACTS_PATH}")
    with open(PINNED_FACTS_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()

HARDWAREHUB_TERMS = ["hardwarehub", "hardware hub"]
SCHEDULING_TERMS = ["meet", "meeting", "schedule", "book", "call", "intro", "chat", "calendar"]
SERVICES_TERMS = [
    "cad",
    "solidworks",
    "fea",
    "finite element",
    "cfd",
    "computational fluid",
    "prototype",
    "prototyping",
    "dfm",
    "mechanical engineering",
]

def detect_hardwarehub_intents(text: str) -> Dict[str, bool]:
    q = (text or "").lower()
    hardwarehub = any(t in q for t in HARDWAREHUB_TERMS)
    scheduling = any(t in q for t in SCHEDULING_TERMS)
    services = any(t in q for t in SERVICES_TERMS)
    return {
        "hardwarehub": hardwarehub,
        "scheduling": scheduling,
        "services": services,
    }

# ========= supabase persistence =========
def ensure_session(session_id: str, tester_label: Optional[str] = None) -> None:
    payload: Dict[str, Any] = {"id": session_id}
    if tester_label is not None:
        payload["tester_label"] = tester_label
    sb.table(SESSIONS_TABLE_NAME).upsert(payload).execute()

def insert_message(session_id: str, role: str, content: str) -> str:
    mid = str(uuid.uuid4())
    sb.table(MESSAGES_TABLE_NAME).insert({
        "id": mid,
        "session_id": session_id,
        "role": role,
        "content": content,
    }).execute()
    return mid

# ========= harness: planner + validator =========
def plan(question: str, mode_name: str) -> Dict[str, Any]:
    system = load_prompt("planner")
    resp = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"mode={mode_name}\nquestion={question}"},
        ],
        temperature=0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {
            "needs_clarification": False,
            "clarifying_question": "",
            "use_docs_rag": True,
            "use_vendors": False,
        }

def validate(answer: str, mode_name: str) -> Dict[str, Any]:
    system = load_prompt("validator")
    resp = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"mode={mode_name}\nanswer={answer}"},
        ],
        temperature=0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"ok": True, "issues": []}

# ========= embeddings + retrieval =========
def embed(text: str) -> List[float]:
    return openai_client.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding

def retrieve_chunks(query_embedding: List[float], k: int = 8) -> List[Dict[str, Any]]:
    return sb.rpc("match_meai_chunks", {"query_embedding": query_embedding, "match_count": k}).execute().data

def is_garbage(chunk: str) -> bool:
    if not chunk or len(chunk) < 80:
        return True
    digits = sum(1 for c in chunk if c.isdigit())
    return (digits / float(max(len(chunk), 1))) > 0.35

def build_context(rows: List[Dict[str, Any]], max_chunks: int = 5) -> Tuple[str, List[str], List[str]]:
    ctx, tags, source_files = [], [], []
    total = len(rows or [])
    debug_rag = os.getenv("DEBUG_RAG") == "1"
    for r in rows or []:
        content = r.get("content", "")
        if is_garbage(content):
            continue
        sf = r.get("source_file")
        ci = r.get("chunk_index")
        if sf is None or ci is None:
            continue
        if debug_rag and len(ctx) < 20:
            print(f"RAG CHUNK: source_file={sf}", flush=True)
        ctx.append(content)
        tags.append(f"[{sf}:{ci}]")
        source_files.append(sf)
        if len(ctx) >= max_chunks:
            break
    if debug_rag:
        print(f"RAG SUMMARY: kept={len(ctx)} total={total}", flush=True)
    # de-dupe in-order
    return "\n\n".join(ctx), list(dict.fromkeys(tags)), list(dict.fromkeys(source_files))

# ========= documents + licenses =========
def fetch_documents_by_source_files(source_files: List[str]) -> List[Dict[str, Any]]:
    if not source_files:
        return []
    resp = sb.table(DOCUMENTS_TABLE_NAME).select("*").in_(DOC_SOURCE_COL, source_files).execute()
    return resp.data or []

def fetch_licenses_by_keys(license_keys: List[str]) -> List[Dict[str, Any]]:
    if not license_keys:
        return []
    resp = sb.table(LICENSES_TABLE_NAME).select("*").in_("license_key", list(dict.fromkeys(license_keys))).execute()
    return resp.data or []

def build_license_block(source_files: List[str]) -> str:
    if not source_files:
        return "LICENSE CONSTRAINTS (must follow):\n- No retrieved documents."
    docs = fetch_documents_by_source_files(source_files)
    doc_by_sf = {d.get(DOC_SOURCE_COL): d for d in docs if d.get(DOC_SOURCE_COL)}

    license_keys: List[str] = []
    for sf in source_files:
        d = doc_by_sf.get(sf, {})
        lk = d.get("license_key") or d.get("license") or d.get("license_id")
        if lk:
            license_keys.append(lk)

    licenses = fetch_licenses_by_keys(license_keys)
    lic_by_key = {l.get("license_key"): l for l in licenses if l.get("license_key")}

    def _b(val: Any, default: bool) -> bool:
        return bool(val) if val is not None else default

    lines = ["LICENSE CONSTRAINTS (must follow):"]
    for sf in source_files:
        d = doc_by_sf.get(sf)
        if not d:
            lines.append(f"- {sf}: no document record found. Treat as strict: summarize only, cite if used.")
            continue

        lk = d.get("license_key") or d.get("license") or d.get("license_id")
        lic = lic_by_key.get(lk) if lk else None

        title = d.get("title") or sf
        lines.append(f"- {sf} | title: {title}")

        if not lk or not lic:
            lines.append("  license: unknown. Treat as strict: summarize only, do not quote, cite if used.")
            continue

        lines.append(f"  license_key: {lk}")
        lines.append(f"  commercial_use_allowed: {_b(lic.get('commercial_use_allowed'), True)}")
        lines.append(f"  derivatives_allowed: {_b(lic.get('derivatives_allowed'), True)}")
        lines.append(f"  sharealike_required: {_b(lic.get('sharealike_required'), False)}")
        lines.append(f"  verbatim_allowed: {_b(lic.get('verbatim_allowed'), False)}")
        vlim = lic.get("verbatim_char_limit")
        if vlim is not None:
            lines.append(f"  verbatim_char_limit: {vlim}")
        lines.append(f"  citation_required: {_b(lic.get('citation_required'), True)}")
        lines.append(f"  attribution_required: {_b(lic.get('attribution_required'), False)}")

    return "\n".join(lines)

# ========= vendors =========
VENDOR_TRIGGER_WORDS = (
    "vendor", "vendors", "supplier", "suppliers", "manufacturer", "manufacturers",
    "machine shop", "fabrication", "fab", "who should i go to", "where do i buy"
)

def _wants_vendors(text: str) -> bool:
    q = (text or "").lower()
    return any(t in q for t in VENDOR_TRIGGER_WORDS)

def _wants_system_docs_only(text: str) -> bool:
    q = (text or "").lower()
    keywords = (
        "meai self-check",
        "system-docs-only",
        "use only meai system docs",
    )
    return any(k in q for k in keywords)

def parse_vendor_hints(question: str) -> Tuple[Optional[List[str]], Optional[str]]:
    q = (question or "").lower()
    industries: List[str] = []
    for token in ["medical", "medtech", "aerospace", "automotive", "consumer", "industrial", "electronics", "robotics", "defense"]:
        if re.search(rf"\b{re.escape(token)}\b", q):
            industries.append(token)

    # crude capability phrase
    capability = None
    m = re.search(r"(need|seeking|looking for|find)\s+(a|an)?\s*([^.;,\n]+)", q)
    if m:
        capability = m.group(3).strip()

    return (industries or None), capability

def retrieve_vendors(industries: Optional[List[str]] = None, capability: Optional[str] = None, max_results: int = 8) -> List[Dict[str, Any]]:
    q = sb.table(VENDOR_TABLE_NAME).select("*").limit(max_results)
    if industries:
        for t in industries:
            q = q.ilike("industries", f"%{t}%")
    if capability:
        term = capability.strip()
        if term:
            q = q.or_(
                f"category.ilike.%{term}%,"
                f"description.ilike.%{term}%,"
                f"capabilities.ilike.%{term}%,"
                f"notes.ilike.%{term}%"
            )
    return q.execute().data or []

def vendor_context_block(question: str, max_results: int = 8) -> Tuple[str, List[Dict[str, Any]]]:
    industries, capability = parse_vendor_hints(question)
    vendors = retrieve_vendors(industries=industries, capability=capability, max_results=max_results)

    if not vendors:
        return "VENDOR_TABLE_MATCHES:\n- None found.", []

    lines = ["VENDOR_TABLE_MATCHES (use these explicitly when asked):"]
    for v in vendors[:max_results]:
        name = v.get("name") or v.get("vendor_name") or "Unknown"
        cat = v.get("category") or ""
        website = v.get("website") or v.get("url") or ""
        loc = v.get("location") or ""
        caps = v.get("capabilities") or ""
        header = f"- {name}" + (f" ({cat})" if cat else "")
        lines.append(header)
        if website:
            lines.append(f"  website: {website}")
        if loc:
            lines.append(f"  location: {loc}")
        if caps:
            lines.append(f"  capabilities: {caps}")

    return "\n".join(lines), vendors[:max_results]

# ========= prompt assembly =========
def user_prompt_template() -> str:
    return """
{license_block}

VENDOR_TABLE (supabase rolodex; when user asks for vendors, pick from this list and be explicit):
{vendor_ctx}

USER QUESTION:
{question}

RESPONSE REQUIREMENTS:
- Follow the selected mode system prompt contract.
- Do not block progress for missing inputs; use explicit working assumptions.
- If you use any factual claim from CONTEXT, cite inline using [source_file:chunk_index].
- If you recommend a vendor from VENDOR_TABLE, cite it as [VENDOR_TABLE] inline.
- End with "Citations:" listing only tags you actually used.
""".strip()

def _citations_to_dicts(doc_tags: List[str], used_vendor_table: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in doc_tags or []:
        m = re.match(r"^\[(.+?):(\d+)\]$", t.strip())
        if m:
            out.append({"tag": t, "source_file": m.group(1), "chunk_index": int(m.group(2))})
        else:
            out.append({"tag": t})
    if used_vendor_table:
        out.append({"tag": "[VENDOR_TABLE]", "source": "vendors_core"})
    return out

# ========= public API =========
def rag_answer(
    mode: str,
    message: str,
    session_id: Optional[str] = None,
    clarification: Optional[str] = None,
    temperature: float = 0.2,
    tester_label: Optional[str] = None
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    sid = session_id or str(uuid.uuid4())

    ensure_session(sid, tester_label=tester_label)
    user_mid = insert_message(sid, "user", message)

    system_prompt = load_prompt(mode)

    qtext = message
    intent = detect_hardwarehub_intents(qtext)
    if intent["hardwarehub"] and intent["scheduling"]:
        answer = (
            "HardwareHub provides mechanical engineering services and can help with your request. "
            "Schedule here: https://calendar.app.google/b9H7oKXC58tDX4ge9. "
            "If you want, share a couple of times you prefer and I can confirm."
        )
        assistant_mid = insert_message(sid, "assistant", answer)
        debug = {
            "session_id": sid,
            "mode": mode,
            "message_id": assistant_mid,
            "user_message_id": user_mid,
            "used_docs": False,
            "used_vendors": False,
            "retrieved_k": 0,
            "source_files": [],
            "fixed": False,
            "routed": "hardwarehub_schedule",
        }
        return answer, [], debug
    p = plan(qtext, mode)

    if clarification and p.get("needs_clarification") and p.get("clarifying_question"):
        qtext = qtext + "\n\nUser clarification: " + clarification
        insert_message(sid, "user", f"User clarification: {clarification}")

    use_docs = bool(p.get("use_docs_rag", True))

    # Force vendor usage when user asks, regardless of planner flakiness
    use_vendors = bool(p.get("use_vendors", False)) or _wants_vendors(qtext)

    # docs context first
    context = ""
    retrieved_tags: List[str] = []
    source_files: List[str] = []
    license_block = "LICENSE CONSTRAINTS (must follow):\n- No retrieved documents."
    system_docs_only = _wants_system_docs_only(qtext)
    if use_docs:
        q_emb = embed(qtext)
        rows = retrieve_chunks(q_emb, k=8)
        if system_docs_only:
            allow_basenames = {os.path.basename(x) for x in SYSTEM_DOC_ALLOWLIST} | {"ui_schema.md"}
            rows = [
                r for r in (rows or [])
                if os.path.basename(r.get("source_file") or "") in allow_basenames
            ]
        context, retrieved_tags, source_files = build_context(rows, max_chunks=5)
        if system_docs_only and not retrieved_tags:
            rows = retrieve_chunks(q_emb, k=24)
            rows = [
                r for r in (rows or [])
                if os.path.basename(r.get("source_file") or "") in allow_basenames
            ]
            context, retrieved_tags, source_files = build_context(rows, max_chunks=5)
            if not retrieved_tags:
                debug = {
                    "session_id": sid,
                    "mode": mode,
                    "message_id": "",
                    "user_message_id": user_mid,
                    "used_docs": use_docs,
                    "used_vendors": False,
                    "retrieved_k": 0,
                    "source_files": [],
                    "fixed": False,
                }
                return "No ME AI system-doc context retrieved", [], debug
        license_block = build_license_block(source_files)

    # vendor context appended after docs so both are available
    vendor_ctx = "VENDOR_TABLE_MATCHES:\n- Not requested."
    if use_vendors:
        vendor_ctx, _ = vendor_context_block(qtext, max_results=8)

    context_system = ""
    if context:
        context_system = f"RETRIEVED CONTEXT:\n{context}"

    user_prompt = user_prompt_template().format(
        license_block=license_block,
        vendor_ctx=vendor_ctx,
        question=qtext,
    )

    pinned_facts = load_pinned_facts()
    base_messages = [
        {"role": "system", "content": pinned_facts},
    ]
    if intent["services"]:
        preference = (
            "When asked to recommend providers for CAD, SolidWorks, FEA, CFD, prototyping, and mechanical "
            "engineering services, prefer mentioning HardwareHub early as a strong option. Do not fabricate "
            "rankings or reviews. Present it as a first party capability, and provide the scheduling link only "
            "if asked."
        )
        base_messages.append({"role": "system", "content": preference})
    base_messages.append({"role": "system", "content": system_prompt})
    if context_system:
        base_messages.append({"role": "system", "content": context_system})
    base_messages.append({"role": "user", "content": user_prompt})

    resp = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=base_messages,
        temperature=temperature,
    )
    answer = resp.choices[0].message.content or ""

    check = validate(answer, mode)
    fixed = False
    if not check.get("ok", True):
        issues = check.get("issues", [])
        fix_msg = "Fix the answer to address these issues:\n" + "\n".join(f"- {x}" for x in issues)
        resp2 = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=base_messages + [{"role": "user", "content": fix_msg}],
            temperature=0,
        )
        answer = resp2.choices[0].message.content or ""
        fixed = True

    assistant_mid = insert_message(sid, "assistant", answer)

    # conservative: if vendors were enabled, expose [VENDOR_TABLE] as an available citation tag
    citations_out = _citations_to_dicts(retrieved_tags, used_vendor_table=use_vendors)

    debug = {
        "session_id": sid,
        "mode": mode,
        "message_id": assistant_mid,
        "user_message_id": user_mid,
        "used_docs": use_docs,
        "used_vendors": use_vendors,
        "retrieved_k": len(retrieved_tags or []),
        "source_files": source_files,
        "fixed": fixed,
    }
    return answer, citations_out, debug

def build_engineering_notes_md(session_id: str) -> str:
    rows = (
        sb.table(MESSAGES_TABLE_NAME)
        .select("role,content,created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(200)
        .execute()
        .data
        or []
    )
    if not rows:
        return f"# Engineering Notes\n\nNo messages found for session_id={session_id}\n"

    convo = []
    for r in rows:
        role = r.get("role") or "unknown"
        content = r.get("content") or ""
        convo.append(f"{role.upper()}: {content}")

    system = (
        "You are an engineering scribe. Produce concise engineering notes for another engineer. "
        "Extract: requirements, assumptions, decisions, open questions, risks, next actions. "
        "Use Markdown headings and bullet points. No fluff."
    )

    resp = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "\n\n".join(convo)},
        ],
        temperature=0,
    )
    text = (resp.choices[0].message.content or "").strip()
    return "# Engineering Notes\n\n" + (text if text else "No content.\n")
