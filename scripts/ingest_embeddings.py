# scripts/ingest_embeddings.py
# Step 2 — Milestone A: Plan & Config (no API calls yet)

import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# ======== CONFIG (edit as you like) ========
EMBEDDING_MODEL_ID = "text-embedding-3-small"   # plan: OpenAI embedding model
VECTOR_DIM = 1536                                # must match your table's vector(1536)
BATCH_SIZE = 50                                  # for larger datasets; fine to lower/raise
TEXT_MAX_CHARS = 500                             # trim description length to control cost
# ===========================================


# ---------- Env & Client ----------
def load_env() -> Dict[str, str]:
    """Load required environment variables from .env and return them."""
    load_dotenv()
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url:
        print("❌ Missing SUPABASE_URL in .env"); sys.exit(1)
    if not key:
        print("❌ Missing SUPABASE_SERVICE_ROLE_KEY in .env"); sys.exit(1)
    return {"SUPABASE_URL": url, "SUPABASE_SERVICE_ROLE_KEY": key}


def make_supabase_client(url: str, key: str) -> Client:
    """Create and return a Supabase client."""
    try:
        return create_client(url, key)
    except Exception as e:
        print(f"❌ Failed to create Supabase client: {e}")
        sys.exit(1)


# ---------- Placeholders for later milestones ----------
def fetch_courses(client: Client) -> List[Dict[str, Any]]:
    """
    Milestone B (next): Read rows from public.courses.
    Return shape: [{ 'course_id': str, 'title': str, 'description': str }, ...]
    """
    # TODO: implement in Milestone B
    # read rows from public.courses
    response = client.table("courses").select("course_id, title, description").execute()
    rows = response.data
    if not rows:
        return []
    
    # 2) Validate & normalize each row
    cleaned: list[dict] = []
    for i, row in enumerate(rows):
        course_id = (row.get("course_id") or "").strip()
        title = (row.get("title") or "").strip()
        # description can be empty; normalize None -> ""
        description = (row.get("description") or "").strip()

        # required fields check (covers None, "", and whitespace-only)
        if not course_id or not title:
            # no prints here; keep function pure — main() can report skipped counts if you want
            continue

        cleaned.append({
            "course_id": course_id,
            "title": title,
            "description": description,
        })

    return cleaned


def build_embedding_text(row: Dict[str, Any]) -> str:
    """
    Milestone B (next): Build 'title — description[:TEXT_MAX_CHARS]' for each row.
    """
    # TODO: implement in Milestone B
def build_embedding_text(row):
    # 1️⃣ Get the fields safely
    title = (row.get("title") or "").strip()
    desc = (row.get("description") or "").strip()

    # 2️⃣ If there's no description, just return the title
    if not desc:
        return title

    # 3️⃣ Clean description (remove newlines, limit length)
    desc = desc.replace("\n", " ")
    desc = " ".join(desc.split())          # collapses extra spaces
    desc = desc[:TEXT_MAX_CHARS]           # limit to your max chars (e.g., 500)

    # 4️⃣ Avoid repeating the title at the start of the description
    if desc.lower().startswith(title.lower()):
        desc = desc[len(title):].strip(" -:;")

    # 5️⃣ Combine title + description
    text = f"{title} — {desc}"
    return text.strip()



