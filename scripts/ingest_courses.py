# scripts/ingest_courses.py
# Purpose: Step 1 ingestion — read data/course_data.csv, normalize fields, and upsert into public.courses.
# Run:     python scripts/ingest_courses.py

import os
import sys
import csv
from typing import List, Dict, Any, Optional
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client


# -----------------------------
# Helpers: env, client, paths
# -----------------------------
def load_env() -> Dict[str, str]:
    """Load required environment variables from .env and return them."""
    loaded = load_dotenv()
    if not loaded:
        print("⚠️  .env not found or not loaded; continuing but keys may be missing")
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url:
        print("❌ Missing SUPABASE_URL in .env")
        sys.exit(1)
    if not key:
        print("❌ Missing SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)
    return {"SUPABASE_URL": url, "SUPABASE_SERVICE_ROLE_KEY": key}


def make_supabase_client(url: str, key: str) -> Client:
    """Create and return a Supabase client."""
    try:
        client: Client = create_client(url, key)
        return client
    except Exception as e:
        print(f"❌ Failed to create Supabase client: {e}")
        sys.exit(1)


def resolve_csv_path(rel_path: str) -> Path:
    """Resolve and validate the CSV path exists."""
    p = Path(rel_path).resolve()
    if not p.exists():
        print(f"❌ CSV not found at: {p}")
        print("   Expected a file named course_data.csv under ./data/")
        sys.exit(1)
    return p


# -----------------------------
# Parsing / normalization
# -----------------------------
def parse_skills(raw: Optional[str]) -> List[str]:
    """Convert comma-separated skills string to a list[str]."""
    if raw is None:
        return []
    raw = raw.strip()
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def parse_bid_points(raw: Optional[str]) -> List[int]:
    """Convert comma-separated numbers string to list[int]. Skips blanks."""
    if raw is None:
        return []
    raw = raw.strip()
    if not raw:
        return []
    out: List[int] = []
    for piece in raw.split(","):
        s = piece.strip()
        if not s:
            continue
        try:
            out.append(int(s))
        except ValueError:
            # Skip any non-numeric artifacts
            print(f"⚠️  Skipping non-numeric bid_points value: {s!r}")
    return out


def read_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Read raw rows from CSV as list[dict] (strings as-is)."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
    return rows


def normalize_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single CSV row into the DB payload shape."""
    course_id = (raw.get("course_id") or "").strip()
    title = (raw.get("title") or "").strip()
    description = (raw.get("description") or "").strip()
    semester = (raw.get("semester") or "").strip()

    if not course_id or not title:
        raise ValueError("Missing required field(s): course_id and/or title")

    skills_list = parse_skills(raw.get("skills"))
    bid_points_list = parse_bid_points(raw.get("bid_points"))

    return {
        "course_id": course_id,
        "title": title,
        "description": description,
        "skills": skills_list,          # Postgres text[]
        "semester": semester,
        "bid_points": bid_points_list,  # Postgres integer[]
    }


def normalize_rows(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize all rows; skip bad rows but report them."""
    cleaned: List[Dict[str, Any]] = []
    skipped = 0
    for i, r in enumerate(raw_rows):
        try:
            cleaned.append(normalize_row(r))
        except Exception as e:
            skipped += 1
            print(f"⚠️  Skipping row {i} due to error: {e}")
    if skipped:
        print(f"ℹ️  Skipped {skipped} row(s) with validation errors.")
    return cleaned


def avg_latest_bid_point(cleaned_rows: List[Dict[str, Any]]) -> float:
    """Average of the last bid point for each row that has at least one value."""
    latest_vals: List[int] = []
    for r in cleaned_rows:
        bp = r.get("bid_points") or []
        if bp:
            latest_vals.append(bp[-1])
    if not latest_vals:
        return float("nan")
    return sum(latest_vals) / len(latest_vals)


# -----------------------------
# Database operations
# -----------------------------
def upsert_courses(client: Client, rows: List[Dict[str, Any]]) -> int:
    """Upsert rows into public.courses. Returns number of rows attempted."""
    if not rows:
        return 0
    # For small data, one batch is fine. (You can chunk later if needed.)
    try:
        _ = client.table("courses").upsert(rows).execute()
        return len(rows)
    except Exception as e:
        print(f"❌ Upsert failed: {e}")
        sys.exit(1)


def count_courses(client: Client) -> int:
    """Return total number of rows in public.courses."""
    # Using count='exact' to ask Supabase to return a row count
    try:
        resp = client.table("courses").select("*", count="exact").execute()
        # supabase-py returns .count on the response (may be None if provider changes)
        if hasattr(resp, "count") and resp.count is not None:
            return int(resp.count)
        # Fallback: len of returned data (not exact for large tables with limits)
        data = getattr(resp, "data", []) or []
        return len(data)
    except Exception as e:
        print(f"❌ Failed to count courses: {e}")
        sys.exit(1)


# -----------------------------
# Orchestrator
# -----------------------------
def main() -> None:
    # A) Env + client + csv path
    env = load_env()
    client = make_supabase_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    print("✅ env ok")
    print("✅ client ok")

    csv_path = resolve_csv_path("data/course_data.csv")
    print("✅ csv path ok")

    # B) Read + normalize
    raw_rows = read_csv_rows(csv_path)
    print(f"✅ parsed rows: {len(raw_rows)}")

    cleaned = normalize_rows(raw_rows)
    print(f"✅ cleaned rows: {len(cleaned)}")

    if not cleaned:
        print("❌ No valid rows to ingest after normalization. Exiting.")
        sys.exit(1)

    # Sanity beacons
    first = cleaned[0]
    print(f"first title: {first['title']}")
    print(f"first skills: {first['skills']}")
    print(f"first bid_points: {first['bid_points']}")
    avg_last = avg_latest_bid_point(cleaned)
    try:
        # round may raise on NaN; guard with isnan check
        from math import isnan
        if isnan(avg_last):
            print("avg latest bid_point: NaN (no bid_points present)")
        else:
            print(f"avg latest bid_point: {round(avg_last, 1)}")
    except Exception:
        print(f"avg latest bid_point: {avg_last}")

    # C) Upsert into DB + verify
    wrote = upsert_courses(client, cleaned)
    print(f"✅ upserted rows: {wrote}")

    db_count = count_courses(client)
    print(f"✅ db_count: {db_count}  | csv_cleaned_count: {len(cleaned)}")

    if db_count < len(cleaned):
        print("⚠️  Database count is lower than cleaned CSV count. Some rows may have been skipped.")
    else:
        print("🎉 Ingestion step completed.")


if __name__ == "__main__":
    main()
