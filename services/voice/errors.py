"""Classified TTS errors. Retry policy lives in the provider, not in Game Master."""

from __future__ import annotations


class TTSError(Exception):
    """Provider synthesis failed. ``retryable`` drives bounded retries only."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


def retry_after_from_headers(headers: dict | None) -> float | None:
    if not headers:
        return None
    raw = None
    for key, value in headers.items():
        if str(key).lower() == "retry-after":
            raw = value
            break
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return True
    try:
        import httpx

        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
            return True
    except ImportError:
        pass
    return False


def is_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, OSError)):
        return True
    try:
        import httpx

        if isinstance(exc, httpx.TransportError):
            return True
    except ImportError:
        pass
    return False


def _message_from_exc(exc: BaseException) -> str:
    """Prefer provider body (status/code/message) over a generic SDK str()."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict):
            parts = [detail.get("status"), detail.get("code"), detail.get("message")]
            text = " ".join(str(part) for part in parts if part)
            if text:
                return text[:300]
        if isinstance(detail, str) and detail.strip():
            return detail.strip()[:300]
    return (str(exc)[:300] or type(exc).__name__)


def classify_exception(exc: BaseException) -> TTSError:
    """Map provider/SDK exceptions to TTSError. Never treat 401/403/422 as retryable."""
    if isinstance(exc, TTSError):
        return exc
    status = getattr(exc, "status_code", None)
    headers = getattr(exc, "headers", None)
    retry_after = retry_after_from_headers(headers if isinstance(headers, dict) else None)
    message = _message_from_exc(exc)

    if status in {401, 403}:
        return TTSError(message, status_code=status, retryable=False)
    if status in {400, 404, 422}:
        return TTSError(message, status_code=status, retryable=False)
    if status == 429 or (isinstance(status, int) and status >= 500):
        return TTSError(
            message,
            status_code=status,
            retryable=True,
            retry_after_seconds=retry_after,
        )
    if is_timeout_error(exc) or is_network_error(exc):
        return TTSError(message, status_code=status, retryable=True)
    return TTSError(message, status_code=status, retryable=False)
