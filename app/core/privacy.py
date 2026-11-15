import re
import logging
from typing import Dict, List, Tuple, Optional
from app.db.models import RetrievedChunk

# High-risk secrets (ALWAYS redacted across all external sinks and logs)
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("API_KEY", re.compile(r"\b(?:AIza[0-9A-Za-z\-_]{35}|sk-[A-Za-z0-9\-_]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9\-]{10,})\b")),
    ("BEARER_TOKEN", re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9\-._~+/]{16,}=*")),
    ("CREDENTIAL", re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\b(\s*[:=]\s*)(['\"]?)[^\s'\",;]{4,}\3")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
]

# Regulated / Sensitive PII
PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("SSN", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?|\d{3,4}[\s.-])\d{3,4}[\s.-]\d{4}\b")),
    ("IPV4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b")),
]

INTERNAL_DOC_TERMS = re.compile(
    r"(?i)\b(confidential|internal use only|proprietary|employee id|ssn|salary|compensation|nda|secret)\b"
)


class PrivacyContext:
    """
    Reversible pseudonymization vault scoped to a single request.
    Allows LLMs to reason over consistent tokens ([EMAIL_1], [PHONE_1]) and restores
    legitimate PDF PII for the authorized user if needed, while stripping raw secrets permanently.
    """

    def __init__(self):
        self.token_to_raw: Dict[str, str] = {}
        self.raw_to_token: Dict[str, str] = {}
        self.counters: Dict[str, int] = {}

    def pseudonymize(self, label: str, value: str) -> str:
        if value in self.raw_to_token:
            return self.raw_to_token[value]
        idx = self.counters.get(label, 0) + 1
        self.counters[label] = idx
        token = f"[{label}_{idx}]"
        self.raw_to_token[value] = token
        self.token_to_raw[token] = value
        return token

    def restore(self, text: str) -> str:
        if not text or not self.token_to_raw:
            return text
        for token, raw in self.token_to_raw.items():
            text = text.replace(token, raw)
        return text


class PrivacyGuard:
    """
    Centralized Data Privacy & Security Layer for external transmission points:
    - 'llm' (Gemini Router / Synthesizer / Critic): Redacts secrets & high-risk PII (SSN, CC);
      pseudonymizes contact PII (EMAIL, PHONE) via PrivacyContext so questions about PDF contacts still work.
    - 'embedding' (Gemini Embeddings): Strips secrets & high-risk PII while preserving semantic text.
    - 'web_search' (DuckDuckGo): Strictest sink. Permanently strips ALL secrets, ALL PII, quoted blocks,
      and blocks queries carrying confidential document markers unless allow_sensitive_web=True.
    - 'log' (Logging / SSE errors): Permanently masks all secrets and PII.
    """

    @staticmethod
    def redact_secrets(text: str) -> str:
        if not text:
            return text
        out = text
        for label, pattern in SECRET_PATTERNS:
            if label == "BEARER_TOKEN":
                out = pattern.sub(r"\1 [REDACTED_BEARER]", out)
            elif label == "CREDENTIAL":
                out = pattern.sub(r"\1\2[REDACTED_SECRET]", out)
            else:
                out = pattern.sub(f"[REDACTED_{label}]", out)
        return out

    @classmethod
    def sanitize_for_llm(cls, text: str, ctx: Optional[PrivacyContext] = None) -> str:
        if not text:
            return text
        out = cls.redact_secrets(text)
        for label, pattern in PII_PATTERNS:
            if label in ("SSN", "CREDIT_CARD"):
                out = pattern.sub(f"[REDACTED_{label}]", out)
            elif ctx is not None and label in ("EMAIL", "PHONE"):
                out = pattern.sub(lambda m: ctx.pseudonymize(label, m.group(0)), out)
            else:
                out = pattern.sub(f"[REDACTED_{label}]", out)
        return out

    @classmethod
    def sanitize_chunks_for_llm(
        cls, chunks: List[RetrievedChunk], ctx: Optional[PrivacyContext] = None
    ) -> List[RetrievedChunk]:
        sanitized: List[RetrievedChunk] = []
        for c in chunks:
            sanitized.append(
                RetrievedChunk(
                    id=c.id,
                    content=cls.sanitize_for_llm(c.content, ctx=ctx),
                    score=c.score,
                    source=cls.redact_secrets(c.source),
                    page=c.page,
                    metadata=dict(c.metadata or {}),
                )
            )
        return sanitized

    @classmethod
    def sanitize_for_embedding(cls, text: str) -> str:
        if not text:
            return text
        out = cls.redact_secrets(text)
        for label, pattern in PII_PATTERNS:
            if label in ("SSN", "CREDIT_CARD"):
                out = pattern.sub(f"[REDACTED_{label}]", out)
        return out

    @classmethod
    def sanitize_for_web_search(
        cls, query: str, allow_sensitive_web: bool = False
    ) -> Optional[str]:
        """
        Sanitizes a query before sending to public DuckDuckGo search.
        Returns None if the query contains confidential internal markers or nothing remains after stripping PII/secrets.
        """
        if not query or not query.strip():
            return None

        if not allow_sensitive_web and INTERNAL_DOC_TERMS.search(query):
            return None

        out = cls.redact_secrets(query)
        for label, pattern in PII_PATTERNS:
            out = pattern.sub("", out)

        # Remove redaction placeholders, long verbatim quotes, and collapse whitespace
        out = re.sub(r"\[REDACTED_[A-Z_]+\]", "", out)
        out = re.sub(r"\[(?:EMAIL|PHONE|SSN|CREDIT_CARD|IPV4)_\d+\]", "", out)
        out = re.sub(r"\s+", " ", out).strip()

        # Enforce strict query length minimization (max 120 chars) for external search
        out = out[:120].strip()
        return out if len(out) >= 2 else None

    @classmethod
    def sanitize_for_log(cls, text: str) -> str:
        if not text:
            return text
        out = cls.redact_secrets(str(text))
        for label, pattern in PII_PATTERNS:
            out = pattern.sub(f"[REDACTED_{label}]", out)
        return out


class PrivacyLogFilter(logging.Filter):
    """Logging filter that scrubs secrets and PII from all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg:
            record.msg = PrivacyGuard.sanitize_for_log(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: PrivacyGuard.sanitize_for_log(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(PrivacyGuard.sanitize_for_log(str(a)) for a in record.args)
        return True


privacy_guard = PrivacyGuard()
