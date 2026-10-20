import subprocess
import time


class NgrokTunnel:
    def __init__(self, domain: str, port: int = 8000) -> None:
        self.domain: str = domain
        self.port: int = port
        self._process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        self._process = subprocess.Popen(
            ["ngrok", "http", f"--url={self.domain}", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

    def stop(self) -> None:
        if self._process:
            self._process.terminate()
            self._process = None
            