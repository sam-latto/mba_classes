import os
import time
from flask import Flask, request, jsonify  # <- include jsonify
import json
from openai import OpenAI
from flask_cors import CORS
from dotenv import load_dotenv
from flask import send_from_directory
import re
from api.services.supabase_client import get_supabase, get_table_name, search_courses_by_title
import requests



# --- App & Config ---
client = OpenAI()
load_dotenv()  # reads .env in development
app = Flask(__name__, static_folder="static", static_url_path="")
# Simple mapping: profession -> skills/keywords for search
PROFESSION_PROFILES = {
    "product manager": {
        "aliases": ["pm", "product management"],
        "skills": [
            "product strategy",
            "customer discovery",
            "roadmapping",
            "experimentation",
            "A/B testing",
            "agile",
            "user research",
            "data-driven decision making",
            "digital product",
            "innovation"
        ]
    }
    # We'll add more professions later
}

def normalize_profession_name(raw: str) -> str | None:
    """
    Map a user-provided profession string to one of our canonical keys
    (e.g., "pm" -> "product manager").
    """
    if not raw:
        return None
    s = raw.strip().lower()
    for name, profile in PROFESSION_PROFILES.items():
        if s == name:
            return name
        if s in profile.get("aliases", []):
            return name
    return None


def build_intent_from_profession(profession: str, extra_goal: str | None = None) -> str:
    """
    Turn a profession into a simple query string that FTS can handle.
    For now, keep it very close to what we already know works.
    """
    canonical = normalize_profession_name(profession)
    if not canonical:
        # If we don't recognize it, just fall back to the raw text
        base = profession.strip()
        if extra_goal:
            base += " " + extra_goal.strip()
        return base

    # For "product manager", we know "product management" works well with FTS
    if canonical == "product manager":
        base = "product management"
    else:
        base = canonical

    if extra_goal:
        base += " " + extra_goal.strip()

    return base



print("Launching app from:", __file__)
print("Routes at startup:", app.url_map)


# CORS(app, resources={r"/*": {"origins": "*"}})  # relax in dev; tighten later
# pip install flask-cors
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# --- Supabase config for FTS-based candidate retrieval ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_KEY")
)

SB_HDR = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
print("DEBUG SUPABASE_URL:", SUPABASE_URL)
print("DEBUG SUPABASE_KEY present:", bool(SUPABASE_KEY))


