import os
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from services.supabase_client import get_supabase, get_table_name, search_courses_by_title


# --- App & Config ---
load_dotenv()  # reads .env in development
app = Flask(__name__)
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
def search():
    start = time.time()

    # 1) Validate request
    if not request.is_json:
        return err("Request body must be JSON", status=400, took_ms=int((time.time()-start)*1000))

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    k = body.get("k", 10)

    if not query:
        return err("Missing or invalid 'query' field", status=400, took_ms=int((time.time()-start)*1000))
    if not isinstance(k, int) or k < 1 or k > 25:
        return err("Invalid 'k' value (must be 1–25)", status=422, took_ms=int((time.time()-start)*1000))

    # 2) Query Supabase
    sb = get_supabase()
    table = get_table_name()
    rows = search_courses_by_title(sb, table, query, k)

    # 3) Shape response to your contract
    results = []
    for r in rows:
        results.append({
            "course_id": r.get("course_id"),
            "title": r.get("title"),
            "score": 1.0,           # placeholder; we’ll add better scoring later
            "reasons": [],          # placeholder; we’ll add “why it matched” later
            "metadata": {
                "instructor": r.get("instructor"),
                "credits": r.get("credits"),
            }
        })

    took_ms = int((time.time() - start) * 1000)
    return ok({"results": results}, status=200, took_ms=took_ms)

# --- Global error safety net (no stack traces to clients) ---
@app.errorhandler(Exception)
def handle_unexpected(e):
    # Log the real error to console during dev
    app.logger.exception(e)
    return err("Internal server error", status=500)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
