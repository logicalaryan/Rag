## 🏗️ System Architecture

This project follows a modular, multi-agent RAG architecture built with **FastAPI, React, ChromaDB, BM25, PostgreSQL, and Gemini**. It separates API handling, retrieval, agent orchestration, document indexing, persistence, and frontend responsibilities.

### 1. Architecture Overview

```mermaid
flowchart TB
    U["User"] --> FE["React Frontend<br/>Vite"]
    FE --> API["FastAPI Application<br/>main.py"]

    API --> GW["API Gateway<br/>Routers & API Key Dependency"]

    GW --> CHAT["Chat Endpoint<br/>SSE Streaming"]
    GW --> DOC["Document Endpoints<br/>Upload, Delete & Index Sync"]
    GW --> HEALTH["Health Endpoints<br/>Liveness & Readiness"]

    CHAT --> ORCH["Async Agent Orchestrator<br/>Pipeline State Machine"]

    ORCH --> ROUTER["Router Agent<br/>Intent Classification & Query Reformulation"]

    ROUTER --> LOCAL["Hybrid Local Retrieval"]
    ROUTER --> WEB["Web Search Tool"]

    subgraph RETRIEVAL["Retrieval Layer"]
        LOCAL --> DENSE["Dense Retrieval<br/>ChromaDB"]
        LOCAL --> SPARSE["Sparse Retrieval<br/>BM25"]
        DENSE --> RERANK["FlashRank Reranking"]
        SPARSE --> RERANK
    end

    WEB --> PRIVACY["Privacy Redaction"]
    PRIVACY --> GEMINI["Gemini Google Search Grounding"]

    RERANK --> SYN["Synthesizer Agent<br/>Grounded Answers & Citations"]
    GEMINI --> SYN

    SYN --> CRITIC["Critic Agent<br/>Factuality & Hallucination Evaluation"]
    CRITIC --> ORCH

    ORCH --> STREAM["SSE Response Stream"]
    STREAM --> FE

    subgraph SHARED["Shared Infrastructure"]
        LLM["LLM Gateway<br/>RPM Throttling, Deduplication & Cache"]
        PRIV["Privacy Module<br/>PII, Secret & Log Sanitization"]
    end

    ROUTER -.-> LLM
    SYN -.-> LLM
    CRITIC -.-> LLM
    ORCH -.-> PRIV

    subgraph DATA["Persistence & Indexing Layer"]
        CHUNK["Structure-Aware Chunking<br/>Semantic Chunking"]
        VECTOR["Vector Store<br/>ChromaDB / pgvector"]
        MODELS["Pydantic Models<br/>Metadata Contracts"]
        POSTGRES["Neon PostgreSQL<br/>Async Connection Pool"]
    end

    DOC --> CHUNK
    CHUNK --> VECTOR
    VECTOR --> DENSE
    ORCH --> POSTGRES
    DOC --> MODELS
    VECTOR --> MODELS

    subgraph DEPLOY["Deployment"]
        DOCKER["Dockerfile"]
        COMPOSE["Docker Compose"]
        REQS["Production Requirements"]
    end
```

### 2. Project Directory Structure

```text
production/
│
├── app/
│   │
│   ├── main.py
│   │   # FastAPI entrypoint, application lifespan,
│   │   # CORS configuration and SSE streaming
│   │
│   ├── config.py
│   │   # Centralized configuration using Pydantic BaseSettings
│   │
│   ├── api/
│   │   └── v1/
│   │       │
│   │       ├── endpoints/
│   │       │   ├── chat.py
│   │       │   │   # SSE-based chat streaming endpoint
│   │       │   │
│   │       │   ├── documents.py
│   │       │   │   # Document upload, admin-gated deletion
│   │       │   │   # and index synchronization
│   │       │   │
│   │       │   └── health.py
│   │       │       # Container readiness and liveness probes
│   │       │
│   │       └── routers.py
│   │           # API route aggregation and API key dependency
│   │
│   ├── core/
│   │   │
│   │   ├── agents/
│   │   │   ├── router.py
│   │   │   │   # Intent classification and query reformulation
│   │   │   │
│   │   │   ├── synthesizer.py
│   │   │   │   # Grounded response generation and citation tracking
│   │   │   │
│   │   │   ├── critic.py
│   │   │   │   # Factuality evaluation and hallucination detection
│   │   │   │
│   │   │   └── orchestrator.py
│   │   │       # Async pipeline state machine and concurrent dispatcher
│   │   │
│   │   ├── tools/
│   │   │   ├── local_retriever.py
│   │   │   │   # Hybrid dense and sparse retrieval
│   │   │   │   # ChromaDB + BM25 + FlashRank
│   │   │   │
│   │   │   └── web_search.py
│   │   │       # Gemini Google Search Grounding
│   │   │       # with privacy redaction
│   │   │
│   │   ├── indexing/
│   │   │   └── chunkers.py
│   │   │       # Structure-aware document parsing
│   │   │       # and semantic chunking
│   │   │
│   │   ├── llm_gateway.py
│   │   │   # RPM throttling, single-flight deduplication
│   │   │   # and in-memory caching
│   │   │
│   │   └── privacy.py
│   │       # PII and secret redaction, log sanitization
│   │
│   └── db/
│       ├── models.py
│       │   # Pydantic schemas and metadata contracts
│       │
│       ├── postgres.py
│       │   # Neon PostgreSQL async connection pool
│       │   # for conversation turn history
│       │
│       └── vector_store.py
│           # Dense vector collection interface
│           # supporting ChromaDB / pgvector
│
├── frontend/
│   └── src/
│       # Vite + React real-time client
│       # SSE reader, dynamic citation badges
│       # and document manager
│
├── Dockerfile
│   # Production container image
│
├── docker-compose.yml
│   # Local multi-container orchestration
│
└── requirements.txt
    # Minimized production dependencies
```

### 3. Request Lifecycle

1. **User Query:** The React frontend sends a chat request to the FastAPI backend.
2. **API Gateway:** The request passes through API routing and API key validation.
3. **Agent Orchestration:** The orchestrator manages the asynchronous RAG pipeline.
4. **Query Routing:** The router agent classifies the user's intent and reformulates the query when required.
5. **Retrieval:** The system retrieves relevant context through hybrid local retrieval (ChromaDB + BM25 + FlashRank) and/or web search.
6. **Response Synthesis:** The synthesizer generates a grounded answer and tracks its citations.
7. **Response Evaluation:** The critic evaluates factuality and potential hallucinations.
8. **Streaming:** The orchestrator returns the response to the frontend through Server-Sent Events (SSE).

### 4. Document Indexing Lifecycle

```mermaid
flowchart LR
    A["Document Upload"] --> B["Document Endpoint"]
    B --> C["Structure-Aware Parsing"]
    C --> D["Semantic Chunking"]
    D --> E["Embedding Generation"]
    E --> F["Vector Store"]
    F --> G["Dense Retrieval"]

    F --> H["Index Synchronization"]
```

### 5. Infrastructure and Supporting Components

| Component | Responsibility |
|---|---|
| FastAPI | REST API and SSE communication |
| React + Vite | Real-time frontend interface |
| ChromaDB | Dense vector storage and retrieval |
| BM25 | Sparse keyword-based retrieval |
| FlashRank | Retrieval result reranking |
| Gemini | LLM inference and Google Search Grounding |
| Neon PostgreSQL | Persistent conversation turn history |
| Pydantic | Configuration, validation and metadata schemas |
| Docker | Containerization and local orchestration |