def retrieve_candidates_fts(intent: str, want: int):
    """
    Minimal FTS helper: call Supabase ft_search and just return [{course_id, title=course_id}]
    so we can see if Supabase is sending back anything at all.
    """
    print("DEBUG FTS: starting with intent =", repr(intent), "want =", want)
    print("DEBUG FTS: URL =", SUPABASE_URL, "KEY present =", bool(SUPABASE_KEY))

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("DEBUG FTS: missing SUPABASE_URL or SUPABASE_KEY, returning [].")
        return []

    want = max(int(want or 10), 1)

    # 1) Call ft_search RPC
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/ft_search",
            headers=SB_HDR,
            json={"q": intent, "match_count": want},
            timeout=10,
        )
        print("DEBUG FTS: ft_search status:", r.status_code)
        print("DEBUG FTS: ft_search raw body:", r.text[:500])
        r.raise_for_status()
        hits = r.json() or []
        print("DEBUG FTS: ft_search parsed hits:", hits)
    except Exception as e:
        print("DEBUG FTS: ERROR calling ft_search:", repr(e))
        return []

    ids = [h.get("course_id") for h in hits if h.get("course_id")]
    print("DEBUG FTS: extracted ids:", ids)

    if not ids:
        print("DEBUG FTS: no ids found in hits, returning [].")
        return []

    # For now, don't bother with a second query; just return ids as candidates
    candidates = [{"course_id": cid, "title": cid} for cid in ids]
    print("DEBUG FTS: final candidates:", candidates)
    return candidates




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

    # --- Parse & validate body ---
    try:
        body = request.get_json(force=True, silent=False) or {}
    except Exception:
        return err("Request body must be valid JSON", 400, int((time.time() - start) * 1000))
   
    # ---- Step 2: Extract profession + build intent if needed ----
    profession = (body.get("profession") or "").strip()
    goal = (body.get("goal") or "").strip()

    intent = (body.get("q") or body.get("query") or "").strip()

    # if no q/query provided, use profession-based intent
    if not intent and profession:
        intent = build_intent_from_profession(profession, goal)
   
    try:
        top_k = int(body.get("top_k", 5))
    except Exception:
        top_k = 5
    top_k = max(1, min(top_k, 25))  # clamp 1–25

    if not intent:
        return err(
        "Missing intent: provide 'q'/'query' or 'profession'",
        400,
        int((time.time() - start) * 1000),
    )


    raw_courses = body.get("courses")
    raw_results = body.get("results")

    # --- Normalize candidates from either 'results' or 'courses' ---
    candidates = []
    seen = set()

    # Prefer 'results' (objects with course_id + title)
    if isinstance(raw_results, list):
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            cid = (item.get("course_id") or "").strip()
            title = (item.get("title") or "").strip()
            if cid and title and cid not in seen:
                seen.add(cid)
                candidates.append({"course_id": cid, "title": title})

    # If only 'courses' (ids) were provided, make minimal candidates
    if isinstance(raw_courses, list):
        for cid in raw_courses:
            if isinstance(cid, str):
                cid = cid.strip()
                if cid and cid not in seen:
                    seen.add(cid)
                    candidates.append({"course_id": cid, "title": f"{cid} (title unknown)"})

    # If neither 'results' nor 'courses' provided anything,
    # fall back to full-text search over all courses using `intent`.
    if not candidates:
        try:
            candidates = retrieve_candidates_fts(intent, top_k)
        except Exception:
            app.logger.exception("FTS retrieval failed")
            candidates = []

    # Now log what happened and bail if still empty
    if not candidates:
        app.logger.info(f"FTS returned no candidates for intent={intent!r}")
        return ok({"recommendations": []}, 200, int((time.time() - start) * 1000))
    else:
        app.logger.info(f"FTS candidates for intent={intent!r}: {candidates}")


    # Contract: if still no candidates, return 200 with empty list
    if not candidates:
        return ok({"recommendations": []}, 200, int((time.time() - start) * 1000))


    # Token control: cap to 10 and slim fields
    candidates = candidates[:10]
    allowed_ids = [c["course_id"] for c in candidates]
    slim = [{"course_id": c["course_id"], "title": c["title"]} for c in candidates]

    # --- Build prompts ---
    system_prompt = (
        "You recommend MBA courses ONLY from the provided candidates.\n"
        "Return STRICT JSON with key 'recommendations': an array of objects with keys:\n"
        "course_id (string), rationale (<=2 sentences), confidence (0.0–1.0).\n"
        "NEVER invent a course_id not in candidates. If unsure, return []."
    )
    user_payload = {
        "intent": intent,
        "top_k": top_k,
        "candidates": slim,  # [{course_id, title}]
    }

    # --- Call OpenAI in JSON mode for reliable parsing ---
    try:
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            timeout=20,
            max_tokens=600,
        )
        content = (resp.choices[0].message.content or "").strip()
        obj = json.loads(content) if content else {}
        recs = obj.get("recommendations", [])
        if not isinstance(recs, list):
            recs = []
    except Exception:
        app.logger.exception("OpenAI call failed")
        recs = []

    # --- Validate, whitelist, and trim ---
    allowed = set(allowed_ids)
    cleaned = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        cid = (r.get("course_id") or "").strip()
        rationale = (r.get("rationale") or "").strip()
        if cid in allowed and rationale:
            try:
                conf = float(r.get("confidence", 0.6))
            except Exception:
                conf = 0.6
            cleaned.append({
                "course_id": cid,
                "rationale": rationale[:400],
                "confidence": max(0.0, min(1.0, conf)),
            })

    # Keep model order (already ranked) but enforce top_k
    recommendations = cleaned[:top_k]

    return ok({"recommendations": recommendations}, 200, int((time.time() - start) * 1000))




@app.route("/__routes", methods=["GET"])
def __routes():
    # Return plain text so we avoid JSON issues
    lines = []
    for r in app.url_map.iter_rules():
        methods = ",".join(sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"}))
        lines.append(f"{r.rule}  [{methods}]  -> {r.endpoint}")
    return "\n".join(sorted(lines)), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/")
def home():
    return app.send_static_file("index.html")


# --- Run the app ---
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
