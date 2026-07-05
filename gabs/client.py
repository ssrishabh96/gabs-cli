"""GitHub API + ntfy.sh transport client for gabs CLI.

Commands: CLI -> GitHub API file -> Hatch cron reads -> processes -> writes response -> CLI reads
Notifications: ntfy.sh provides instant push when response is ready.
Fallback: GitHub API polling every few seconds.
"""

from __future__ import annotations

import json
import base64
import time
import threading
import logging
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from .config import Config

logger = logging.getLogger("gabs.client")


class GabsClient:
    """Client that bridges CLI <-> Gabs agent via GitHub + ntfy.sh."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._connected = False
        self._command_ts: float = 0.0  # Track when command was sent

    # ── Connection ─────────────────────────────────────────────────────────

    def connect(self, timeout: float = 10.0) -> bool:
        """Verify GitHub API access by reading the repo."""
        try:
            resp = self._github_api("GET", f"repos/{self.config.github_repo}")
            if resp and resp.get("full_name"):
                self._connected = True
                return True
        except Exception as exc:
            logger.error("GitHub connection failed: %s", exc)
        self._connected = False
        return False

    def verify_write_access(self) -> bool:
        """Verify we can write to the repo (not just read)."""
        test_path = f"gabs-inbox/.write-test-{int(time.time())}"
        ok = self._write_github_file(
            test_path, "test", "gabs-cli: write access check",
        )
        if ok:
            self._delete_github_file(test_path, "gabs-cli: cleanup write test")
        return ok

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Send Command ───────────────────────────────────────────────────────

    def send_command(
        self,
        command: str,
        cmd_type: str = "query",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Write command to GitHub and ping ntfy. Returns True on success."""
        self._command_ts = time.time()

        payload = {
            "v": 1,
            "type": cmd_type,
            "command": command,
            "ts": self._command_ts,
            "client": "gabs-cli",
        }
        if metadata:
            payload["meta"] = metadata

        ok = self._write_github_file(
            self.config.command_path,
            json.dumps(payload, indent=2),
            f"gabs-cli: {command[:60]}",
        )
        if not ok:
            return False

        # Ping ntfy.sh (non-fatal if it fails)
        try:
            self._ntfy_publish(self.config.ntfy_cmd_topic, f"cmd: {command[:80]}")
        except Exception:
            pass

        return True

    # ── Wait for Response ──────────────────────────────────────────────────

    def wait_for_response(self, timeout: int | None = None) -> dict[str, Any] | None:
        """Poll GitHub (+ ntfy wake-up) for a response to the last sent command."""
        timeout = timeout or self.config.timeout
        deadline = time.monotonic() + timeout

        # Use the timestamp from when we sent the command, not now
        cmd_ts = self._command_ts if self._command_ts > 0 else time.time()

        # ntfy wake-up event — lets us interrupt the poll sleep early
        wake_event = threading.Event()

        ntfy_thread = threading.Thread(
            target=self._ntfy_listen,
            args=(self.config.ntfy_res_topic, deadline, wake_event),
            daemon=True,
        )
        ntfy_thread.start()

        # Poll GitHub for response
        while time.monotonic() < deadline:
            response_text = self._read_github_file(self.config.response_path)
            if response_text:
                try:
                    data = json.loads(response_text)
                    resp_ts = data.get("ts", 0)
                    # Accept if response timestamp is within 30s before command
                    # (covers clock skew between Mac and Hatch VM)
                    if resp_ts >= cmd_ts - 30:
                        # Clean up response file (best effort)
                        self._delete_github_file(
                            self.config.response_path, "gabs-cli: consumed",
                        )
                        return data
                except json.JSONDecodeError:
                    pass

            # Sleep until ntfy wakes us or poll interval elapses
            remaining = deadline - time.monotonic()
            wait_time = min(self.config.poll_interval, max(remaining, 0))
            if wait_time > 0:
                wake_event.wait(timeout=wait_time)
                wake_event.clear()

        return None

    # ── GitHub File Ops ────────────────────────────────────────────────────

    def read_file(self, filepath: str) -> str | None:
        """Read a file from the GitHub repo. Public for COLLAB.md access."""
        return self._read_github_file(filepath)

    def write_file(self, filepath: str, content: str, message: str) -> bool:
        """Write a file to the GitHub repo. Public for COLLAB.md access."""
        return self._write_github_file(filepath, content, message)

    # ── GitHub API ─────────────────────────────────────────────────────────

    def _github_api(
        self, method: str, path: str, body: dict | None = None
    ) -> dict | None:
        url = f"https://api.github.com/{path}"
        headers = {
            "Authorization": f"token {self.config.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "gabs-cli/1.1",
        }
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code == 404:
                return None
            error_body = ""
            try:
                error_body = e.read().decode()[:200]
            except Exception:
                pass
            logger.error("GitHub API %d: %s", e.code, error_body)
            return None
        except (URLError, TimeoutError) as e:
            logger.error("GitHub API error: %s", e)
            return None

    def _write_github_file(
        self, filepath: str, content: str, message: str
    ) -> bool:
        path = f"repos/{self.config.github_repo}/contents/{quote(filepath, safe='/')}"
        existing = self._github_api("GET", path)
        sha = existing.get("sha") if existing else None

        body: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
        }
        if sha:
            body["sha"] = sha

        result = self._github_api("PUT", path, body)
        return result is not None and "content" in (result or {})

    def _read_github_file(self, filepath: str) -> str | None:
        path = f"repos/{self.config.github_repo}/contents/{quote(filepath, safe='/')}"
        data = self._github_api("GET", path)
        if data and "content" in data:
            try:
                return base64.b64decode(data["content"]).decode()
            except Exception:
                return None
        return None

    def _delete_github_file(self, filepath: str, message: str) -> bool:
        path = f"repos/{self.config.github_repo}/contents/{quote(filepath, safe='/')}"
        existing = self._github_api("GET", path)
        if not existing or "sha" not in existing:
            return True
        body = {"message": message, "sha": existing["sha"]}
        try:
            url = f"https://api.github.com/{path}"
            headers = {
                "Authorization": f"token {self.config.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "gabs-cli/1.1",
            }
            req = Request(
                url, data=json.dumps(body).encode(),
                headers=headers, method="DELETE",
            )
            with urlopen(req, timeout=15):
                return True
        except Exception:
            return False

    # ── ntfy.sh ────────────────────────────────────────────────────────────

    def _ntfy_publish(self, topic: str, message: str) -> None:
        url = f"{self.config.ntfy_server}/{topic}"
        req = Request(url, data=message.encode(), method="POST")
        req.add_header("Title", "gabs-cli")
        try:
            with urlopen(req, timeout=5):
                pass
        except Exception:
            pass

    def _ntfy_listen(
        self, topic: str, deadline: float, wake_event: threading.Event
    ) -> None:
        """Subscribe to ntfy SSE stream; set wake_event when a message arrives."""
        url = f"{self.config.ntfy_server}/{topic}/sse"
        try:
            remaining = max(deadline - time.monotonic(), 5)
            req = Request(url)
            with urlopen(req, timeout=remaining) as resp:
                for line in resp:
                    if time.monotonic() >= deadline:
                        break
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data:"):
                        wake_event.set()
                        break
        except Exception:
            pass
