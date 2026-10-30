# Production Agentic RAG System

Enterprise microservice architecture for autonomous Retrieval-Augmented Generation.

## Tech Stack

- **Language:** Python 3.11
- **API:** FastAPI, Uvicorn, and Server-Sent Events with `sse-starlette`
- **AI:** Google Gemini through the Google GenAI SDK
- **Retrieval:** ChromaDB, BM25 with `rank-bm25`, and FlashRank
- **Document processing:** `pypdf`, `pdfplumber`, BeautifulSoup, and `python-multipart`
- **Data and messaging:** PostgreSQL with SQLAlchemy and asyncpg, Redis, and Celery
- **Observability:** OpenTelemetry and Prometheus
- **Testing:** pytest, pytest-asyncio, and HTTPX
- **Deployment:** Docker and Docker Compose

## Architecture Structure

```
production/
├── app/
│   ├── main.py                     # FastAPI entrypoint & lifespan
│   ├── config.py                   # Pydantic BaseSettings
│   │
│   ├── api/                        # REST & SSE API Gateway
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── chat.py         # SSE streaming chat endpoint
│   │   │   │   ├── documents.py    # Document upload & ingestion triggers
│   │   │   │   └── health.py       # Liveness / readiness probes
│   │   │   └── routers.py          # API v1 aggregator
│   │   └── middlewares/
│   │       ├── auth.py             # JWT / API Key security
│   │       ├── rate_limiter.py     # Redis token bucket
│   │       └── guardrails.py       # Prompt injection & PII filtering
│   │
│   ├── core/                       # Multi-Agent Engine
│   │   ├── agents/
│   │   │   ├── router.py           # Intent router & query rewriter
│   │   │   ├── synthesizer.py      # Response synthesis with citations
│   │   │   ├── critic.py           # Self-reflection groundedness checker
│   │   │   └── orchestrator.py     # Async pipeline state machine
│   │   ├── tools/
│   │   │   ├── base.py             # Abstract tool interface
│   │   │   ├── local_retriever.py  # Hybrid Dense + BM25 + FlashRank
│   │   │   └── web_search.py       # Async DuckDuckGo search & scraping
│   │   ├── indexing/
│   │   │   ├── parsers.py          # Multi-format extractors (PDF/TXT/MD)
│   │   │   ├── chunkers.py         # Structure-aware recursive chunker
│   │   │   └── embeddings.py       # Batch embedding client with backoff
│   │   └── memory/
│   │       ├── session_store.py    # PostgreSQL multi-turn chat persistence
│   │       └── semantic_cache.py   # Redis semantic vector cache
│   │
│   ├── db/                         # Persistence & Database Adapters
│   │   ├── postgres.py             # SQLAlchemy async engine
│   │   ├── vector_store.py         # Qdrant / ChromaDB Server adapter
│   │   └── models.py               # ORM & Pydantic schemas
│   │
│   ├── workers/                    # Background Workers
│   │   └── ingestion_worker.py     # Async Celery/Redis document ingestion
│   │
│   └── telemetry/                  # Observability
│       ├── tracing.py              # OpenTelemetry / Langfuse instrumentation
│       └── metrics.py              # Prometheus latency & token metrics
│
├── tests/                          # Automated Tests
│   ├── test_agents.py
│   ├── test_retriever.py
│   └── test_api.py
│
├── Dockerfile                      # Production container image
├── docker-compose.yml              # Local multi-service cluster
├── requirements.txt                # Production dependencies
└── README.md
```

## Quick Start (Docker)

### 1. Clone the repository

```bash
git clone https://github.com/logicalaryan/Rag.git
cd Rag
```

### 2. Configure the Gemini API key

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
```

### 3. Build and run the services

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`.

To stop the services:

```bash
docker compose down
```

## Run Locally

Python 3.11 or later is recommended.

```bash
git clone https://github.com/logicalaryan/Rag.git
cd Rag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=your_gemini_api_key
uvicorn app.main:app --reload
```

The local API is available at `http://localhost:8000`.
