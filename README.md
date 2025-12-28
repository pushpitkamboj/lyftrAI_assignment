# LyftrAI Backend Assignment

A webhook ingestion service built with FastAPI that receives, validates, and stores SMS messages with HMAC signature verification.

---

## 📚 Technologies Used

| Category | Technology |
|----------|------------|
| **Language** | Python 3.11 |
| **Framework** | FastAPI |
| **Validation** | Pydantic v2 |
| **Database** | SQLite (via SQLModel) |
| **ORM** | SQLModel (SQLAlchemy wrapper) |
| **Container** | Docker & Docker Compose |
| **Testing** | pytest |

---

## 🚀 Setup & Installation

### Prerequisites
- Docker & Docker Compose installed
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/pushpitkamboj/lyftrAI_assignment.git
cd lyftrAI_assignment

# Set environment variables
export WEBHOOK_SECRET="your-secret-key"
export DATABASE_URL="sqlite:////data/app.db"

# Start the application
make up
```

That's it! The API will be running at `http://localhost:8000` 🎉

### 🛠️ Setup Used

> **VSCode + GitHub Copilot + Occasional Prompts**

<details>
<summary><b>Prompt for Containerizing the App</b></summary>

```
● Runs via Docker Compose using SQLite for storage.
DB: SQLite only; DB file must live under a Docker volume (e.g. /data/app.db)

understand the code and help me create 3 files
dockerfile
docker-compose.yml
makefile

Makefile targets:
● make up → docker compose up -d --build
● make down → docker compose down -v
● make logs → docker compose logs -f api
● make test → run your tests

understand the code #file:app and write the files
```

</details>

<details>
<summary><b>Prompt for README File</b></summary>

```
create a readme file which is divided in sections
technologies used -
language = python
validation = pydantic
container = docker
testing = pytest
framework = fastapi
etc

then complete setup workflow
git clone lyftrAI_assignment
cd
then run make up (it will do things for u :)
then run endpoints
GET
POST
whatever 4 endpoints i have ...
u can also see the logs by running make logs if u want to...

and then explain design decisions
1. focus on explaining implementation of HMAC verification in webhook
2. how pagination works (focus of /messages route functionality and telling the validation things and etc)
3. explaining logging style in app, running tests with make test

and then at last write contributing guidelines, write testcases etc basic stuff
```

</details>

### Available Make Commands

| Command | Description |
|---------|-------------|
| `make up` | Build and start containers in detached mode |
| `make down` | Stop containers and remove volumes |
| `make logs` | Stream logs from the API container (Ctrl+C to exit) |
| `make test` | Run pytest inside the container |

---

## 📡 API Endpoints

### Health Checks

#### `GET /health/live`
Liveness probe - checks if the service is running.

```bash
curl http://localhost:8000/health/live
```

**Response:** `200 OK` - "live route working fine"

---

#### `GET /health/ready`
Readiness probe - checks if the service is ready to accept traffic (WEBHOOK_SECRET set + DB accessible).

```bash
curl http://localhost:8000/health/ready
```

**Response:** 
- `200 OK` - "ready route working fine"
- `503 Service Unavailable` - if not ready

---

### Webhook

#### `POST /webhook`
Receives and stores incoming SMS messages with HMAC signature verification.

```bash
# Generate HMAC signature
BODY='{"message_id":"msg-001","from":"+1234567890","to":"+0987654321","ts":"2025-12-28T10:00:00Z","text":"Hello!"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')

# Send request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$BODY"
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_id` | string | Yes | Unique message identifier |
| `from` | string | Yes | Sender phone (E.164 format: `+<digits>`) |
| `to` | string | Yes | Recipient phone (E.164 format) |
| `ts` | string | Yes | ISO-8601 UTC timestamp ending with `Z` |
| `text` | string | No | Message content (max 4096 chars) |

**Response:** `200 OK` - `{"status": "ok"}`

**Errors:**
- `401 Unauthorized` - Invalid/missing signature
- `422 Unprocessable Entity` - Validation error

---

### Messages

#### `GET /messages`
Retrieve stored messages with pagination and filtering.

