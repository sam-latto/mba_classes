# 🎓 Ross AI Course Recommender (Backend MVP)

An AI-powered Flask API that recommends University of Michigan Ross MBA courses based on user queries.  
Built as an MVP to explore **backend development**, **Supabase integration**, and **OpenAI reasoning** for educational use.

---

## 🧠 Overview

**Goal:** Help MBA students discover the most relevant courses for their professional goals — and explain *why* each course fits.  
The backend provides three main endpoints:

| Endpoint | Description | Status |
|-----------|--------------|--------|
| `/health` | Sanity check route | ✅ Working |
| `/search` | Queries Supabase for relevant courses | ✅ Working |
| `/recommend` | Uses OpenAI to explain “why these courses” | ✅ Working |

---

## ⚙️ Tech Stack

| Component | Purpose |
|------------|----------|
| **Flask** | API framework for routing |
| **Supabase** | Cloud database of course data |
| **OpenAI API** | Generates AI-written rationales |
| **python-dotenv** | Loads environment variables from `.env` |
| **Render / Railway** | Deployment platform for public hosting |

---

## 🧩 Setup and Local Run

### 1️⃣ Clone and Install

```bash
git clone https://github.com/<your-repo-name>.git
cd api
pip install -r requirements.txt
```

### 2️⃣ Add Environment Variables

Create a `.env` file inside `/api`:

```
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-anon-key>
OPENAI_API_KEY=<your-openai-api-key>
```

You can copy and rename the included `.env.example` file.

### 3️⃣ Run Locally

```bash
python app.py
```

If successful, your terminal will show:

```
* Running on http://127.0.0.1:5000
```

Test the server:
```
GET http://127.0.0.1:5000/health
```

**Expected:**
```json
{ "ok": true }
```

---

## 🔍 API Endpoints

### ✅ `GET /health`

Simple health check.

**Response**
```json
{ "ok": true }
```

---

### ✅ `POST /search`

Searches Supabase and returns the top-k relevant courses.

**Request**
```json
{
  "query": "product management",
  "k": 5
}
```

**Response**
```json
{
  "results": [
    {
      "course_id": "TO-567",
      "title": "Product Management Studio",
      "metadata": {
        "instructor": "Kim",
        "credits": 3
      }
    },
    {
      "course_id": "TO-620",
      "title": "Design Thinking",
      "metadata": {
        "instructor": "Patel",
        "credits": 3
      }
    }
  ],
  "took_ms": 310
}
```

---

### ✅ `POST /recommend`

Generates AI-written rationales explaining *why* courses fit a user’s query.  
This endpoint uses your `OPENAI_API_KEY` to call the Chat Completions API.

**Request**
```json
{
  "query": "product management",
  "results": [
    { "course_id": "TO-567", "title": "Product Management Studio" },
    { "course_id": "TO-620", "title": "Design Thinking" }
  ],
  "top_k": 2
}
```

**Response**
```json
{
  "recommendations": [
    {
      "course_id": "TO-567",
      "rationale": "Focuses on PM strategy and cross-functional execution.",
      "confidence": 0.86
    },
    {
      "course_id": "TO-620",
      "rationale": "Emphasizes creative problem-solving and user-centered design.",
      "confidence": 0.78
    }
  ],
  "took_ms": 1245
}
```

---

## 🧱 Project Structure

```
api/
├── app.py                      # Main Flask app
├── services/
│   ├── __init__.py
│   └── supabase_client.py      # Supabase connection logic
├── probe_supabase.py           # Local connection test utility
├── requirements.txt            # Dependencies
├── .env.example
└── README.md
```

---

## 🧪 Testing Locally (PowerShell)

```powershell
$body = @{
  query = "product management"
  results = @(
    @{ course_id="TO-567"; title="Product Management Studio"; metadata=@{ instructor="Kim"; credits=3 } },
    @{ course_id="TO-620"; title="Design Thinking"; metadata=@{ instructor="Patel"; credits=3 } }
  )
  top_k = 2
} | ConvertTo-Json -Depth 5

irm http://127.0.0.1:5000/recommend `
  -Method Post `
  -ContentType 'application/json' `
  -Body $body
```

---

## 📊 Logging & Debugging Tips

- Use `print()` or `app.logger.info()` inside `/recommend` to inspect:
  ```python
  print("✅ Final recommendations:", recommendations)
  ```
- Add timing for performance metrics:
  ```python
  took_ms = int((time.time() - start) * 1000)
  ```
- Common issues:
  - `OPENAI_API_KEY` not loaded → check `.env`
  - Model access error → use `"gpt-4o-mini"` or another chat-capable model
  - Empty recommendations → check `parse_json_safely()` and prompt format

---

## 🚀 Deployment Guide (Step 6)

Deploy your backend to **Render** or **Railway**.

### 1. Push to GitHub
Commit your latest code:
```bash
git add .
git commit -m "Initial working MVP backend"
git push origin main
```

### 2. Create a New Render Web Service
- Select your GitHub repo.
- Environment → Python 3.11+
- **Build Command:**  
  `pip install -r requirements.txt`
- **Start Command:**  
  `python app.py`
- Add Environment Variables:
  ```
  SUPABASE_URL
  SUPABASE_KEY
  OPENAI_API_KEY
  ```

### 3. Verify Deployment
Check:
```
https://<your-app-name>.onrender.com/health
→ { "ok": true }
```

Then test `/recommend` with your sample JSON payload.

---

## 🧭 Next Steps (Roadmap)

| Step | Goal | Deliverable |
|------|------|-------------|
| **Step 6** | Deploy backend to Render or Railway | ✅ Public API endpoint |
| **Step 7** | Connect your Figma front-end prototype via REST | Interactive demo |
| **Step 8** | Add logging, metrics, and documentation polish | Complete GitHub repo |
| **Step 9** | Optional: improve `/search` ranking with embeddings | Smarter recommendations |

---

## 🧰 Future Enhancements

- Add `/metrics` endpoint for internal analytics  
- Store recommendation history in Supabase  
- Integrate embeddings for semantic matching  
- Implement user feedback loop for ranking refinement  
- Build dashboard for API usage and performance

---

## 🧾 Example Response from Working Build

```json
{
  "recommendations": [
    {
      "course_id": "TO-567",
      "rationale": "This course focuses on the practical aspects of product management, making it suitable for those interested in the field.",
      "confidence": 1.0
    }
  ],
  "took_ms": 1364
}
```

---

## ✨ Author & Learning Goals

This project was developed as part of an MBA initiative to explore:
- Backend API development (Flask)
- Integrating Supabase databases
- Calling OpenAI APIs for reasoning
- Full MVP deployment workflows
- Connecting AI results to front-end prototypes in Figma

**Created by:** Sam Latto  
**University of Michigan – Ross School of Business**
