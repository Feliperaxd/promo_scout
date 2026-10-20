import http.server
import os
import urllib.parse
import webbrowser

from dotenv import load_dotenv

from ngrok_tunnel import NgrokTunnel

load_dotenv()


class Auth:
    def __init__(self, port: int = 8000) -> None:
        app_id = os.getenv("ML_APP_ID")
        redirect_url = os.getenv("ML_REDIRECT_URI")

        if app_id is None or redirect_url is None:
            raise RuntimeError(
                "Defina ML_APP_ID e ML_REDIRECT_URI no .env"
            )

        self.app_id: str = app_id
        self.redirect_url: str = redirect_url
        self.port: int = port

    def get_authorization_url(self) -> str:
        return "https://auth.mercadolivre.com.br/authorization?" + (
            urllib.parse.urlencode(
                {
                    "response_type": "code",
                    "client_id": self.app_id,
                    "redirect_uri": self.redirect_url,
                }
            )
        )

    def _wait_for_code(self) -> str:
        result: dict[str, str | None] = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                code = params.get("code", [None])[0]

                # Ignora requisições sem code (ex: favicon.ico)
                if code is None:
                    self.send_response(204)
                    self.end_headers()
                    return

                result["code"] = code
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    "Autorizado! Pode fechar esta aba.".encode()
                )

            def log_message(self, *args) -> None:
                pass

        server = http.server.HTTPServer(("localhost", self.port), Handler)
        while "code" not in result:
            server.handle_request()
        server.server_close()

        return str(result["code"])

    def open_authorization_url(self) -> str:
        domain = urllib.parse.urlparse(self.redirect_url).hostname
        if domain is None:
            raise ValueError("ML_REDIRECT_URI inválida.")

        tunnel = NgrokTunnel(domain, self.port)
        tunnel.start()
        try:
            webbrowser.open(self.get_authorization_url())
            return self._wait_for_code()
        finally:
            tunnel.stop()
            