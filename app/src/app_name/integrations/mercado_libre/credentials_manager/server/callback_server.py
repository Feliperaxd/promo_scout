import html
import http.server
import secrets
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path

CLIENT_DIR = Path(__file__).resolve().parents[1] / "static"
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
WAIT_TIMEOUT = 600.0

# Receives the submitted form and returns the URL to redirect the browser to.
SubmitHandler = Callable[[dict[str, str]], str]


class CallbackServerError(RuntimeError):
    """Raised when the authorization is denied or times out."""


class NeedsMoreInput(Exception):
    """Raised by the submit handler to ask the form for an extra field.

    The browser is sent back to the form with ``need=<field>`` plus the
    ``prefill`` values in the query string. Never put secrets in ``prefill``.
    """

    def __init__(
        self, field: str, prefill: dict[str, str] | None = None
    ) -> None:
        super().__init__(field)
        self.field: str = field
        self.prefill: dict[str, str] = prefill or {}


def _message_page(title: str, text: str, back: bool = False) -> bytes:
    link = '<p class="footer"><a href="/">Voltar</a></p>' if back else ""
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        '<link rel="stylesheet" href="/style.css"></head><body>'
        f'<main class="card"><h1>{html.escape(title)}</h1>'
        f'<p class="subtitle">{html.escape(text)}</p>{link}</main>'
        "</body></html>"
    ).encode()


class CallbackServer:
    """Serve the setup form on localhost and capture the OAuth callback.

    The form (GET / and POST /setup) is only served to requests that arrive
    through localhost. Requests coming through the public tunnel can only
    deliver the authorization code.
    """

    def __init__(self, on_submit: SubmitHandler, port: int = 8000) -> None:
        self.state: str = secrets.token_urlsafe(16)
        self._on_submit = on_submit
        self._code: str | None = None
        self._error: str | None = None

        self._server = http.server.HTTPServer(
            ("localhost", port), self._make_handler()
        )
        self._server.timeout = 1.0

    def wait_for_code(self, timeout: float = WAIT_TIMEOUT) -> str:
        """Serve requests until the authorization code arrives."""
        deadline = time.monotonic() + timeout

        try:
            while self._code is None and self._error is None:
                if time.monotonic() > deadline:
                    raise CallbackServerError(
                        "Timed out waiting for the authorization."
                    )
                self._server.handle_request()
        finally:
            self._server.server_close()

        if self._error is not None:
            raise CallbackServerError(f"Authorization failed: {self._error}")

        return str(self._code)

    def _make_handler(self) -> type[http.server.BaseHTTPRequestHandler]:
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def _is_local(self) -> bool:
                host = self.headers.get("Host", "").split(":")[0]
                return host in LOCAL_HOSTS

            def _send(
                self,
                status: int,
                body: bytes = b"",
                content_type: str = "text/html; charset=utf-8",
                location: str | None = None,
            ) -> None:
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(body)))
                    if location is not None:
                        self.send_header("Location", location)
                    self.end_headers()
                    self.wfile.write(body)
                except ConnectionError:
                    # The client closed the connection before reading.
                    pass

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)

                if parsed.path == "/style.css":
                    css = (CLIENT_DIR / "style.css").read_bytes()
                    self._send(200, css, "text/css; charset=utf-8")
                    return

                if parsed.path != "/":
                    self._send(204)
                    return

                params = urllib.parse.parse_qs(parsed.query)
                code = params.get("code", [None])[0]
                error = params.get("error", [None])[0]

                if code is not None:
                    received = params.get("state", [""])[0]
                    if not secrets.compare_digest(received, outer.state):
                        self._send(400, _message_page(
                            "Requisição inválida",
                            "O parâmetro state não confere.",
                        ))
                        return
                    outer._code = code
                    self._send(200, _message_page(
                        "Autorizado!", "Pode fechar esta aba."
                    ))
                    return

                if error is not None:
                    outer._error = error
                    self._send(200, _message_page(
                        "Autorização negada", "Pode fechar esta aba."
                    ))
                    return

                if not self._is_local():
                    self._send(404)
                    return

                self._send(200, (CLIENT_DIR / "index.html").read_bytes())

            def do_POST(self) -> None:
                if self.path != "/setup" or not self._is_local():
                    self._send(404)
                    return

                length = min(int(self.headers.get("Content-Length", 0)), 10_000)
                raw = self.rfile.read(length).decode()
                form = {
                    key: values[0].strip()
                    for key, values in urllib.parse.parse_qs(raw).items()
                }

                try:
                    location = outer._on_submit(form)
                except NeedsMoreInput as exc:
                    query = urllib.parse.urlencode(
                        {"need": exc.field, **exc.prefill}
                    )
                    self._send(303, location=f"/?{query}")
                    return
                except Exception as exc:
                    print(f"[setup] {exc}")
                    self._send(400, _message_page(
                        "Não foi possível continuar", str(exc), back=True
                    ))
                    return

                self._send(303, location=location)

        return Handler
    