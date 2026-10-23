import json
import subprocess
import time
import urllib.error
import urllib.request

NGROK_API_URL = "http://127.0.0.1:4040/api/tunnels"
STARTUP_TIMEOUT = 10.0
POLL_INTERVAL = 0.3


class NgrokTunnelError(RuntimeError):
    """Raised when the ngrok tunnel fails to start or stay up."""


class NgrokTunnel:
    """Run an ngrok tunnel with a fixed domain via subprocess."""

    def __init__(self, domain: str, port: int = 8000) -> None:
        self.domain: str = domain
        self.port: int = port
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def public_url(self) -> str:
        """Return the public HTTPS URL of the tunnel."""
        return f"https://{self.domain}"

    def start(self) -> str:
        """Start the tunnel and return its public URL once it is up."""
        if self._process is not None:
            raise NgrokTunnelError("The tunnel is already running.")

        try:
            self._process = subprocess.Popen(
                ["ngrok", "http", f"--url={self.domain}", str(self.port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise NgrokTunnelError(
                "ngrok not found. Install it and check your PATH."
            ) from exc

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
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
        self._process = None

    def _wait_until_ready(self) -> None:
        """Block until the tunnel is reachable or the timeout expires."""
        deadline = time.monotonic() + STARTUP_TIMEOUT

        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise NgrokTunnelError(
                    "ngrok exited on startup. Check your authtoken and "
                    "whether the domain is already used by another tunnel."
                )
            if self._is_tunnel_up():
                return
            time.sleep(POLL_INTERVAL)

        raise NgrokTunnelError("Timed out waiting for the tunnel to start.")

    def _is_tunnel_up(self) -> bool:
        """Check ngrok's local API for an active tunnel on this domain."""
        try:
            with urllib.request.urlopen(NGROK_API_URL, timeout=1) as response:
                data = json.load(response)
        except (urllib.error.URLError, OSError, ValueError):
            return False

        return any(
            self.domain in tunnel.get("public_url", "")
            for tunnel in data.get("tunnels", [])
        )

    def __enter__(self) -> "NgrokTunnel":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()
        