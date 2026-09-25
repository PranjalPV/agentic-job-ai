import html
import json
import logging
import re

logger = logging.getLogger("agents")


def safe_json_parse(text: str):
    """
    Extract and parse JSON from LLM output safely
    """
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        # Try to extract JSON block
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                return None
        return None


def clean_text(text) -> str:
    """Strip HTML tags/entities and collapse whitespace (job APIs return HTML)."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(text))
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def emit_progress(message: str, **extra):
    """
    Send a progress event on LangGraph's "custom" stream.
    Does nothing when called outside a running graph (e.g. unit tests).
    """
    logger.info(message)
    try:
        from agents.graph.runtime import get_active_stream_writer, get_current_context

        writer = get_active_stream_writer()
        if writer:
            writer({"message": message, **extra})

        ctx = get_current_context()
        if ctx and getattr(ctx, "progress_callback", None):
            ctx.progress_callback(message)
    except Exception:
        pass
