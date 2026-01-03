import os
import re
import json
import uuid
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

# ========= logging =========
LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "sessions.jsonl")

def ensure_log_dir():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def log_event(event: dict):
    ensure_log_dir()
    event["ts"] = datetime.utcnow().isoformat()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

# ========= env + clients =========
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
assert OPENAI_API_KEY and SUPABASE_URL and SUPABASE_SERVICE_KEY, "Missing env vars"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

VENDOR_TABLE_NAME = "meai_vendors"
DOCUMENTS_TABLE_NAME = "meai_documents"
LICENSES_TABLE_NAME = "meai_licenses"

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# New MVP: only two modes with files prompts/mode_1.txt and prompts/mode_2.txt
MODE_MAP = {
    "1": ("mode_1", "Mode 1: Guidance (Sense-Making)"),
    "2": ("mode_2", "Mode 2: Verification (Technical Validation)"),
}

LLM_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"

# Must match your meai_documents schema. Your DB has source_url.
DOC_SOURCE_COL = "source_url"

# ========= prompts =========
def load_prompt(name: str) -> str:
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing prompt file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

# ========= harness: planner + validator =========
def plan(question: str, mode_name: str) -> dict:
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
        data = json.loads(raw)
    except Exception:
        data = {
            "needs_clarification": False,
            "clarifying_question": "",
            "use_docs_rag": True,
            "use_vendors": False,
        }
    return data

def validate(answer: str, mode_name: str) -> dict:
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
        data = json.loads(raw)
    except Exception:
        data = {"ok": True, "issues": []}
    return data

# ========= embeddings + retrieval =========
def embed(text: str):
    return openai_client.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding

def retrieve_chunks(query_embedding, k=8):
    return sb.rpc(
        "match_meai_chunks",
        {"query_embedding": query_embedding, "match_count": k}
    ).execute().data

def is_garbage(chunk: str) -> bool:
    if not chunk or len(chunk) < 80:
        return True
    digits = sum(c.isdigit() for c in chunk)
    return (digits / max(len(chunk), 1)) > 0.35

def build_context(rows, max_chunks=5):
    ctx, citations, source_files = [], [], []
    for r in rows or []:
        content = r.get("content", "")
        if is_garbage(content):
            continue
        sf = r.get("source_file")
        ci = r.get("chunk_index")
        if sf is None or ci is None:
            continue
        ctx.append(content)
        citations.append(f"[{sf}:{ci}]")
        source_files.append(sf)
        if len(ctx) >= max_chunks:
            break
    # de-dupe citations/source_files but preserve order
    return "\n\n".join(ctx), list(dict.fromkeys(citations)), list(dict.fromkeys(source_files))

