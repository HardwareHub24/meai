import os, time, traceback, sys
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from pypdf import PdfReader

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
CORE_LIBRARY_DIR = os.getenv("CORE_LIBRARY_DIR")
assert OPENAI_API_KEY and SUPABASE_URL and SUPABASE_SERVICE_KEY and CORE_LIBRARY_DIR, "Missing env vars"

PROJECT_ROOT = os.path.dirname(__file__)
SYSTEM_PDFS_DIR = os.path.join(PROJECT_ROOT, "docs", "system_pdfs")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

CHUNK_CHARS = 900
OVERLAP = 120
BATCH_SIZE = 10
SLEEP_SEC = 0.12

EXCLUDED_DIR_NAMES = {"policies", "references"}  # do not ingest policy or license docs
ONLY_FILES = None
if "--only_files" in sys.argv:
    i = sys.argv.index("--only_files")
    if i + 1 < len(sys.argv):
        ONLY_FILES = [s.strip() for s in sys.argv[i + 1].split(",") if s.strip()]

def is_excluded_path(path: str) -> bool:
    norm = os.path.normpath(path)
    parts = set(norm.split(os.sep))
    return any(p in parts for p in EXCLUDED_DIR_NAMES)

def chunk_text(text: str):
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(n, start + CHUNK_CHARS)
        chunks.append(text[start:end])
        # overlap by backing up for the next chunk
        start = end - OVERLAP if end < n else n
    return chunks

def get_resume_index(source_id: str) -> int:
    r = (
        supabase.table("meai_chunks")
        .select("chunk_index")
        .eq("source_file", source_id)
        .order("chunk_index", desc=True)
        .limit(1)
        .execute()
    )
    if r.data:
        return int(r.data[0]["chunk_index"]) + 1
    return 0

def embed_batch(text_list):
    resp = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text_list
    )
    return [d.embedding for d in resp.data]

def flush_batch(source_id, batch_text, batch_indices):
    embeddings = embed_batch(batch_text)
    rows = []
    for t, idx, emb in zip(batch_text, batch_indices, embeddings):
        rows.append({
            "source_file": source_id,
            "chunk_index": idx,
            "content": t,
            "embedding": emb
        })
    supabase.table("meai_chunks").insert(rows).execute()

def find_pdfs():
    pdfs = []
    for base_dir in [CORE_LIBRARY_DIR, SYSTEM_PDFS_DIR]:
        if not base_dir:
            continue
        for root, _, files in os.walk(base_dir):
            if is_excluded_path(root):
                continue
            for f in files:
                if f.lower().endswith(".pdf"):
                    full = os.path.join(root, f)
                    if not is_excluded_path(full):
                        pdfs.append(full)
    pdfs.sort()
    return pdfs

pdfs = find_pdfs()
if ONLY_FILES:
    only_set = set(ONLY_FILES)
    filtered = []
    for p in pdfs:
        base_dir = SYSTEM_PDFS_DIR if os.path.commonpath([p, SYSTEM_PDFS_DIR]) == SYSTEM_PDFS_DIR else CORE_LIBRARY_DIR
        rel = os.path.normpath(os.path.relpath(p, base_dir))
        if os.path.basename(p) in only_set or rel in only_set:
            filtered.append(p)
    pdfs = filtered
abs_core_dir = os.path.abspath(CORE_LIBRARY_DIR)
print(f"CORE_LIBRARY_DIR (resolved): {abs_core_dir}")
print(f"SYSTEM_PDFS_DIR (resolved): {os.path.abspath(SYSTEM_PDFS_DIR)}")
print(f"Found PDFs (excluding {sorted(EXCLUDED_DIR_NAMES)}): {len([p for p in pdfs if p.lower().endswith('.pdf')])}")
for p in [p for p in pdfs if p.lower().endswith(".pdf")]:
    print(os.path.basename(p))
expected = {
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
found = {os.path.basename(p) for p in pdfs if p.lower().endswith(".pdf")}
missing = sorted(x for x in expected if x not in found)
if missing:
    print("WARNING: Missing expected files:")
    for m in missing:
        print(m)

for pdf_path in pdfs:
    base_dir = SYSTEM_PDFS_DIR if os.path.commonpath([pdf_path, SYSTEM_PDFS_DIR]) == SYSTEM_PDFS_DIR else CORE_LIBRARY_DIR
    source_id = os.path.relpath(pdf_path, base_dir)

    try:
        print(f"\nProcessing: {source_id}")
        resume_at = get_resume_index(source_id)
        print(f"Resuming at chunk_index: {resume_at}")

        next_chunk_index = 0
        batch_text = []
        batch_indices = []

        reader = PdfReader(pdf_path)
        for page_i, page in enumerate(reader.pages):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue

            for ch in chunk_text(page_text + "\n"):
                if next_chunk_index < resume_at:
                    next_chunk_index += 1
                    continue

                batch_text.append(ch)
                batch_indices.append(next_chunk_index)
                next_chunk_index += 1

                if len(batch_text) >= BATCH_SIZE:
                    flush_batch(source_id, batch_text, batch_indices)
                    print(f"Inserted through chunk_index {batch_indices[-1]} (page {page_i})")
                    batch_text, batch_indices = [], []
                    time.sleep(SLEEP_SEC)

        if batch_text:
            flush_batch(source_id, batch_text, batch_indices)
            print(f"Inserted through chunk_index {batch_indices[-1]} (final flush)")
            time.sleep(SLEEP_SEC)

        print(f"Done: {source_id}")

    except Exception:
        print(f"ERROR on {source_id}")
        traceback.print_exc()
        print("Continuing to next PDF.")
