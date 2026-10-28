import json
import subprocess
import time
import urllib.request
from typing import Self

AUTH_ERROR_HINTS = ("authtoken", "authentication failed")
NGROK_API_URL = "http://127.0.0.1:4040/api/tunnels"
STARTUP_TIMEOUT = 10.0
POLL_INTERVAL = 0.3

_AUTHTOKEN_TIMEOUT = 15
_API_TIMEOUT = 1
_STOP_TIMEOUT = 5
_NOT_FOUND_MESSAGE = "ngrok not found. Install it and check your PATH."


class NgrokTunnelError(RuntimeError):
    """Raised when the ngrok tunnel fails to start or stay up."""


class NgrokAuthError(NgrokTunnelError):
    """ngrok refused to start: the authtoken is missing or invalid."""


def set_authtoken(token: str) -> None:
    """Save the authtoken in ngrok's own configuration file.

    Args:
        token: the authtoken from the ngrok dashboard.

    Raises:
        NgrokAuthError: if ngrok rejects the token.
        NgrokTunnelError: if ngrok is not installed or the command times out.
    """
    try:
        result = subprocess.run(
            ["ngrok", "config", "add-authtoken", token],
            capture_output=True,
            text=True,
            timeout=_AUTHTOKEN_TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise NgrokTunnelError(_NOT_FOUND_MESSAGE) from exc
    except subprocess.TimeoutExpired as exc:
        raise NgrokTunnelError("Timed out saving the authtoken.") from exc

    if result.returncode != 0:
        message = (result.stdout + result.stderr).strip()
        raise NgrokAuthError(message or "Could not save the authtoken.")


class NgrokTunnel:
    """Run an ngrok tunnel with a fixed domain via subprocess.

    Can be used as a context manager: the tunnel starts on enter and stops
    on exit.

    Attributes:
        domain: fixed ngrok domain, without scheme, e.g. "my.ngrok-free.dev".
        port: local port the tunnel forwards to.
    """

    def __init__(self, domain: str, port: int = 8000) -> None:
        self.domain: str = domain
        self.port: int = port
        self._process: subprocess.Popen[str] | None = None

    @property
    def public_url(self) -> str:
        """Public HTTPS URL of the tunnel."""
        return f"https://{self.domain}"

    def start(self) -> str:
        """Start the tunnel and return its public URL once it is up.

        Raises:
            NgrokAuthError: if the authtoken is missing or invalid.
            NgrokTunnelError: if the tunnel is already running, ngrok is not
                installed, or the tunnel does not come up in time.
        """
        if self._process is not None:
            raise NgrokTunnelError("The tunnel is already running.")

        try:
            self._process = subprocess.Popen(
                [
                    "ngrok",
                    "http",
                    f"--url={self.domain}",
                    "--log=stdout",
                    str(self.port),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise NgrokTunnelError(_NOT_FOUND_MESSAGE) from exc

        try:
            self._wait_until_ready()
        except NgrokTunnelError:
            self.stop()
            raise

        return self.public_url

    def stop(self) -> None:
        """Stop the tunnel if it is running."""
        if self._process is None:
            return

        self._process.terminate()
        try:
            self._process.wait(timeout=_STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._process.kill()

        if self._process.stdout is not None:
            self._process.stdout.close()
        self._process = None

    def _wait_until_ready(self) -> None:
        """Block until the tunnel is reachable or the timeout expires."""
        deadline = time.monotonic() + STARTUP_TIMEOUT

        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                self._raise_startup_error()
            if self._is_tunnel_up():
                return
            time.sleep(POLL_INTERVAL)

        raise NgrokTunnelError("Timed out waiting for the tunnel to start.")

    def _raise_startup_error(self) -> None:
        """Classify why ngrok exited and raise the matching error."""
        output = ""
        if self._process is not None and self._process.stdout is not None:
            output = self._process.stdout.read().strip()

        if any(hint in output.lower() for hint in AUTH_ERROR_HINTS):
            raise NgrokAuthError(output)

        raise NgrokTunnelError(f"ngrok exited on startup:\n{output}")

    def _is_tunnel_up(self) -> bool:
        """Check ngrok's local API for an active tunnel on this domain."""
        try:
            with urllib.request.urlopen(NGROK_API_URL, timeout=_API_TIMEOUT) as response:
                data = json.load(response)
        except (OSError, ValueError):  # URLError is an OSError
            return False

        return any(
            self.domain in tunnel.get("public_url", "")
            for tunnel in data.get("tunnels", [])
        )

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()
