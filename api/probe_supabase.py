from pprint import pprint
from services.supabase_client import get_supabase, get_table_name


if __name__ == "__main__":
    sb = get_supabase()
    table = get_table_name()
    resp = sb.table(table).select("course_id,title").limit(3).execute()
    print("=== Supabase Probe ===")
    pprint({"count": len(resp.data or []), "sample": resp.data})
