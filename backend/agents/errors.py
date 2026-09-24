class UserFacingError(ValueError):
    """
    An error whose message is safe and useful to show the user.
    Never retried: running again gives the same result.
    """


class InvalidLLMOutput(ValueError):
    """The model answered, but not in the expected format."""


class TransientError(Exception):
    """A temporary failure that is worth retrying."""


def is_transient(exc: Exception) -> bool:
    """
    Decide whether a failed node should be retried by LangGraph's RetryPolicy.
    Retries rate limits, timeouts, connection problems and 5xx errors only,
    so bad API keys or bad input fail fast.
    """
    if isinstance(exc, ValueError):
        return False
    if isinstance(exc, TransientError):
        return True

    try:
        import requests

        if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
            return True
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return exc.response.status_code == 429 or exc.response.status_code >= 500
    except ImportError:
        pass

    try:
        import httpx

        if isinstance(exc, httpx.TransportError):
            return True
    except ImportError:
        pass

    try:
        import groq

        if isinstance(exc, (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError)):
            return True
    except ImportError:
        pass

    try:
        from google.genai import errors as genai_errors

        if isinstance(exc, genai_errors.ServerError):
            return True
        if isinstance(exc, genai_errors.ClientError) and getattr(exc, "code", None) == 429:
            return True
    except ImportError:
        pass

    return False
