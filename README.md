<div align="center">
  <img src="Phase3_Dashboard.png" alt="AI Startup Idea Validator Dashboard" width="800"/>
  <h1>🚀 AI Startup Idea Validator</h1>
  <p><strong>A full-stack, AI-powered orchestrator to validate and analyze startup ideas in real-time.</strong></p>
</div>

---

## 💡 What is this?
The **AI Startup Idea Validator** is a high-performance system designed to take a raw startup idea, analyze its potential using cutting-edge Generative AI (NVIDIA NIM APIs), and stream the analyzed results back to a visually stunning dashboard in real-time. 

It breaks down the validation process into three distinct, concurrent AI modules:
1. 📈 **Market Analysis**: Defines the target audience, estimates market size (TAM/SAM/SOM), and identifies growth trends.
2. ⚔️ **Competitor Research**: Discovers direct and indirect competitors, highlighting their strengths and weaknesses.
3. 🎯 **Viability Scoring**: Generates an overall viability score alongside a radar chart of strengths (Technical, Market, Financial, Team, Timing).

---

## 🏗️ Architecture & Tech Stack

This project is built using modern, fast, and scalable technologies designed to handle concurrent processing safely:

*   **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
*   **AI Integration**: NVIDIA NIM APIs (`meta/llama-3.3-70b-instruct`) with built-in retry mechanisms and fallback models (`mistralai/mistral-7b-instruct-v0.3`).
*   **Database**: PostgreSQL 16 (via `asyncpg` and SQLAlchemy 2.0+ native async ORM) for persisting validation history.
*   **Message Broker**: Redis 7 for queuing jobs (Redis Streams) and consumer group logic.
*   **Real-time Streaming**: Server-Sent Events (SSE) via `sse-starlette` to stream real-time JSON payloads to the client without polling.
*   **Frontend UI**: Single-file dark-themed Dashboard (`vanilla HTML/CSS/JS`), utilizing Chart.js for data visualization and CSS Grid for layout.
*   **Containerization**: Fully Dockerized using `docker-compose` spanning `app`, `redis`, and `postgres` services.

### 🔄 The Validation Workflow
1. **User Input** → Submits an idea via the frontend dashboard.
2. **REST API** (`POST /validate`) → Creates a UUID job, logs a `queued` status in PostgreSQL, and enqueues the job into a Redis stream (`validator:jobs`).
3. **Orchestrator Task** (`background task`) → Uses a free-tier safe `asyncio.Semaphore(1)` to process jobs sequentially. 
4. **Concurrent LLM Calls** → Dispatches 3 parallel async API calls (`gather()`) to Market, Competitor, and Viability modules.
5. **Real-time Updates** → Publishes the outcome backward via Redis pub/sub.
6. **SSE Feed** (`GET /stream/{job_id}`) → Listens to the Redis result stream and pipes JSON chunks directly to the web client.

---

## 🚀 Getting Started

### Prerequisites
* [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
* An NVIDIA API Key for the NIM endpoints.

### 1. Environment Variables
Create a `.env` file in the root directory (you can copy `.env.example`):
```env
# Logging Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=DEBUG

# NVIDIA NIM API (Required)
NVIDIA_API_KEY=nvapi-your_key_here

# PostgreSQL Database Configuration
DATABASE_URL=postgresql+asyncpg://myapp:myapp@postgres:5432/myapp

# Redis Configuration
REDIS_URL=redis://redis:6379/0
```

### 2. Run the Application
Start up the entire stack seamlessly with Docker Compose:
```bash
docker-compose up --build -d
```
*   The `app` service depends on the defined health checks of both `redis` and `postgres`, ensuring smooth autonomous orchestration on load.

### 3. Access the Dashboard
Navigate to `http://localhost:8000` in your web browser. 

You should be greeted by the dark-themed UI. Type a startup idea (e.g., "AI-powered CRM for local bakeries") and hit **Validate Idea**.

---

## 📂 Project Structure

```bash
.
├── docker-compose.yml       # Composes App + Redis + PostgreSQL
├── Dockerfile               # Python dependency and app packaging
├── requirements.txt         # Dependencies (FastAPI, Redis, Asyncpg, etc.)
├── .env.example             # Environment scaffolding
├── static/
│   └── dashboard.html       # The single-SPA UI with vanilla JS & Chart.js
└── src/
    ├── __init__.py
    ├── main.py              # FastAPI Routes & Lifespan Hooks
    ├── config.py            # Pydantic Settings Manager
    ├── models.py            # SQLAlchemy ORM schemas & Pydantic DTOs
    ├── db.py                # Async PostgreSQL CRUD operations
    ├── redis_client.py      # Redis connections, streams, and consumer groups
    ├── orchestrator.py      # Background worker handling module fan-out
    ├── nvidia.py            # NVIDIA API integration with retry & fallback
    └── modules/
        ├── market.py        # Instruct LLM to analyze TAM/SAM/SOM
        ├── competitors.py   # Instruct LLM to generate competitor matrices
        └── viability.py     # Instruct LLM to construct radar chart metrics
```

---

## 🧪 Testing
The repository includes an end-to-end test script `e2e_test.py` to assert the stream logic and queue systems:

```bash
docker-compose exec app python e2e_test.py
```

---

## 🛡️ License
> Proprietary / Closed Source

This project embodies modern best-practices for LLM application development, managing backpressure with robust queueing, handling rate limits elegantly, and delivering a smooth, snappy user experience via an EventSource-driven stream.
