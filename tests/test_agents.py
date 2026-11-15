"""
Unit tests for centralized Data Privacy & Security Layer across all external transmission points:
1. Gemini LLM APIs (Router, Synthesizer, Critic) with reversible PII pseudonymization
2. DuckDuckGo Web Search (strict PII/secret stripping and confidential query blocking)
3. External Embedding Provider (secret/SSN/CC scrubbing before embed_content)
4. Logging & Observability (PrivacyLogFilter scrubbing log records)
5. Tenant / Document access isolation in retrieval
"""
import logging
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.core.privacy import privacy_guard, PrivacyContext, PrivacyLogFilter
from app.db.models import RetrievedChunk
from app.core.agents.router import RouterAgent
from app.core.agents.synthesizer import SynthesizerAgent
from app.core.agents.critic import CriticAgent
from app.core.tools.web_search import GeminiGoogleSearchTool as WebSearchTool
from app.core.indexing.embeddings import EmbeddingClient


def test_secret_and_pii_detection_without_corrupting_normal_numbers():
    ctx = PrivacyContext()
    raw = (
        "Contact hr@company.com or +1 (555) 234-5678. "
        "Temperature in Lucknow is 28.5°C on 2026-11-15. "
        "API_KEY=AIzaSyD-1234567890abcdefghijklmnopqrstuvw and SSN 123-45-6789."
    )
    sanitized = privacy_guard.sanitize_for_llm(raw, ctx=ctx)

    # Secrets and SSN permanently redacted
    assert "AIzaSyD" not in sanitized
    assert "123-45-6789" not in sanitized
    assert "[REDACTED_SSN]" in sanitized

    # Email and Phone pseudonymized consistently
    assert "hr@company.com" not in sanitized
    assert "234-5678" not in sanitized
    assert "[EMAIL_1]" in sanitized
    assert "[PHONE_1]" in sanitized

    # Legitimate numbers (temperature, dates) preserved intact
    assert "28.5°C" in sanitized
    assert "2026-11-15" in sanitized

    # Reversible restoration for authorized user response
    llm_draft = "You can reach HR at [EMAIL_1] or call [PHONE_1]."
    restored = ctx.restore(llm_draft)
    assert restored == "You can reach HR at hr@company.com or call +1 (555) 234-5678."


@pytest.mark.asyncio
async def test_router_agent_scrubs_secrets_and_pii_before_gemini_call():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"intent": "search_local", "rewritten_query": "contact [EMAIL_1]", "reasoning": "ok"}'
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

    router = RouterAgent(mock_client)
    ctx = PrivacyContext()
    await router.route(
        query="Email alice@enterprise.org with password=supersecret123",
        chat_history="User: My SSN is 123-45-6789",
        privacy_ctx=ctx,
    )

    called_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    sent_contents = called_kwargs["contents"]
    assert "alice@enterprise.org" not in sent_contents
    assert "supersecret123" not in sent_contents
    assert "123-45-6789" not in sent_contents
    assert "[EMAIL_1]" in sent_contents
    assert "[REDACTED_SECRET]" in sent_contents


@pytest.mark.asyncio
async def test_synthesizer_preserves_pdf_pii_answers_without_leaking_to_gemini():
    mock_client = MagicMock()

    async def fake_stream():
        chunk = MagicMock()
        chunk.text = "The support email in the policy PDF is [EMAIL_1]."
        yield chunk

    mock_client.aio.models.generate_content_stream = AsyncMock(return_value=fake_stream())

    synthesizer = SynthesizerAgent(mock_client)
    ctx = PrivacyContext()
    chunks = [
        RetrievedChunk(
            id="doc1_p1_c1",
            content="For IT escalations, contact support@internal.corp or Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            score=0.92,
            source="company_policy.pdf",
            page=1,
        )
    ]

    output_tokens = [
        t async for t in synthesizer.stream_generate(
            query="What is the IT escalation email?",
            context_chunks=chunks,
            privacy_ctx=ctx,
        )
    ]
    full_answer = "".join(output_tokens)

    # Verify Gemini never saw raw email or bearer token
    sent_prompt = mock_client.aio.models.generate_content_stream.call_args.kwargs["contents"]
    assert "support@internal.corp" not in sent_prompt
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sent_prompt
    assert "[EMAIL_1]" in sent_prompt

    # Verify user still gets the real email from their PDF
    assert "support@internal.corp" in full_answer


@pytest.mark.asyncio
async def test_critic_agent_scrubs_chunks_and_draft_before_gemini_call():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"passed": true, "faithfulness_score": 0.95, "relevance_score": 0.95}'
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

    critic = CriticAgent(mock_client)
    ctx = PrivacyContext()
    chunks = [
        RetrievedChunk(
            id="c1",
            content="Admin email is admin@corp.com and api_key=sk-1234567890abcdefghijklmnop",
            score=0.9,
            source="sec.pdf",
            page=1,
        )
    ]
    await critic.evaluate("Who is admin?", chunks, "Admin is admin@corp.com", privacy_ctx=ctx)

    sent_prompt = mock_client.aio.models.generate_content.call_args.kwargs["contents"]
    assert "admin@corp.com" not in sent_prompt
    assert "sk-1234567890abcdefghijklmnop" not in sent_prompt


@pytest.mark.asyncio
async def test_web_search_blocks_confidential_queries_and_strips_pii():
    tool = WebSearchTool()
    tool.client = MagicMock()

    # 1. Confidential internal query must be blocked from Web Search
    with patch.object(tool, "search_and_ground") as mock_search:
        res = await tool.execute("Confidential salary compensation policy for employee id 42")
        assert res == []
        mock_search.assert_not_called()

    # 2. Public query containing accidental PII strips PII before hitting Google Grounding
    with patch.object(tool, "search_and_ground", return_value=([], "")) as mock_search:
        await tool.execute("weather in Lucknow for user john@example.com")
        mock_search.assert_called_once()
        sent_query = mock_search.call_args.args[0]
        assert "john@example.com" not in sent_query
        assert "weather in Lucknow" in sent_query


def test_embedding_client_redacts_secrets_and_ssn():
    client = EmbeddingClient()
    client.client = MagicMock()
    mock_emb = MagicMock()
    mock_emb.values = [0.1, 0.2]
    client.client.models.embed_content.return_value = MagicMock(embeddings=[mock_emb])

    client.embed_query("Search SSN 123-45-6789 with token=my_secret_token_value")
    sent_text = client.client.models.embed_content.call_args.kwargs["contents"]
    assert "123-45-6789" not in sent_text
    assert "my_secret_token_value" not in sent_text


def test_log_filter_scrubs_sensitive_values():
    log_filter = PrivacyLogFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=1,
        msg="Failed login for user@domain.com with password=topsecretvalue",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record)
    assert "user@domain.com" not in record.msg
    assert "topsecretvalue" not in record.msg
    assert "[REDACTED_EMAIL]" in record.msg
    assert "[REDACTED_SECRET]" in record.msg