# ========= documents + licenses =========
def fetch_documents_by_source_files(source_files):
    """
    Chunks provide meai_chunks.source_file.
    meai_documents uses DOC_SOURCE_COL = source_url.
    If these values do not match, this returns [] (fail-safe).
    """
    if not source_files:
        return []
    try:
        resp = (
            sb.table(DOCUMENTS_TABLE_NAME)
            .select("*")
            .in_(DOC_SOURCE_COL, source_files)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []

def fetch_licenses_by_keys(license_keys):
    if not license_keys:
        return []
    resp = (
        sb.table(LICENSES_TABLE_NAME)
        .select("*")
        .in_("license_key", list(dict.fromkeys(license_keys)))
        .execute()
    )
    return resp.data or []

def build_license_block(source_files):
    docs = fetch_documents_by_source_files(source_files)
    doc_by_sf = {d.get(DOC_SOURCE_COL): d for d in docs if d.get(DOC_SOURCE_COL)}

    license_keys = []
    for sf in source_files:
        d = doc_by_sf.get(sf, {})
        lk = d.get("license_key") or d.get("license") or d.get("license_id")
        if lk:
            license_keys.append(lk)

    licenses = fetch_licenses_by_keys(license_keys)
    lic_by_key = {l.get("license_key"): l for l in licenses if l.get("license_key")}

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

        citation_required = bool(lic.get("citation_required")) if lic.get("citation_required") is not None else True
        attribution_required = bool(lic.get("attribution_required")) if lic.get("attribution_required") is not None else False
        verbatim_allowed = bool(lic.get("verbatim_allowed")) if lic.get("verbatim_allowed") is not None else False
        verbatim_char_limit = lic.get("verbatim_char_limit")
        derivatives_allowed = bool(lic.get("derivatives_allowed")) if lic.get("derivatives_allowed") is not None else True
        sharealike_required = bool(lic.get("sharealike_required")) if lic.get("sharealike_required") is not None else False
        commercial_use_allowed = bool(lic.get("commercial_use_allowed")) if lic.get("commercial_use_allowed") is not None else True

        lines.append(f"  license_key: {lk}")
        lines.append(f"  commercial_use_allowed: {commercial_use_allowed}")
        lines.append(f"  derivatives_allowed: {derivatives_allowed}")
        lines.append(f"  sharealike_required: {sharealike_required}")
        lines.append(f"  verbatim_allowed: {verbatim_allowed}")
        if verbatim_char_limit is not None:
            lines.append(f"  verbatim_char_limit: {verbatim_char_limit}")
        lines.append(f"  citation_required: {citation_required}")
        lines.append(f"  attribution_required: {attribution_required}")

    return "\n".join(lines)

# ========= vendors =========
def parse_vendor_hints(question: str):
    q = question.lower()

    industries = []
    for token in [
        "medical", "medtech", "aerospace", "automotive", "consumer",
        "industrial", "electronics", "robotics", "defense"
    ]:
        if re.search(rf"\b{re.escape(token)}\b", q):
            industries.append(token)

    capabilities = []
    m = re.search(r"(looking for|need|seeking)\s+(a|an)?\s*([^.;,]+)", q)
    if m:
        capabilities.append(m.group(3).strip())

    return industries or None, capabilities or None

def retrieve_vendors(industries=None, capabilities=None, max_results=8):
    q = sb.table(VENDOR_TABLE_NAME).select("*").limit(max_results)

    if industries:
        for t in industries:
            q = q.ilike("industries", f"%{t}%")

    if capabilities:
        term = capabilities[0].strip()
        if term:
            q = q.or_(
                f"category.ilike.%{term}%,"
                f"description.ilike.%{term}%,"
                f"capabilities.ilike.%{term}%,"
                f"notes.ilike.%{term}%"
            )

    return q.execute().data or []

def format_vendor_block(vendors):
    if not vendors:
        return (
            "VENDOR RECOMMENDATIONS:\n"
            "- None found in meai_vendors for the current filters.\n"
            "- If needed, suggest an external vendor category + search terms."
        )

    lines = ["VENDOR RECOMMENDATIONS (prefer these; cite as [VENDOR_TABLE] only if used):"]
    for v in vendors[:8]:
        name = v.get("name") or "Unknown"
        cat = v.get("category") or ""
        industries = v.get("industries") or ""
        website = v.get("website") or v.get("url") or ""
        contact = v.get("contact_name") or ""
        email = v.get("email") or ""
        phone = v.get("phone") or ""

        header = f"- {name}"
        if cat:
            header += f" ({cat})"
        lines.append(header)

        if industries:
            lines.append(f"  industries: {industries}")
        if website:
            lines.append(f"  website: {website}")
        if contact:
            lines.append(f"  contact: {contact}")
        if email:
            lines.append(f"  email: {email}")
        if phone:
            lines.append(f"  phone: {phone}")

    return "\n".join(lines)

# ========= ui helpers =========
def choose_mode() -> str:
    print("Select mode: 1=Guidance  2=Verification")
    choice = input("M> ").strip()
    return MODE_MAP.get(choice, MODE_MAP["1"])[0]

def user_prompt_template(mode_name: str) -> str:
    # Both modes share the same wrapper; differences live in the system prompts.
    # Vendors are optional and controlled by the planner.
    return """
CONTEXT (use as primary reference):
{context}

{license_block}

VENDOR_TABLE_SNIPPET (curated rolodex; use only if relevant; cite as [VENDOR_TABLE] only if used):
{vendor_block}

USER QUESTION:
{question}

RESPONSE REQUIREMENTS:
- Follow the selected mode system prompt contract.
- Do not block progress for missing inputs; use explicit working assumptions.
- If you use any factual claim from CONTEXT, cite inline using [source_file:chunk_index].
- End with "Citations:" listing only tags you actually used.
""".strip()

# ========= main loop =========
print("\nMEAI Mechanical Engineer RAG CLI")
print("Single-line questions only. Ctrl+C to exit.\n")

SESSION_ID = str(uuid.uuid4())
print(f"Session: {SESSION_ID}")
log_event({"type": "session_start", "session_id": SESSION_ID, "model": LLM_MODEL})

while True:
    try:
        mode_name = choose_mode()
        system_prompt = load_prompt(mode_name)

        question = input("Q> ").strip()
        if not question:
            continue
        if question.startswith("Q>"):
            question = question[2:].strip()

        log_event({"type": "question", "session_id": SESSION_ID, "mode": mode_name, "question": question})

        p = plan(question, mode_name)
        log_event({"type": "plan", "session_id": SESSION_ID, "mode": mode_name, "plan": p})

        clar = ""
        # Planner can still ask for clarification, but we keep it optional and single-shot.
        if p.get("needs_clarification") and p.get("clarifying_question"):
            clar = input(f"CLARIFY> {p['clarifying_question']} ").strip()
            if clar:
                question = question + "\n\nUser clarification: " + clar
            log_event({
                "type": "clarify",
                "session_id": SESSION_ID,
                "mode": mode_name,
                "clarifying_question": p.get("clarifying_question", ""),
                "clarification": clar
            })

        use_docs = bool(p.get("use_docs_rag", True))
        use_vendors = bool(p.get("use_vendors", False))

        context = ""
        citations = []
        source_files = []
        license_block = "LICENSE CONSTRAINTS (must follow):\n- No retrieved documents."
        if use_docs:
            q_emb = embed(question)
            rows = retrieve_chunks(q_emb, k=8)
            context, citations, source_files = build_context(rows, max_chunks=5)
            license_block = build_license_block(source_files)

        vendor_block = "VENDOR RECOMMENDATIONS:\n- None (not requested)."
        if use_vendors:
            industries, capabilities = parse_vendor_hints(question)
            vendors = retrieve_vendors(
                industries=industries,
                capabilities=capabilities,
                max_results=8
            )
            vendor_block = format_vendor_block(vendors)

        log_event({
            "type": "retrieval",
            "session_id": SESSION_ID,
            "mode": mode_name,
            "used_docs": use_docs,
            "used_vendors": use_vendors,
            "source_files": source_files,
            "citations_retrieved": citations,
            "vendor_count": 0 if vendor_block.startswith("VENDOR RECOMMENDATIONS:\n- None") else 1
        })

        user_prompt = user_prompt_template(mode_name).format(
            context=context,
            license_block=license_block,
            vendor_block=vendor_block,
            question=question
        )

        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        answer = resp.choices[0].message.content or ""

        check = validate(answer, mode_name)
        log_event({
            "type": "validate",
            "session_id": SESSION_ID,
            "mode": mode_name,
            "ok": check.get("ok", True),
            "issues": check.get("issues", [])
        })

        fixed = False
        if not check.get("ok", True):
            issues = check.get("issues", [])
            fix_msg = "Fix the answer to address these issues:\n" + "\n".join(f"- {x}" for x in issues)
            resp2 = openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                    {"role": "user", "content": fix_msg}
                ],
                temperature=0
            )
            answer = resp2.choices[0].message.content or ""
            fixed = True

        log_event({
            "type": "answer",
            "session_id": SESSION_ID,
            "mode": mode_name,
            "fixed": fixed,
            "answer_len_chars": len(answer)
        })

        print("\nANSWER:\n")
        print(answer)

        if citations:
            print("\nRetrieved sources (retrieved, not necessarily used):")
            for c in citations:
                print(c)

        print("\n" + ("=" * 70) + "\n")

    except KeyboardInterrupt:
        log_event({"type": "session_end", "session_id": SESSION_ID})
        print("\nExiting.")
        break
