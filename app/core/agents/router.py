import json
import logging
from google import genai
from google.genai import types
from app.config import settings
from app.db.models import RoutingDecision


class RouterAgent:
    """
    Analyzes user intent and context:
    1. Classifies intent: 'search_local', 'search_web', 'both', or 'direct_answer'
    2. Resolves pronouns & rewrites conversational query into a standalone search query.
    """

    def __init__(self, client: genai.Client):
        self.client = client

    async def route(self, query: str, chat_history: str = "", critic_feedback: str = "") -> RoutingDecision:
        refinement_note = (
            f"\nSelf-Correction Feedback from Critic (generate a refined search query to fill missing/unverified details):\n{critic_feedback}\n"
            if critic_feedback
            else ""
        )
        prompt = f"""You are the Query Rewriter and Intent Router for an Agentic RAG system.
Evaluate the user query and conversational history:
- 'search_local': For internal company policies, technical specifications, and uploaded documents (Tool: search_local_docs).
- 'search_web': For current events, real-time info, or public entities outside internal knowledge (Tool: search_web).
- 'both': Needs both internal documents and external web context.
- 'direct_answer': Basic conversational greetings or clarification requiring no search.

Also produce a rewritten standalone search query resolving ambiguous pronouns.{refinement_note}
Return strictly a JSON object:
{{
  "intent": "search_local" | "search_web" | "both" | "direct_answer",
  "rewritten_query": "<resolved standalone search query>",
  "reasoning": "<brief 1-sentence reason>"
}}

Chat History:
{chat_history}

User Query:
{query}
"""
        for model in (settings.PRIMARY_MODEL, settings.FALLBACK_MODEL):
            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                data = json.loads(response.text)
                return RoutingDecision(
                    intent=data.get("intent", "search_local"),
                    rewritten_query=data.get("rewritten_query", query),
                    reasoning=data.get("reasoning", "Standard routing"),
                )
            except Exception:
                if model == settings.FALLBACK_MODEL:
                    logging.exception("router failed, defaulting to search_local")
        return RoutingDecision(
            intent="search_local",
            rewritten_query=query,
            reasoning="Fallback heuristic default",
        )
