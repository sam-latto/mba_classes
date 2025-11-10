import os
from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


# Load .env from the project root when running locally
load_dotenv()

def get_supabase() -> Client:
    """Return an authenticated Supabase client using env vars."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    print(f"SUPABASE_URL found: {bool(url)}, key length: {len(key or '')}")

    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    return create_client(url, key)


def get_table_name() -> str:
    """Return the courses table name (defaults to 'courses')."""
    return os.getenv("COURSES_TABLE", "courses")


def search_courses_by_title(client, table_name: str, query: str, k: int = 10):
    """
    Return up to k rows where the course title contains the query (case-insensitive).
    """
    q = client.table(table_name).select(
        "course_id,title,instructor,credits"
    ).ilike("title", f"%{query}%").limit(k).execute()

    # Supabase response shape: has .data (list) and .error (None or object)
    rows = q.data or []
    return rows

