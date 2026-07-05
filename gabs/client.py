"""GitHub API + ntfy.sh transport client for gabs CLI.

Commands: CLI -> GitHub API file -> Hatch cron reads -> processes -> writes response -> CLI reads
Notifications: ntfy.sh provides instant push when response is ready (open source).
Fallback: GitHub API polling every few seconds if ntfy misses.
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
        self._response: dict[str, Any] | None = None
        self._response_event = threading.Event()

    # ── Connection ─────────────────────────────────────────────────────────

    def connect(self, timeout: float = 10.0) -> bool:
        try:
            resp = self._github_api("GET", f"repos/{self.config.github_repo}")
            if resp and resp.get("full_name"):
                self._connected = True
                return True
        except Exception as exc:
            logger.error("GitHub connection failed: %s", exc)
        self._connected = False
        return False

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
        payload = {
            "v": 1,
            "type": cmd_type,
            "command": command,
            "ts": time.time(),
            "client": "gabs-cli",
        }
        if metadata:
            payload["meta"] = metadata

        self._response = None
        self._response_event.clear()

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
        timeout = timeout or self.config.timeout
        deadline = time.monotonic() + timeout
        cmd_ts = time.time()

        # Start ntfy listener in background
        ntfy_thread = threading.Thread(
            target=self._ntfy_listen,
            args=(self.config.ntfy_res_topic, deadline),
            daemon=True,
        )
        ntfy_thread.start()

        # Poll GitHub as primary + ntfy as interrupt
        while time.monotonic() < deadline:
            if self._response_event.is_set() and self._response:
                return self._response

            response_text = self._read_github_file(self.config.response_path)
            if response_text:
                try:
                    data = json.loads(response_text)
                    resp_ts = data.get("ts", 0)
                    if resp_ts >= cmd_ts - 5:
                        self._response = data
                        self._response_event.set()
                        # Clean up
                        self._delete_github_file(
                            self.config.response_path,
                            "gabs-cli: consumed",
                        )
                        return self._response
                except json.JSONDecodeError:
                    pass

            remaining = deadline - time.monotonic()
            wait_time = min(self.config.poll_interval, max(remaining, 0))
            if wait_time > 0:
                self._response_event.wait(timeout=wait_time)
                self._response_event.clear()

        return None

    def send_and_wait(
        self,
        command: str,
        cmd_type: str = "query",
        timeout: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not self.send_command(command, cmd_type, metadata):
            return None
        return self.wait_for_response(timeout)

    # ── GitHub API ─────────────────────────────────────────────────────────

    def _github_api(self, method: str, path: str, body: dict | None = None) -> dict | None:
        url = f"https://api.github.com/{path}"
        headers = {
            "Authorization": f"token {self.config.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "gabs-cli/1.0",
        }
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code == 404:
                return None
            logger.error("GitHub API %d: %s", e.code, e.read().decode()[:200])
            return None
        except (URLError, TimeoutError) as e:
            logger.error("GitHub API error: %s", e)
            return None

    def _write_github_file(self, filepath: str, content: str, message: str) -> bool:
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
                "User-Agent": "gabs-cli/1.0",
            }
            req = Request(url, data=json.dumps(body).encode(), headers=headers, method="DELETE")
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

    def _ntfy_listen(self, topic: str, deadline: float) -> None:
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
                        self._response_event.set()
                        break
        except Exception:
            pass