def create_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Milestone C (later): Call provider to get vectors of length VECTOR_DIM.
    """
    # TODO: implement in Milestone C
        # 🧩 1️⃣ Set up your embedding model
    # Choose the embedding model you’ll use (e.g., text-embedding-3-small).
    # Record its expected output dimension (1536) for later validation.
    EMBEDDING_MODEL = "text-embedding-3-small"   # lightweight, cost-efficient
    EMBEDDING_DIM = 1536                         # number of floats per vector
    BATCH_SIZE = 50                              # safe upper bound for requests

    print(f"🔎 embedding_model: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")


    # 🧮 2️⃣ Check your input data
    # Print the number of course texts so you know how many you’ll embed.
    # Optionally, inspect the first one to confirm it looks like “Title – Description”.
    print(f"📥 Number of texts to embed: {len(texts)}")
    print(f"🧪 Example text[0]: {texts[0][:100]}{'...' if len(texts[0]) > 100 else ''}")
    if len(texts) == 0:
        print("❌ No texts provided for embedding.")
        return []
    


    # ⚙️ 3️⃣ Send the texts to the embeddings API
    # Use your OpenAI client to create embeddings for all texts.
    # You can embed them in one batch since you have only ~20.
    # Capture the response that comes back from the API.
    print(f"⚙️  Sending {len(texts)} texts to embedding API in batches of {BATCH_SIZE}...")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    embeddings: List[List[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        print(f"   📦 Processing batch {i // BATCH_SIZE + 1} with {len(batch)} texts...")
        # Call your embedding API here (pseudocode)
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        # Extract embeddings from response and append to embeddings list
        for item in response.data:
            embeddings.append(item.embedding)
        # For now, just append dummy data

    print(f"✅ Received {len(embeddings)} embeddings from API.")


    # 🔍 5️⃣ Validate shapes and counts
    # Confirm the number of embeddings equals the number of texts you sent.
    # Check that each embedding’s length matches 1536.
    # Print a confirmation message showing both values.
    if len(embeddings) != len(texts):
        print(f"❌ Mismatch: {len(embeddings)} embeddings for {len(texts)} texts.")
        return []
    for i, vec in enumerate(embeddings):
        if len(vec) != EMBEDDING_DIM:
            print(f"❌ Embedding {i} has dimension {len(vec)}; expected {EMBEDDING_DIM}.")
            return []

    # 🧠 6️⃣ Optionally inspect one vector
    # Print the first few numbers of the first vector to verify it looks like small decimal values.
    # (This helps catch formatting or response issues.)

    # 🧾 7️⃣ Return the list of vectors
    # Return all embeddings so the next step (upsert to Supabase) can use them.
    return embeddings


def upsert_course_embeddings(client: Client, items: List[Dict[str, Any]]) -> int:
    """
    Milestone D (later): Upsert [{'course_id': ..., 'embedding': [...]}, ...] into public.course_embeddings.
    """
    # TODO: implement in Milestone D
    if not items:
        return 0
    # 2) Optional: print how many you’re sending (helpful when you scale)
    print(f"🚚 sending {len(items)} items to upsert...")

    # 3) Perform the upsert
    try:
        _ = client.table("course_embeddings").upsert(items).execute()
        print("✅ upsert call succeeded.")
        return len(items)
    except Exception as e:
        # 4) Loud, actionable failure
        print("❌ Upsert failed.")
        print("   Hints:")
        print("   • Ensure SUPABASE_SERVICE_ROLE_KEY is used (not anon).")
        print("   • Ensure table public.course_embeddings exists with columns:")
        print("     - course_id TEXT (PRIMARY KEY or UNIQUE)")
        print("     - embedding  VECTOR(1536)")
        print(f"   Details: {e}")
        raise


    
    


def count_table(client: Client, table: str) -> int:
    """
    Utility: Count rows in a table (used for quick sanity checks).
    """
    try:
        resp = client.table(table).select("*", count="exact").execute()
        if hasattr(resp, "count") and resp.count is not None:
            return int(resp.count)
        return len(getattr(resp, "data", []) or [])
    except Exception as e:
        print(f"⚠️ count_table('{table}') failed: {e}")
        return -1


# ---------- Orchestrator ----------
def main() -> None:
    # ===== Milestone A: Plan & Config =====
    env = load_env()
    sb = make_supabase_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    print("✅ env ok")
    print("✅ client ok")
    print(f"🔎 embedding_model: {EMBEDDING_MODEL_ID} (dim={VECTOR_DIM})")
    print(f"🔎 batch_size: {BATCH_SIZE}, text_max_chars: {TEXT_MAX_CHARS}")

    total_courses = count_table(sb, "courses")
    print(f"📦 courses in DB: {total_courses if total_courses >= 0 else 'unknown'}")

    # ===== Milestone B: Fetch courses & build texts =====
    rows = fetch_courses(sb)  # must return [{course_id, title, description}, ...]
    if not rows:
        print("❌ No courses fetched; check table name, RLS policies, or data.")
        sys.exit(1)
    print(f"📥 fetched courses: {len(rows)}")

    # # Build text inputs for embedding
    texts = [build_embedding_text(r) for r in rows]
    print(f"🧰 prepared texts for embedding: {len(texts)}")
    # show 1–2 examples (truncated) for sanity
    ex0 = texts[0][:120].replace("\n", " ")
    print(f"🧪 example[0]: {ex0}{'...' if len(texts[0]) > 120 else ''}")
    if len(texts) > 1:
        ex1 = texts[1][:120].replace("\n", " ")
        print(f"🧪 example[1]: {ex1}{'...' if len(texts[1]) > 120 else ''}")

    # # ===== Milestone C: Create embeddings =====
    vectors = create_embeddings(texts)  # must return list[list[float]] of length == len(texts)
    if not vectors or len(vectors) != len(texts):
        print(f"❌ Embedding count mismatch: got {len(vectors) if vectors else 0}, expected {len(texts)}")
        sys.exit(1)
    # quick dimensionality check on the first vector
    dim = len(vectors[0]) if vectors else 0
    print(f"✅ created embeddings: {len(vectors)} (sample dim={dim})")
    if dim != VECTOR_DIM:
        print(f"⚠️ vector dimension {dim} != expected {VECTOR_DIM} — check model/table setup")

    # Build upsert payload
    items = [{"course_id": r["course_id"], "embedding": v} for r, v in zip(rows, vectors)]

    # # ===== Milestone D: Upsert into course_embeddings =====
    written = upsert_course_embeddings(sb, items)
    print(f"✅ upserted embeddings: {written}")

    # # ===== Milestone E: Verify counts =====
    ce_count = count_table(sb, "course_embeddings")
    co_count = count_table(sb, "courses")
    print(f"✅ counts — courses: {co_count} | course_embeddings: {ce_count}")

    if ce_count == co_count and ce_count == len(rows):
        print("🎉 embeddings ingestion completed (counts match).")
    else:
        print("⚠️ Counts do not match. Investigate missing or failed rows.")
        missing = co_count - ce_count if (co_count >= 0 and ce_count >= 0) else "unknown"
        print(f"   Difference (courses - embeddings): {missing}")
        sys.exit(2)


if __name__ == "__main__":
    main()

