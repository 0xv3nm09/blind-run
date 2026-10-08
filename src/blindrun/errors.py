"""One exception tree. Adapters translate library errors into it."""

from blindrun.types import RunStatus  # noqa: F401  (re-exported for convenience)


class BlindRunError(Exception):
    code = "internal"
    http = 500


class SchemaError(BlindRunError):
    code = "schema_error"

    def __init__(self, role: str, err: Exception):
        super().__init__(f"{role}: {err}")
        self.role = role


class BudgetExceeded(BlindRunError):
    code = "budget_exceeded"
    http = 409


class UpstreamError(BlindRunError):
    code = "upstream_error"
    http = 502

    def __init__(self, service: str, status: int | None = None):
        super().__init__(f"{service} failed ({status})")
        self.service = service


class RateLimited(UpstreamError):
    code = "rate_limited"
    http = 429


class EarError(BlindRunError):
    code = "ear_error"


class EarTimeout(EarError):
    code = "ear_timeout"


class SandboxError(BlindRunError):
    code = "sandbox_error"


class IllegalTransition(BlindRunError):
    code = "internal"


class GuardBlocked(BlindRunError):
    code = "blocked"
    http = 400
