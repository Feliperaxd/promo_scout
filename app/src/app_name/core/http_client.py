import time
from typing import Any, Protocol

import requests

from app_name.core.errors import AuthenticationError, RateLimitError, SourceError

REQUEST_TIMEOUT = 15.0
MAX_RETRIES = 3
RETRY_STATUS = {429, 500, 502, 503, 504}


class AuthProvider(Protocol):
    """How a source authenticates its requests.

    Each integration implements this in its own way (OAuth tokens, API keys,
    basic auth...). `HttpClient` only depends on this contract.
    """

    def headers(self) -> dict[str, str]:
        """Return the headers that authenticate a request.

        Raises:
            AuthenticationError: if there are no credentials to use.
        """

    def refresh(self) -> None:
        """Renew the credentials after the source rejected them (HTTP 401).

        Raises:
            AuthenticationError: if the credentials cannot be renewed.
        """


class HttpClient:
    """Thin HTTP layer: auth headers, retries and error mapping.

    It knows nothing about any specific store: the base URL and the
    authentication strategy are injected.
    """

    def __init__(self, base_url: str, auth: AuthProvider | None = None) -> None:
        """Create the client.

        Args:
            base_url: root URL of the API, without a trailing slash.
            auth: authenticates the requests. None for public APIs.
        """
        self._base_url = base_url
        self._auth = auth
        self._session = requests.Session()

    def get(self, path: str, **params: Any) -> Any:
        """Send a GET request and return the decoded JSON body.

        Args:
            path: API path starting with "/", e.g. "/users/me".
            **params: query string parameters, e.g. `limit=50`.

        Returns:
            The parsed JSON: a dict or a list, depending on the endpoint.

        Raises:
            AuthenticationError: the auth provider has no credentials, or the
                API answered 401/403.
            RateLimitError: the API answered 429 and the retries ran out.
            SourceError: any other failed response, or retries exhausted.
        """
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict[str, Any]) -> Any:
        """Send a POST request with a JSON body. Same returns and errors as `get`."""
        return self._request("POST", path, json=json)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send a request, renewing the credentials and retrying when needed.

        On a 401 the credentials are renewed once (`auth.refresh()`) and the
        request is repeated. Statuses in `RETRY_STATUS` are retried up to
        `MAX_RETRIES` times with exponential backoff (1s, 2s, 4s).
        """
        refreshed = False

        for attempt in range(MAX_RETRIES + 1):
            response = self._session.request(
                method,
                f"{self._base_url}{path}",
                headers=self._auth_headers(),
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )

            if response.status_code == 401 and self._auth and not refreshed:
                self._auth.refresh()
                refreshed = True
                continue

            if response.status_code in RETRY_STATUS and attempt < MAX_RETRIES:
                time.sleep(2**attempt)  # 1s, 2s, 4s
                continue

            return self._parse(response)

        raise SourceError("Retries exhausted.")

    def _auth_headers(self) -> dict[str, str]:
        return self._auth.headers() if self._auth else {}

    @staticmethod
    def _parse(response: requests.Response) -> Any:
        """Return the JSON body, or raise the exception that matches the status."""
        if response.status_code == 429:
            raise RateLimitError("Rate limit reached.")
        if response.status_code in (401, 403):
            raise AuthenticationError(response.text)
        if not response.ok:
            raise SourceError(f"{response.status_code}: {response.text}")
        return response.json()
    