production/
├── app/
│   ├── main.py                     # FastAPI entrypoint, lifespan, CORS, and SSE streaming
│   ├── config.py                   # Pydantic BaseSettings (centralized configuration)
│   ├── api/v1/                     # REST & SSE API Gateway
│   │   ├── endpoints/
│   │   │   ├── chat.py             # Server-Sent Events (SSE) chat stream
│   │   │   ├── documents.py        # File upload, deletion (Admin-gated), and index sync
│   │   │   └── health.py           # Container readiness & liveness probes
│   │   └── routers.py              # Aggregated routing & API key dependency
│   ├── core/                       # Multi-Agent RAG Engine
│   │   ├── agents/
│   │   │   ├── router.py           # Intent classification & query reformulation
│   │   │   ├── synthesizer.py      # Grounded response synthesis with strict citation tracking
│   │   │   ├── critic.py           # Self-reflective factuality & hallucination evaluator
│   │   │   └── orchestrator.py     # Async pipeline state machine & concurrent dispatcher
│   │   ├── tools/
│   │   │   ├── local_retriever.py  # Hybrid Dense (ChromaDB) + Sparse (BM25) + FlashRank
│   │   │   └── web_search.py       # Live Gemini Google Search Grounding with privacy redaction
│   │   ├── indexing/
│   │   │   └── chunkers.py         # Structure-aware document parser and semantic chunking
│   │   ├── llm_gateway.py          # RPM throttle, single-flight deduplication & in-memory cache
│   │   └── privacy.py              # PII, secret redaction, and log sanitization
│   └── db/                         # Persistence Layer
│       ├── models.py               # Pydantic schemas and metadata contracts
│       ├── postgres.py             # Neon Postgres async connection pool for turn history
│       └── vector_store.py         # Dense vector collection interface (ChromaDB/pgvector)
├── frontend/                       # Vite + React Real-Time Client
│   └── src/                        # SSE reader, dynamic citation badges, document manager
├── Dockerfile                      # Production container image
├── docker-compose.yml              # Local orchestration cluster
└── requirements.txt                # Minimized production dependencies
