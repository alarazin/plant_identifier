"""Classify provider errors and decide whether fallback is allowed.

Only explicit model availability or model-limit errors allow fallback.
Provider error reference: https://docs.eachlabs.ai/errors"""

from enum import Enum


class ErrorKind(str, Enum):
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_LIMIT = "model_limit"
    ACCOUNT_LIMIT = "account_limit"
    AUTH = "auth"
    BALANCE = "balance"
    TIMEOUT = "timeout"
    NETWORK = "network"
    INVALID_RESPONSE = "invalid_response"
    UPSTREAM = "upstream"


class EachlabsError(RuntimeError):
    def __init__(
        self, message: str, *, kind: ErrorKind = ErrorKind.UPSTREAM,
        status_code: int | None = None, code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.code = code
        self.record: dict | None = None

    @property
    def allows_fallback(self) -> bool:
        return self.kind in {ErrorKind.MODEL_UNAVAILABLE, ErrorKind.MODEL_LIMIT}


# Only these explicit model errors allow fallback. Unknown errors stop the request.
_UNAVAILABLE_CODES = {"MODEL_UNAVAILABLE", "MODEL_DISABLED", "MODEL_OFFLINE"}
_LIMIT_CODES = {"MODEL_RATE_LIMITED", "MODEL_QUOTA_EXCEEDED"}
_UNAVAILABLE_MESSAGES = {
    "model unavailable", "model is unavailable", "model temporarily unavailable",
    "model is temporarily unavailable", "model is not available", "model is disabled",
}


def provider_error(
    payload: object, *, operation: str, status_code: int | None = None,
) -> EachlabsError:
    """Classify trusted error fields, never arbitrary logs or model answer text."""
    body = payload if isinstance(payload, dict) else {}
    detail = body.get("error") if isinstance(body.get("error"), dict) else body
    code = str(detail.get("error_code") or detail.get("code") or "").upper()
    message = detail.get("error_message") or detail.get("message") or detail.get("error")
    message = message if isinstance(message, str) else "upstream request failed"
    scope = str(detail.get("scope") or body.get("scope") or "").lower()

    kind = ErrorKind.UPSTREAM
    if status_code in {401, 403} or code in {"PROVIDER_AUTH_ERROR", "AUTHENTICATION_ERROR"}:
        kind = ErrorKind.AUTH
    elif status_code == 402 or code == "INSUFFICIENT_BALANCE":
        kind = ErrorKind.BALANCE
    elif status_code == 429 or code in {"ACCOUNT_RATE_LIMITED", "ACCOUNT_CONCURRENCY_LIMIT"}:
        # Eachlabs' documented default is account-wide concurrency, not a
        # model quota. Only an explicit model-limit code can override it.
        kind = ErrorKind.ACCOUNT_LIMIT

    model_error = (
        operation in {"create prediction", "prediction"}
        and status_code in {None, 404, 410, 429, 503}
        and kind not in {ErrorKind.AUTH, ErrorKind.BALANCE}
        and code not in {"ACCOUNT_RATE_LIMITED", "ACCOUNT_CONCURRENCY_LIMIT"}
        and scope not in {"account", "organization", "platform"}
    )
    if model_error:
        if code in _LIMIT_CODES or (scope == "model" and status_code == 429):
            kind = ErrorKind.MODEL_LIMIT
        elif status_code != 429 and (
            code in _UNAVAILABLE_CODES
            or message.strip().lower().rstrip(".") in _UNAVAILABLE_MESSAGES
        ):
            kind = ErrorKind.MODEL_UNAVAILABLE

    return EachlabsError(
        f"{operation} failed [{status_code or code or 'error'}]: {message[:200]}",
        kind=kind, status_code=status_code, code=code or None,
    )


def public_error(exc: EachlabsError) -> tuple[int, str]:
    """Messages safe and useful to display on the phone, without provider logs."""
    return {
        ErrorKind.MODEL_UNAVAILABLE: (503, "The identification models are unavailable. Please try again later."),
        ErrorKind.MODEL_LIMIT: (503, "The models have reached their request limit. Please try again later."),
        ErrorKind.ACCOUNT_LIMIT: (503, "The identification service is busy. Please try again shortly."),
        ErrorKind.AUTH: (503, "The identification service is not configured correctly. Check the backend API key and permissions."),
        ErrorKind.BALANCE: (503, "The identification service has insufficient API credit. Check the backend account balance."),
        ErrorKind.TIMEOUT: (504, "The identification service took too long to respond. Please try again."),
        ErrorKind.NETWORK: (503, "Could not connect to the identification service. Please try again."),
        ErrorKind.INVALID_RESPONSE: (502, "The model returned an unreadable response. Please try again."),
        ErrorKind.UPSTREAM: (502, "The identification service could not process the request. Please try again."),
    }[exc.kind]
