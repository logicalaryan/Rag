# Production Agentic RAG System

Enterprise microservice architecture for autonomous Retrieval-Augmented Generation.

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

```bash
docker-compose up --build
```
