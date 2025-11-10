## POST /search — API Contract (Draft v1)

**Purpose:**  
Searches the course database and returns the most relevant matches based on the user’s query (e.g., “product management”). This endpoint connects the Figma front-end to the Flask backend.

---

### 🔹 Request

**Method:** `POST`  
**URL:** `/search`  
**Content-Type:** `application/json`

**Body Parameters:**
| Field | Type | Required | Description |
|--------|------|-----------|--------------|
| `query` | string | ✅ Yes | The user’s text query (e.g., “product management”). |
| `k` | integer | ❌ No | Number of results to return. Defaults to 10. Max 25. |
| `filters` | object | ❌ No | Optional filters (e.g., `{ "level": "MBA", "term": "W25" }`). |

**Example Request:**
```json
{
  "query": "product management",
  "k": 5,
  "filters": { "level": "MBA" }
}
