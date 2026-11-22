import os
import json
import asyncio
import re
from typing import AsyncGenerator, Dict, Any, List
from google import genai
from app.config import settings
from app.db.models import RetrievedChunk
from app.db.vector_store import vector_store
from app.db.postgres import conversation_store
from app.core.agents.router import RouterAgent
from app.core.agents.synthesizer import SynthesizerAgent
from app.core.agents.critic import CriticAgent
from app.core.tools.local_retriever import local_retriever
from app.core.tools.web_search import web_search_tool
from app.core.privacy import privacy_guard, PrivacyContext
from app.core.llm_gateway import gemini_gateway


class RAGOrchestrator:
    def _contains_sensitive_web_query_data(self, text: str) -> bool:
        if not text:
            return False
        patterns = [
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b",
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----",
            r"\b(?:api[_-]?key|secret|token|password|passwd|credential)s?\b",
        ]
        lowered = text.lower()
        if any(k in lowered for k in ("internal only", "confidential", "do not share", "private data")):
            return True
        return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

    """
    Multi-Agent Asynchronous State Machine:
    1. Request Rate Limiting, Tenant-Scoped Cache & Single-Flight Coalescing
    2. Intent Routing & Query Rewriting
    3. Tool Execution (Local Hybrid Search / Web Search)
    4. Grounded Synthesis & Critic Verification
    5. PostgreSQL Conversation Persistence & SSE Event Emission
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
        if self.client:
            web_search_tool.client = self.client
        self.sessions: Dict[str, List[str]] = {}

    async def execute_stream(
        self,
        query: str,
        session_id: str,
        chat_history: str = "",
        tenant_id: str = "default",
        allow_web_search: bool = True,
        allow_sensitive_web: bool = False,
    ) -> AsyncGenerator[str, None]:
        if not self.client:
            yield f"data: {json.dumps({'type': 'token', 'content': 'Error: GEMINI_API_KEY is not configured on the backend.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        session_key = f"{tenant_id}:{session_id}"

        # 1. Request-level rate limiting per tenant/session
        allowed, retry_after = gemini_gateway.check_client_rate_limit(session_key)
        if not allowed:
            msg = f"Rate limit reached: please wait {retry_after}s before sending another message."
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 2. Tenant- & KB-Isolated Response Cache
        kb_count = vector_store.count()
        kb_fingerprint = f"chunks:{kb_count}"
        cache_key = gemini_gateway.build_cache_key(
            tenant_id=tenant_id,
            kb_fingerprint=kb_fingerprint,
            query=query,
            allow_web_search=allow_web_search,
        )
        cached = gemini_gateway.get_cached(cache_key)
        if cached:
            yield f"data: {json.dumps({'type': 'token', 'content': cached['text']})}\n\n"
            if cached.get("citations"):
                yield f"data: {json.dumps({'type': 'citations', 'sources': cached['citations']})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 3. Single-Flight Deduplication for identical concurrent requests
        inflight_fut = gemini_gateway._inflight.get(cache_key)
        if inflight_fut is not None:
            yield f"data: {json.dumps({'type': 'thinking', 'content': 'Awaiting identical in-flight request...'})}\n\n"
            try:
                result = await asyncio.wait_for(asyncio.shield(inflight_fut), timeout=settings.GEMINI_TIMEOUT_SECONDS)
                yield f"data: {json.dumps({'type': 'token', 'content': result['text']})}\n\n"
                if result.get("citations"):
                    yield f"data: {json.dumps({'type': 'citations', 'sources': result['citations']})}\n\n"
                yield "data: [DONE]\n\n"
                return
            except Exception:
                pass

        loop = asyncio.get_running_loop()
        my_future = loop.create_future()
        gemini_gateway._inflight[cache_key] = my_future

        # Load recent conversation history from PostgreSQL (or fall back to in-memory buffer)
        history_turns = self.sessions.setdefault(session_key, [])
        if len(history_turns) > 12:
            del history_turns[:-12]
        effective_history = chat_history
        if not effective_history:
            pg_turns = await conversation_store.get_recent_history(session_id=session_id, tenant_id=tenant_id, limit=4)
            effective_history = "\n".join(pg_turns) if pg_turns else "\n".join(history_turns[-4:])

        privacy_ctx = PrivacyContext()
        tenant_filter = {"tenant_id": tenant_id} if tenant_id and tenant_id != "default" else None

        feedback, draft, approved = "", "", False
        citations: List[str] = []
        context_chunks: List[RetrievedChunk] = []
        streamed_directly = False

        try:
            for attempt in range(settings.MAX_CRITIC_RETRIES + 1):
                status_prefix = f"[Retry {attempt}/{settings.MAX_CRITIC_RETRIES}] " if attempt > 0 else ""
                yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Router analyzing intent & rewriting query...'})}\n\n"
                routing = await self.router.route(
                    query,
                    effective_history,
                    critic_feedback=feedback,
                    privacy_ctx=privacy_ctx,
                    has_local_docs=(kb_count > 0),
                )
                search_query = privacy_ctx.restore(routing.rewritten_query)
                safe_display_query = privacy_guard.sanitize_for_log(search_query)

                # Direct LLM Response path (Greetings, Math, Timeless General Knowledge)
                if routing.intent == "direct_answer" and attempt == 0:
                    async for token in self.synthesizer.stream_generate(
                        query, [], chat_history=effective_history, direct_answer=True, privacy_ctx=privacy_ctx
                    ):
                        draft += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    approved = True
                    streamed_directly = True
                    break

                # Tool Execution
                seen_ids = {c.id for c in context_chunks}
                if routing.intent == "both" and kb_count > 0 and allow_web_search:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Searching local docs & web in parallel: \"{safe_display_query}\"...'})}\n\n"
                    local_chunks, web_chunks = await asyncio.gather(
                        local_retriever.execute(search_query, top_k=settings.FINAL_TOP_K, filter_metadata=tenant_filter),
                        web_search_tool.execute(search_query, top_k=3, allow_sensitive_web=allow_sensitive_web),
                    )
                    context_chunks.extend(c for c in local_chunks + web_chunks if c.id not in seen_ids)
                elif routing.intent in ("search_local", "both") and kb_count > 0:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Tool search_local_docs (HNSW + BM25 + FlashRank): \"{safe_display_query}\"...'})}\n\n"
                    local_chunks = await local_retriever.execute(
                        search_query, top_k=settings.FINAL_TOP_K, filter_metadata=tenant_filter
                    )
                    context_chunks.extend(c for c in local_chunks if c.id not in seen_ids)

                if allow_web_search and (
                    routing.intent == "search_web" or (not context_chunks and routing.intent != "direct_answer")
                ):
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Tool search_web: \"{safe_display_query}\"...'})}\n\n"
                    web_chunks = await web_search_tool.execute(
                        search_query, top_k=3, allow_sensitive_web=allow_sensitive_web
                    )
                    seen_ids = {c.id for c in context_chunks}
                    context_chunks.extend(c for c in web_chunks if c.id not in seen_ids)

                # If KB is empty and Web Search Grounding returned empty (e.g. grounding quota limit),
                # answer general queries directly rather than burning 2+ extra calls on empty context
                if not context_chunks and kb_count == 0:
                    async for token in self.synthesizer.stream_generate(
                        query, [], chat_history=effective_history, direct_answer=True, privacy_ctx=privacy_ctx
                    ):
                        draft += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    approved = True
                    streamed_directly = True
                    break

                for c in context_chunks:
                    label = f"{c.source}" + (f":p{c.page}" if c.page else "")
                    if label not in citations:
                        citations.append(label)

                # Synthesizer Agent (Draft Answer)
                yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Synthesizer drafting grounded answer...'})}\n\n"
                draft = "".join([
                    t async for t in self.synthesizer.stream_generate(
                        query, context_chunks, feedback, chat_history=effective_history, privacy_ctx=privacy_ctx
                    )
                ])

                # Skip extra Critic LLM call when context is empty or came solely from Google Search Grounding
                only_web_sources = bool(context_chunks) and all(c.id.startswith("web_google") for c in context_chunks)
                if not context_chunks or only_web_sources:
                    approved = True
                    break

                # Critic Agent (Is Answer Grounded & Complete?)
                yield f"data: {json.dumps({'type': 'thinking', 'content': f'{status_prefix}Critic verifying groundedness & completeness...'})}\n\n"
                verdict = await self.critic.evaluate(query, context_chunks, draft, privacy_ctx=privacy_ctx)
                if verdict.passed:
                    approved = True
                    break
                feedback = verdict.feedback or "Ensure all claims are grounded and complete."

            if not streamed_directly:
                text = draft if approved else (draft or "I could not verify a grounded answer from the available sources.")
                yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
        except Exception as exc:
            safe_err = privacy_guard.sanitize_for_log(str(exc))
            if "429" in safe_err or "RESOURCE_EXHAUSTED" in safe_err:
                text = "The AI service is temporarily rate-limited (Free Tier quota). Please wait ~30 seconds and try again."
            else:
                text = f"Service error while generating response: {safe_err}"
            yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
            if not my_future.done():
                my_future.set_exception(exc)
        else:
            final_text = draft if approved else (draft or "I could not verify a grounded answer from the available sources.")
            safe_user_msg = privacy_guard.redact_secrets(query)
            safe_assistant_msg = privacy_guard.redact_secrets(final_text)

            history_turns.extend([
                f"User: {safe_user_msg}",
                f"Assistant: {safe_assistant_msg}",
            ])
            is_refusal = "do not have enough verified information" in final_text.lower() or not approved
            final_citations = citations if (citations and not is_refusal) else []

            # Persist turn to Neon PostgreSQL
            await conversation_store.save_turn(
                session_id=session_id,
                tenant_id=tenant_id,
                user_query=safe_user_msg,
                assistant_answer=safe_assistant_msg,
                citations=final_citations,
            )

            payload = {"text": final_text, "citations": final_citations}
            if approved and not is_refusal:
                gemini_gateway.set_cached(cache_key, payload)
            if not my_future.done():
                my_future.set_result(payload)
        finally:
            gemini_gateway._inflight.pop(cache_key, None)

        # Emit Citations and Completion
        is_refusal = "do not have enough verified information" in draft.lower() or not approved
        if citations and not is_refusal:
            yield f"data: {json.dumps({'type': 'citations', 'sources': citations})}\n\n"

        yield "data: [DONE]\n\n"


orchestrator = RAGOrchestrator()
