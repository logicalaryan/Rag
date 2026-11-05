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
        self.sessions: Dict[str, List[str]] = {}

    async def execute_stream(
        self, query: str, session_id: str, chat_history: str = ""
    ) -> AsyncGenerator[str, None]:
        if not self.client:
            yield f"data: {json.dumps({'type': 'token', 'content': 'Error: GEMINI_API_KEY is not configured on the backend.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        history_turns = self.sessions.setdefault(session_id, [])
        effective_history = chat_history or "\n".join(history_turns[-6:])

        feedback, draft, approved = "", "", False
        citations: List[str] = []
        context_chunks: List[RetrievedChunk] = []

        try:
            # Self-Reflection Loop (archit5.md): Router -> Tools -> Synthesizer -> Critic -> (Refine -> Router)
            for attempt in range(settings.MAX_CRITIC_RETRIES + 1):
                # 1. Query Rewriter & Router Agent
                status_prefix = f"[Retry {attempt}/{settings.MAX_CRITIC_RETRIES}] " if attempt > 0 else ""
                yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Router analyzing intent & rewriting query...'})}\n\n"
                routing = await self.router.route(query, effective_history, critic_feedback=feedback)
                search_query = routing.rewritten_query

                # Direct LLM Response path (Basic Greeting)
                if routing.intent == "direct_answer" and attempt == 0:
                    async for token in self.synthesizer.stream_generate(
                        query, [], chat_history=effective_history, direct_answer=True
                    ):
                        draft += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    approved = True
                    break

                # 2. Tool Execution (search_local_docs / search_web)
                if routing.intent in ["search_local", "both"]:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Tool search_local_docs (HNSW + BM25 + FlashRank): \"{search_query}\"...'})}\n\n"
                    local_chunks = await local_retriever.execute(search_query, top_k=settings.FINAL_TOP_K)
                    seen_ids = {c.id for c in context_chunks}
                    context_chunks.extend(c for c in local_chunks if c.id not in seen_ids)

                if routing.intent in ["search_web", "both"] or (not context_chunks and routing.intent != "direct_answer"):
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Tool search_web: \"{search_query}\"...'})}\n\n"
                    web_chunks = await web_search_tool.execute(search_query, top_k=2)
                    seen_ids = {c.id for c in context_chunks}
                    context_chunks.extend(c for c in web_chunks if c.id not in seen_ids)

                for c in context_chunks:
                    label = f"{c.source}" + (f":p{c.page}" if c.page else "")
                    if label not in citations:
                        citations.append(label)

                # 3. Synthesizer Agent (Draft Answer)
                yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Synthesizer drafting grounded answer...'})}\n\n"
                draft = "".join([
                    t async for t in self.synthesizer.stream_generate(
                        query, context_chunks, feedback, chat_history=effective_history
                    )
                ])

                # 4. Critic Agent (Is Answer Grounded & Complete?)
                yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Critic verifying groundedness & completeness...'})}\n\n"
                verdict = await self.critic.evaluate(query, context_chunks, draft)
                if verdict.passed:
                    approved = True
                    break
                feedback = verdict.feedback or "Ensure all claims are grounded and complete."

            if not (routing.intent == "direct_answer" and approved and not context_chunks):
                text = draft if approved else (draft or "I could not verify a grounded answer from the available sources.")
                yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
        except Exception as exc:
            text = f"Service error while generating response: {exc}"
            yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
        else:
            final_text = draft if approved else (draft or "I could not verify a grounded answer from the available sources.")
            history_turns.extend([f"User: {query}", f"Assistant: {final_text}"])

        # 5. Emit Citations and Completion
        if citations:
            yield f"data: {json.dumps({'type': 'citations', 'sources': citations})}\n\n"

        yield "data: [DONE]\n\n"


orchestrator = RAGOrchestrator()
