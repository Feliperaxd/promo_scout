import json
import time
from pathlib import Path
from typing import Any


def save_tokens(path: Path, response: dict[str, Any]) -> None:
    """Save the token response as JSON, adding an absolute expiry time.

    The tokens are stored in plain text, so keep this file out of version
    control.

    Args:
        path: JSON file to write. Missing folders are created.
        response: token response from Mercado Libre. Its `expires_in`
            (seconds) is converted to `expires_at`, a Unix timestamp. If
            `expires_in` is missing, the tokens are saved as already expired.
    """
    data = dict(response)
    data["expires_at"] = int(time.time()) + int(response.get("expires_in", 0))

    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file first so a crash never leaves a broken file.
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_tokens(path: Path) -> dict[str, Any] | None:
    """Return the saved tokens, or None if nothing was saved yet.

    Raises:
        json.JSONDecodeError: if the file exists but is not valid JSON.
    """
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
