# Production Agentic RAG — Frontend Client

A high-performance, minimalist black-and-white React SPA for the Production Agentic RAG pipeline.

## Features
- **Monochrome Theme:** Pure black background (`#000000`), crisp typography (Inter & JetBrains Mono), and subtle high-contrast borders.
- **Server-Sent Events (SSE) Streaming:** Real-time token streaming with live thinking indicators and source citations.
- **Document Management:** Knowledge base uploader for PDF, Markdown, and TXT files.
- **Resilient Fallback:** Simulated demonstration mode when FastAPI backend is offline.

## Quick Start

```bash
cd production/frontend
npm install
npm run dev
```

The app will run at `http://localhost:3000` and automatically proxy `/api` requests to `http://localhost:8000`.
