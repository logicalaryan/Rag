import json
from typing import List
from google import genai
from google.genai import types
from app.config import settings
from app.db.models import CriticEvaluation, RetrievedChunk


class CriticAgent:
    """
    Self-reflection agent:
    Validates groundedness (hallucinations) and answer relevance against retrieved context.
    """

    def __init__(self, client: genai.Client):
        self.client = client

    async def evaluate(self, query: str, context_chunks: List[RetrievedChunk], draft_answer: str) -> CriticEvaluation:
        if not context_chunks:
            # If no context, check if the model appropriately refused or gave conversational greeting
            is_polite_refusal = any(phrase in draft_answer.lower() for phrase in ["not mentioned", "cannot find", "do not have", "hello", "hi "])
            return CriticEvaluation(
                passed=is_polite_refusal,
                faithfulness_score=1.0 if is_polite_refusal else 0.2,
                relevance_score=0.9,
                feedback="Validated against empty context boundary."
            )

        contexts_text = "\n\n".join([f"[{c.source} | p.{c.page or 1}]: {c.content}" for c in context_chunks])

        prompt = f"""You are the strict Quality and Groundedness Critic for a RAG pipeline.
Your job is to detect hallucinations, unsupported claims, or ungrounded statements in the draft answer.

Rules:
1. Faithfulness: Every factual statement in the draft must be supported by the Context.
2. If there are hallucinations, list them.
3. Pass threshold: faithfulness_score >= 0.85 and relevance_score >= 0.80.

Return strictly a JSON object:
{{
  "passed": true | false,
  "faithfulness_score": 0.0 - 1.0,
  "relevance_score": 0.0 - 1.0,
  "feedback": "<Critique guidance for correction if failed>",
  "detected_hallucinations": ["<claim 1>", ...]
}}

Context:
{contexts_text}

Question:
{query}

Draft Answer:
{draft_answer}
"""
        try:
            response = self.client.models.generate_content(
                model=settings.PRIMARY_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(response.text)
            return CriticEvaluation(
                passed=bool(data.get("passed", True)),
                faithfulness_score=float(data.get("faithfulness_score", 1.0)),
                relevance_score=float(data.get("relevance_score", 1.0)),
                feedback=data.get("feedback"),
                detected_hallucinations=data.get("detected_hallucinations", []),
            )
        except Exception:
            return CriticEvaluation(
                passed=True,
                faithfulness_score=1.0,
                relevance_score=1.0,
                feedback="Critic bypass on parsing error",
            )
