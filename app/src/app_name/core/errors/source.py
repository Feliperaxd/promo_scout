from .base import AppError


class SourceError(AppError):
    """An integration (API, scraper...) failed to return what was asked."""

    def __init__(
        self,
        message: str,
        *,
        source: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.source: str | None = source
        self.status_code: int | None = status_code

    def __str__(self) -> str:
        prefix = f"[{self.source}] " if self.source else ""
        suffix = f" (HTTP {self.status_code})" if self.status_code else ""
        return f"{prefix}{super().__str__()}{suffix}"


class AuthenticationError(SourceError):
    """Missing, invalid or expired credentials."""


class RateLimitError(SourceError):
    """The source asked us to slow down."""

    def __init__(
        self,
        message: str = "Rate limit reached.",
        *,
        source: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, source=source, status_code=429)
        self.retry_after: float | None = retry_after
        