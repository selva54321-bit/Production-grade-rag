import logfire
from portkey_ai import Portkey, createHeaders, PORTKEY_GATEWAY_URL
from langchain_openai import ChatOpenAI

from app.config import settings

#for now we use portkey but later we can use external cache system


# Production gateway config:
#   - Fallback: primary @rag/llama-3.3-70b-versatile → @brag/llama-3.1-8b-instant on failure
#   - Cache: semantic mode (requires Portkey Enterprise — silently falls back to simple on free/starter)
#   - Retry: 2 attempts on rate limit / server error before triggering the fallback target
GATEWAY_CONFIG = {
    "strategy": {"mode": "fallback"},
    "cache": {"mode": "simple"},
    "retry": {
        "attempts": 2,
        "on_status_codes": [429, 503]
    },
    "targets": [
        {"override_params": {"model": f"@{settings.GROQ_SLUG}/llama-3.3-70b-versatile"}},
        {"override_params": {"model": f"@{settings.GROQ_SLUG_2}/llama-3.1-8b-instant"}},
    ]
}

kwargs = {
    "api_key": settings.PORTKEY_API_KEY or "dummy"
}
if settings.PORTKEY_CONFIG_ID:
    kwargs["config"] = settings.PORTKEY_CONFIG_ID

# If Portkey is configured, use it. Otherwise, we will rely on Langchain fallbacks in the nodes.
try:
    portkey_client = Portkey(**kwargs)
except Exception:
    portkey_client = None

def get_langchain_llm(feature: str = "rag"):
    """
    Returns a Portkey-backed ChatOpenAI — a drop-in for ChatGroq in LangChain nodes.
    If PORTKEY_API_KEY is missing, falls back directly to ChatGroq.
    """
    if not settings.PORTKEY_API_KEY:
        logfire.warning("PORTKEY_API_KEY is not set. Falling back to direct ChatGroq.")
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=settings.GROQ_MODEL,
            temperature=0
        )

    headers = {
        "api_key": settings.PORTKEY_API_KEY,
        "metadata": {
            "feature": feature,  
            "_user": "rag-system",
            "environment": "production"
        }
    }
    if settings.PORTKEY_CONFIG_ID:
        headers["config"] = settings.PORTKEY_CONFIG_ID

    return ChatOpenAI(   
        api_key=settings.PORTKEY_API_KEY,
        base_url=PORTKEY_GATEWAY_URL,
        model=f"@{settings.GROQ_SLUG}/{settings.GROQ_MODEL}",
        temperature=0,
        default_headers=createHeaders(**headers)
    )

def extract_cache_status(response) -> str:
    """
    Pull x-portkey-cache-status from the Portkey native client response headers.
    Tries multiple attribute paths defensively — returns 'MISS' if not found.
    """
    for attr in ("_raw_response", "_response", "_http_response"):
        raw = getattr(response, attr, None)
        if raw is not None:
            status = getattr(raw, "headers", {}).get("x-portkey-cache-status", "")
            if status:
                return status.upper()
    return "MISS"