```bash
# Basic request
curl http://localhost:8000/messages

# With pagination
curl "http://localhost:8000/messages?limit=10&offset=0"

# Filter by sender
curl "http://localhost:8000/messages?from=%2B1234567890"

# Filter by timestamp
curl "http://localhost:8000/messages?since=2025-12-01T00:00:00Z"

# Search by text
curl "http://localhost:8000/messages?q=hello"
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Results per page (1-100) |
| `offset` | int | 0 | Number of records to skip |
| `from` | string | - | Filter by sender phone |
| `since` | string | - | Filter messages after timestamp |
| `q` | string | - | Search text content (case-insensitive) |

**Response:**
```json
{
  "data": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

---

### Statistics

#### `GET /stats`
Get aggregated statistics about stored messages.

```bash
curl http://localhost:8000/stats
```

**Response:**
```json
{
  "total_messages": 150,
  "senders_count": 25,
  "messages_per_sender": [
    {"from": "+1234567890", "count": 15},
    ...
  ],
  "first_message_ts": "2025-12-01T08:00:00Z",
  "last_message_ts": "2025-12-28T15:30:00Z"
}
```

---

## 🏗️ Design Decisions

### 1. HMAC Signature Verification

The webhook endpoint implements HMAC-SHA256 signature verification to ensure message authenticity and integrity.

**How it works:**

```python
# 1. Read raw request body
body_bytes = await request.body()

# 2. Compute expected signature using shared secret
expected_signature = hmac.new(
    key=os.getenv("WEBHOOK_SECRET").encode(),
    msg=body_bytes,
    digestmod=hashlib.sha256 
).hexdigest()

# 3. Compare with provided signature (timing-attack safe)
if not hmac.compare_digest(expected_signature, x_signature):
    raise HTTPException(status_code=401, detail="invalid_signature")
```

**Key Points:**
- Uses `hmac.compare_digest()` for constant-time comparison (prevents timing attacks)
- Signature is computed over raw bytes (not parsed JSON) to catch any tampering
- Secret is loaded from environment variable (never hardcoded)
- Missing or invalid signatures return `401 Unauthorized`

---

### 2. Pagination & Filtering (`/messages`)

The messages endpoint provides flexible querying with offset-based pagination.

**Pagination:**
- `limit` - Controls page size (default: 50, max: 100)
- `offset` - Skip N records for pagination
- Response includes `total` count for calculating pages

**Filtering Options:**
- `from` - Exact match on sender phone number
- `since` - Messages with timestamp >= value
- `q` - Case-insensitive text search using SQL `ILIKE`

**Validation:**
- Phone numbers must be E.164 format (`+` followed by digits)
- Timestamps must be valid ISO-8601 UTC format
- `limit` bounded between 1-100 to prevent abuse
- `offset` must be non-negative

**Ordering:**
- Results sorted by `ts` ascending, then `message_id` ascending
- Ensures consistent pagination results

---

### 3. Structured JSON Logging

All requests are logged in structured JSON format via middleware for easy parsing and analysis.

**Log Format:**
```json
{
  "ts": "2025-12-28T10:30:00.000000+00:00",
  "level": "INFO",
  "request_id": "uuid-here",
  "method": "POST",
  "path": "/webhook",
  "status": 200,
  "latency_ms": 12.34,
  "result": "created",
  "dup": false,
  "message_id": "msg-001"
}
```

**Features:**
- **Request ID**: Unique UUID per request for tracing
- **Latency tracking**: Response time in milliseconds
- **Log level**: INFO for success (< 400), ERROR for failures
- **Contextual data**: Webhook-specific fields (result, dup, message_id)

**View Logs:**
```bash
make logs
```

---

### 4. Running Tests

Tests are run inside the Docker container using pytest:

```bash
make test
```

This executes `docker compose exec api pytest tests/ -v` which:
- Runs pytest with verbose output
- Uses the same environment as the running application
- Tests against the SQLite database

---

## 🤝 Contributing

### Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `make test`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

### Writing Tests

Tests are located in the `tests/` directory. Use pytest fixtures and FastAPI's `TestClient`:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200

def test_webhook_invalid_signature():
    response = client.post(
        "/webhook",
        json={"message_id": "1", "from": "+123", "to": "+456", "ts": "2025-01-01T00:00:00Z"},
        headers={"X-Signature": "invalid"}
    )
    assert response.status_code == 401
```
