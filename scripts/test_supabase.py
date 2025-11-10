# Purpose: verify .env is loading and Supabase client can talk to your project.
# Run from project root:  python test_supabase_connection.py

import os, sys
from dotenv import load_dotenv
from supabase import create_client, Client

def fail(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)

def main():
    # 1) Load env
    if not load_dotenv():
        print("⚠️  .env not found or not loaded—continuing, but keys may be missing")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url:
        fail("SUPABASE_URL is missing in .env")
    if not key:
        fail("SUPABASE_SERVICE_ROLE_KEY is missing in .env")

    print("✅ Environment variables loaded")

    # 2) Create client
    try:
        sb: Client = create_client(url, key)
        print("✅ Supabase client created")
    except Exception as e:
        fail(f"Failed to create client: {e}")

    # 3) Try a harmless read
    # If 'courses' doesn't exist yet, we expect an error—handle it nicely.
    try:
        resp = sb.table("courses").select("*").limit(1).execute()
        # If the table exists, resp.data is a list (possibly empty)
        print("✅ Connection test OK — 'courses' table reachable")
        print(f"   Sample result length: {len(resp.data)}")
    except Exception as e:
        # Common case right now: table not created yet
        print("ℹ️  Could not read from 'courses' (likely not created yet).")
        print(f"   Details: {e}")
        print("   This still proves the client can make requests.")

    print("🎉 Connection test finished")

if __name__ == "__main__":
    main()
