# scripts/query_courses.py
# Step 3 — Retrieval: embed a query, call match_courses(), print top-k.
import os
import sys
import argparse
from typing import List, Dict, Any

from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI


# ---------- Config (must match your embedding table/model) ----------
EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
DEFAULT_TOP_K = 5
# -------------------------------------------------------------------


def load_env() -> Dict[str, str]:
    load_dotenv()
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    oai = (os.getenv("OPENAI_API_KEY") or "").strip()
    missing = [name for name, val in [
        ("SUPABASE_URL", url), ("SUPABASE_SERVICE_ROLE_KEY", key), ("OPENAI_API_KEY", oai)
    ] if not val]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}"); sys.exit(1)
    return {"SUPABASE_URL": url, "SUPABASE_SERVICE_ROLE_KEY": key, "OPENAI_API_KEY": oai}


def make_clients(env: Dict[str, str]) -> tuple[Client, OpenAI]:
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    oai = OpenAI()  # reads OPENAI_API_KEY from env automatically
    return sb, oai


def embed_query(oai: OpenAI, text: str) -> List[float]:
    """
    Turn the user query into a 1536-d vector using the SAME model you used for courses.
    """
    text = (text or "").strip()
    if not text:
        print("❌ Empty query."); sys.exit(1)

    # light cleanup: keep queries short & focused to improve retrieval quality
    if len(text) > 500:
        text = text[:500]

    resp = oai.embeddings.create(model=EMBEDDING_MODEL, input=[text])
    vec = resp.data[0].embedding
    if len(vec) != EMBED_DIM:
        print(f"❌ Embedding dim {len(vec)} != expected {EMBED_DIM}"); sys.exit(1)
    return vec


def search_courses(sb: Client, qvec: List[float], k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
    """
    Calls the SQL function `match_courses` via RPC to get top-k most similar courses.
    Returns a list of dicts with course_id, title, description, distance.
    """
    try:
        resp = sb.rpc("match_courses", {"query_embedding": qvec, "match_count": k}).execute()
        rows = resp.data or []
        return rows
    except Exception as e:
        print("❌ RPC call failed. Did you create the SQL function `match_courses`?")
        print("   Run: sql/match_courses.sql in Supabase SQL Editor.")
        print(f"   Details: {e}")
        sys.exit(1)


def pretty_print(results: List[Dict[str, Any]]) -> None:
    if not results:
        print("∅ No matches found."); return
    print("\nTop matches:")
    for i, r in enumerate(results, 1):
        cid = r.get("course_id", "")
        title = r.get("title", "")
        desc = (r.get("description") or "").replace("\n", " ")
        dist = r.get("distance")
        snippet = (desc[:140] + "…") if len(desc) > 140 else desc
        print(f"{i}. [{cid}] {title}")
        print(f"   distance: {dist:.4f}")
        print(f"   {snippet}\n")


def main() -> None:
    # 0) Parse CLI args
    parser = argparse.ArgumentParser(description="Semantic course search (Supabase + pgvector)")
    parser.add_argument("--query", "-q", required=True, help="Search text, e.g. 'product management analytics'")
    parser.add_argument("--k", "-k", type=int, default=DEFAULT_TOP_K, help="How many results to return")
    args = parser.parse_args()

    # 1) Setup
    env = load_env()
    sb, oai = make_clients(env)
    print("✅ env + clients ready")
    print(f"🔎 model: {EMBEDDING_MODEL} (dim={EMBED_DIM})")

    # 2) Embed the user query
    qvec = embed_query(oai, args.query)
    print(f"✅ query embedded (dim={len(qvec)})")

    # 3) Vector search via SQL function
    results = search_courses(sb, qvec, k=args.k)
    print(f"✅ retrieved {len(results)} results")

    # 4) Show results
    pretty_print(results)


if __name__ == "__main__":
    main()
