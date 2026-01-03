import os, time, traceback
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

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

CHUNK_CHARS = 900
OVERLAP = 120
BATCH_SIZE = 10
SLEEP_SEC = 0.12

EXCLUDED_DIR_NAMES = {"policies", "references"}  # do not ingest policy or license docs

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
    for root, _, files in os.walk(CORE_LIBRARY_DIR):
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
print(f"Found PDFs (excluding {sorted(EXCLUDED_DIR_NAMES)}): {len(pdfs)}")

for pdf_path in pdfs:
    source_id = os.path.relpath(pdf_path, CORE_LIBRARY_DIR)

    try:
        print(f"\nProcessing: {source_id}")
        resume_at = get_resume_index(source_id)
        print(f"Resuming at chunk_index: {resume_at}")

        reader = PdfReader(pdf_path)

        next_chunk_index = 0
        batch_text = []
        batch_indices = []

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
