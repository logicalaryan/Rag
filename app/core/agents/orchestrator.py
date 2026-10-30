import os
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from google import genai
from app.config import settings
from app.db.models import RetrievedChunk
from app.core.agents.router import RouterAgent
from app.core.agents.synthesizer import SynthesizerAgent
from app.core.agents.critic import CriticAgent
from app.core.tools.local_retriever import local_retriever
from app.core.tools.web_search import web_search_tool


class RAGOrchestrator:
    """
    Multi-Agent Asynchronous State Machine:
    1. Intent Routing & Query Rewriting
    2. Tool Execution (Local Hybrid Search / Web Search)
    3. Grounded Synthesis & Critic Loop
    4. SSE Event Emission
    """

    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY", "")

        self.client = genai.Client(api_key=api_key) if api_key else None
        self.router = RouterAgent(self.client) if self.client else None
        self.synthesizer = SynthesizerAgent(self.client) if self.client else None
        self.critic = CriticAgent(self.client) if self.client else None

    async def execute_stream(
        self, query: str, session_id: str, chat_history: str = ""
    ) -> AsyncGenerator[str, None]:
        if not self.client:
            yield f"data: {json.dumps({'type': 'token', 'content': 'Error: GEMINI_API_KEY is not configured on the backend.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 1. Routing
        yield f"data: {json.dumps({'type': 'thinking', 'content': 'Analyzing intent and optimizing search query...'})}\n\n"
        routing = await self.router.route(query, chat_history)
        search_query = routing.rewritten_query

        # 2. Tool Execution
        context_chunks: List[RetrievedChunk] = []
        if routing.intent in ["search_local", "both"]:
            yield f"data: {json.dumps({'type': 'thinking', 'content': f'Searching internal knowledge base for: \"{search_query}\"...'})}\n\n"
            local_chunks = await local_retriever.execute(search_query, top_k=settings.FINAL_TOP_K)
            context_chunks.extend(local_chunks)

        if routing.intent in ["search_web", "both"] or (not context_chunks and routing.intent != "direct_answer"):
            yield f"data: {json.dumps({'type': 'thinking', 'content': f'Consulting live web sources...'})}\n\n"
            web_chunks = await web_search_tool.execute(search_query, top_k=2)
            context_chunks.extend(web_chunks)

        # 3. Collect Citations
        citations = []
        for c in context_chunks:
            label = f"{c.source}" + (f":p{c.page}" if c.page else "")
            if label not in citations:
                citations.append(label)

        # 4. Draft -> Critic loop (buffered: tokens can't be unsent once streamed)
        feedback, draft, approved = "", "", False
        for attempt in range(settings.MAX_CRITIC_RETRIES + 1):
            yield f"data: {json.dumps({'type': 'thinking', 'content': 'Synthesizing and verifying response...'})}\n\n"
            draft = "".join([t async for t in self.synthesizer.stream_generate(query, context_chunks, feedback)])
            verdict = await self.critic.evaluate(query, context_chunks, draft)
            if verdict.passed:
                approved = True
                break
            feedback = verdict.feedback or ""

        text = draft if approved else "I could not verify a grounded answer from the available sources."
        yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"

        # 5. Emit Citations and Completion
        if citations:
            yield f"data: {json.dumps({'type': 'citations', 'sources': citations})}\n\n"

        yield "data: [DONE]\n\n"


orchestrator = RAGOrchestrator()
