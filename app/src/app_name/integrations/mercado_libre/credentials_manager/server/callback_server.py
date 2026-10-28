import html
import http.server
import logging
import secrets
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path

CLIENT_DIR = Path(__file__).resolve().parents[1] / "static"
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
WAIT_TIMEOUT = 600.0

_MAX_FORM_BYTES = 10_000
_POLL_INTERVAL = 1.0

logger = logging.getLogger(__name__)

# Receives the submitted form and returns the URL to redirect the browser to.
SubmitHandler = Callable[[dict[str, str]], str]


class CallbackServerError(RuntimeError):
    """Raised when the authorization is denied or times out."""


class NeedsMoreInput(Exception):
    """Raised by the submit handler to ask the form for an extra field.

    The browser is sent back to the form with ``need=<field>`` plus the
    ``prefill`` values in the query string. Never put secrets in ``prefill``.
    """

    def __init__(self, field: str, prefill: dict[str, str] | None = None) -> None:
        super().__init__(field)
        self.field: str = field
        self.prefill: dict[str, str] = prefill or {}


def _message_page(title: str, text: str, back_link: bool = False) -> bytes:
    """Render a minimal HTML page with a title and a message."""
    link = '<p class="footer"><a href="/">Back</a></p>' if back_link else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        '<link rel="stylesheet" href="/style.css"></head><body>'
        f'<main class="card"><h1>{html.escape(title)}</h1>'
        f'<p class="subtitle">{html.escape(text)}</p>{link}</main>'
        "</body></html>"
    ).encode()


class CallbackServer(http.server.HTTPServer):
    """Serve the setup form on localhost and capture the OAuth callback.

    The form (GET / and POST /setup) is only served to requests that arrive
    through localhost. Requests coming through the public tunnel can only
    deliver the authorization code.

    The request handler reads and writes the attributes below through
    ``self.server``.

    Attributes:
        state: random value to include in the authorization URL. The callback
            must echo it back, otherwise the request is rejected (CSRF check).
        on_submit: called with the submitted form. Returns the URL to redirect
            the browser to, or raises `NeedsMoreInput`.
        code: authorization code, set when the callback arrives.
        error: error sent by the provider, set when the user denies access.
    """

    def __init__(self, on_submit: SubmitHandler, port: int = 8000) -> None:
        """Create the server and bind it to localhost.

        Args:
            on_submit: see the class attributes.
            port: local port to listen on.
        """
        super().__init__(("localhost", port), _RequestHandler)
        self.timeout = _POLL_INTERVAL
        self.state: str = secrets.token_urlsafe(16)
        self.on_submit = on_submit
        self.code: str | None = None
        self.error: str | None = None

    def wait_for_code(self, timeout: float = WAIT_TIMEOUT) -> str:
        """Serve requests until the authorization code arrives.

        Args:
            timeout: maximum time to wait, in seconds.

        Returns:
            The authorization code sent by the provider.

        Raises:
            CallbackServerError: if the authorization is denied or the
                timeout is reached.
        """
        deadline = time.monotonic() + timeout

        try:
            while self.code is None and self.error is None:
                if time.monotonic() > deadline:
                    raise CallbackServerError(
                        "Timed out waiting for the authorization."
                    )
                self.handle_request()
        finally:
            self.server_close()

        if self.error is not None:
            raise CallbackServerError(f"Authorization failed: {self.error}")

        assert self.code is not None  # the loop only ends with a code or an error
        return self.code


class _RequestHandler(http.server.BaseHTTPRequestHandler):
    """Handle the requests received by `CallbackServer`."""

    server: CallbackServer

    def log_message(self, *args: object) -> None:
        """Silence the default request logging."""

    def do_GET(self) -> None:
        """Serve the form and assets, or receive the OAuth callback."""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/style.css":
            css = (CLIENT_DIR / "style.css").read_bytes()
            self._send(200, css, "text/css; charset=utf-8")
            return

        if parsed.path != "/":
            self._send(204)  # e.g. the browser asking for /favicon.ico
            return

        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            self._handle_authorization_code(params)
        elif "error" in params:
            self._handle_authorization_error(params)
        elif self._is_local():
            self._send(200, (CLIENT_DIR / "index.html").read_bytes())
        else:
            self._send(404)

    def do_POST(self) -> None:
        """Receive the setup form and redirect to the next step."""
        if self.path != "/setup" or not self._is_local():
            self._send(404)
            return

        try:
            location = self.server.on_submit(self._read_form())
        except NeedsMoreInput as exc:
            query = urllib.parse.urlencode({"need": exc.field, **exc.prefill})
            self._send(303, location=f"/?{query}")
        except Exception as exc:  # noqa: BLE001 - shown to the user
            logger.warning("Setup failed: %s", exc)
            self._send(
                400,
                _message_page("Could not continue", str(exc), back_link=True),
            )
        else:
            self._send(303, location=location)

    def _handle_authorization_code(self, params: dict[str, list[str]]) -> None:
        """Store the authorization code if the state matches."""
        received_state = params.get("state", [""])[0]

        if not secrets.compare_digest(received_state, self.server.state):
            self._send(
                400,
                _message_page(
                    "Invalid request", "The state parameter does not match."
                ),
            )
            return

        self.server.code = params["code"][0]
        self._send(200, _message_page("Authorized!", "You can close this tab."))

    def _handle_authorization_error(self, params: dict[str, list[str]]) -> None:
        """Store the error sent by the provider."""
        self.server.error = params["error"][0]
        self._send(
            200, _message_page("Authorization denied", "You can close this tab.")
        )

    def _is_local(self) -> bool:
        """Tell whether the request arrived through localhost."""
        host = self.headers.get("Host", "").split(":")[0]
        return host in LOCAL_HOSTS

    def _read_form(self) -> dict[str, str]:
        """Read the submitted form, limited to `_MAX_FORM_BYTES`."""
        length = min(int(self.headers.get("Content-Length", 0)), _MAX_FORM_BYTES)
        raw = self.rfile.read(length).decode()
        return {
            key: values[0].strip()
            for key, values in urllib.parse.parse_qs(raw).items()
        }

    def _send(
        self,
        status: int,
        body: bytes = b"",
        content_type: str = "text/html; charset=utf-8",
        location: str | None = None,
    ) -> None:
        """Write a complete response, ignoring clients that disconnected."""
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if location is not None:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(body)
        except ConnectionError:
            pass  # the client closed the connection before reading
