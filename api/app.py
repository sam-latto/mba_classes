import os
import time
from flask import Flask, request, jsonify  # <- include jsonify
import json
from openai import OpenAI
from flask_cors import CORS
from dotenv import load_dotenv
import re
from api.services.supabase_client import get_supabase, get_table_name, search_courses_by_title



# --- App & Config ---
client = OpenAI()
load_dotenv()  # reads .env in development
app = Flask(__name__)
print("Launching app from:", __file__)
print("Routes at startup:", app.url_map)


CORS(app, resources={r"/*": {"origins": "*"}})  # relax in dev; tighten later

# Simple helper to make consistent JSON responses
def ok(data=None, status=200, took_ms=None):
    body = data if isinstance(data, dict) else {"data": data}
    if took_ms is not None:
        body["took_ms"] = took_ms
    return jsonify(body), status

def err(message, status=400, took_ms=None):
    body = {"error": message}
    if took_ms is not None:
        body["took_ms"] = took_ms
    return jsonify(body), status

# --- Healthcheck (keeps us honest) ---
@app.route("/health", methods=["GET"])
def health():
    return ok({"ok": True}, status=200)

# --- Example pattern we’ll use for /search soon ---
@app.post("/search")
def search():
    start = time.time()

    # 1) Parse JSON (fail loudly if not valid JSON)
    try:
        body = request.get_json(force=True, silent=False) or {}
    except Exception:
        return err("Request body must be valid JSON", status=400, took_ms=int((time.time()-start)*1000))

    # 2) Accept either "q" or "query"
    q = (body.get("q") or body.get("query") or "").strip()

    # 3) Validate k (coerce to int if passed as a string)
    try:
        k = int(body.get("k", 10))
    except Exception:
        k = -1  # force validation failure below

    if not q:
        return err("Missing or invalid 'query' (use 'q' or 'query')", status=400, took_ms=int((time.time()-start)*1000))
    if not (1 <= k <= 25):
        return err("Invalid 'k' value (must be 1–25)", status=422, took_ms=int((time.time()-start)*1000))

    # 2) Query Supabase
       # 2) Query Supabase (safe)
    # --- Direct REST call to Supabase (bypasses SDK to avoid proxy mismatch) ---
    import os, requests
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    API_KEY = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_KEY")
    )
    if not SUPABASE_URL or not API_KEY:
        return err("Missing SUPABASE_URL or API key", 500, int((time.time() - start) * 1000))

    table = "courses"  # change if your table has a different name

    # Build PostgREST filter: title ilike %q%
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": API_KEY,
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    params = {
        "select": "course_id,title,description",
        "title": f"ilike.*{q}*",
        "limit": k,
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        rows = r.json()

    except requests.HTTPError as e:
        # Surface Supabase’s exact error text (e.g. invalid column/table)
        detail = ""
        try:
            detail = r.text
        except Exception:
            pass
        return err(f"Search failed (REST): {e} | {detail}", 500, int((time.time() - start) * 1000))

    except Exception as e:
        return err(f"Search failed (REST): {e}", 500, int((time.time() - start) * 1000))


    results = []
    for r_ in rows or []:
        results.append({
            "course_id": r_.get("course_id"),
            "title": r_.get("title"),
            "score": 1.0,
            "reasons": [],
            "metadata": {"description": r_.get("description")},
        })


    took_ms = int((time.time() - start) * 1000)
    return ok({"results": results}, status=200, took_ms=took_ms)

# --- Global error safety net (no stack traces to clients) ---
@app.errorhandler(Exception)
def handle_unexpected(e):
    # Log the real error to console during dev
    app.logger.exception(e)
    return err("Internal server error", status=500)


def parse_json_safely(text: str):
    """
    Parse a JSON array from model output. Strips code fences and, if needed,
    extracts the first [...] block. Returns [] on failure.
    """
    if not isinstance(text, str):
        return []
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", t)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    print("⚠️ Model returned invalid JSON; using empty list.")
    return []

@app.route("/recommend", methods=["POST"])
def recommend():
    start = time.time()

    # 1) Validate JSON
   # Parse JSON
    try:
        body = request.get_json(force=True, silent=False) or {}
    except Exception:
        return err("Request body must be valid JSON", 400, int((time.time()-start)*1000))

    # Accept either "q" or "query"
    user_q = (body.get("q") or body.get("query") or "").strip()

    # Accept either "courses" (list of IDs) OR "results" (list of objects with course_id)
    courses = body.get("courses")
    results = body.get("results")

    course_ids = []
    if isinstance(courses, list) and all(isinstance(x, str) for x in courses):
        course_ids = courses
    elif isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and "course_id" in item and isinstance(item["course_id"], str):
                course_ids.append(item["course_id"])


    try:
        top_k = int(body.get("top_k", 5))
    except Exception:
        top_k = 5
    top_k = max(1, min(top_k, 25))  # keep between 1–25

    # Validate
    if not user_q:
        return err("Missing or invalid 'q'/'query'", 400, int((time.time()-start)*1000))
    if not course_ids:
        return err("Missing or invalid 'courses' or 'results' (need course IDs)", 400, int((time.time()-start)*1000))

    # 3) Normalize candidates (only keep the fields we need)
    candidates = []
    seen_ids = set()
    for item in results:
        cid = (item or {}).get("course_id")
        title = (item or {}).get("title")
        if not cid or not title or cid in seen_ids:
            continue
        seen_ids.add(cid)
        candidates.append({
            "course_id": cid,
            "title": title,
            "metadata": (item or {}).get("metadata", {})  # instructor/credits/etc.
        })

    # 4) Early return on empty candidates (contract says 200 with empty recommendations)
    if not candidates:
        took_ms = int((time.time() - start) * 1000)
        return ok({"recommendations": []}, status=200, took_ms=took_ms)







    # 0) Early return if no candidates
    if not candidates:
        took_ms = int((time.time() - start) * 1000)
        return ok({"recommendations": []}, status=200, took_ms=took_ms)

    # 1) Cap and slim candidates for token control
    allowed_ids = []
    slim = []
    for c in candidates[:10]:  # cap to 10
        cid = c.get("course_id")
        title = c.get("title")
        md = c.get("metadata") or {}
        if cid and title:
            allowed_ids.append(cid)
            slim.append({
                "course_id": cid,
                "title": title,
                # keep only small, useful bits
                # "instructor": md.get("instructor"),
                # "credits": md.get("credits"),
                # add brief/description here if you have a short one
            })

    candidates_json = json.dumps(slim, ensure_ascii=False)

    system_prompt = (
        "You recommend MBA courses ONLY from the provided candidates.\n"
        "Return STRICT JSON: an array of objects with keys: "
        "course_id (string), rationale (<=2 sentences), confidence (0.0–1.0).\n"
        "NEVER invent a course_id not in candidates. If unsure, return []."
    )

    user_prompt = (
        f"query: {user_q}\n"
        f"top_k: {top_k}\n"
        f"CANDIDATES(JSON): {candidates_json}\n\n"
        "Return ONLY JSON. No prose."
    )

    # 2) Call the model
    try:
        response = client.chat.completions.create(
        model="gpt-4o-mini",  # or another chat-capable model you have access to
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        top_p=1.0,
        max_tokens=500,
    )
        raw = response.choices[0].message.content if response and response.choices else "[]"
    except Exception:
        try:
            app.logger.exception("OpenAI call failed")
        except Exception:
            pass
        raw = "[]"


    # 3) Parse + enforce whitelist + cap to top_k
    recs = parse_json_safely(raw)
    allowed_set = set(allowed_ids)
    filtered = []
    for r in (recs if isinstance(recs, list) else []):
        cid = (r or {}).get("course_id")
        rationale = (r or {}).get("rationale")
        conf = (r or {}).get("confidence", 0.6)
        if cid in allowed_set and isinstance(rationale, str) and rationale.strip():
            try:
                conf = float(conf)
            except Exception:
                conf = 0.6
            filtered.append({
                "course_id": cid,
                "rationale": rationale.strip()[:400],  # keep it tight
                "confidence": max(0.0, min(1.0, conf)),
            })
        if len(filtered) >= top_k:
            break

    recommendations = filtered

    # 4) Return
    took_ms = int((time.time() - start) * 1000)
    return ok({"recommendations": recommendations}, status=200, took_ms=took_ms)



@app.route("/__routes", methods=["GET"])
def __routes():
    # Return plain text so we avoid JSON issues
    lines = []
    for r in app.url_map.iter_rules():
        methods = ",".join(sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"}))
        lines.append(f"{r.rule}  [{methods}]  -> {r.endpoint}")
    return "\n".join(sorted(lines)), 200, {"Content-Type": "text/plain; charset=utf-8"}




# --- Run the app ---
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
