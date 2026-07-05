"""Configuration management for gabs CLI.

Transport: GitHub API (commands/responses) + ntfy.sh (real-time notifications).
Config stored in ~/.gabs/config.yaml. Auto-generates namespace on first run.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".gabs"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
HISTORY_FILE = CONFIG_DIR / "history"
CACHE_DIR = CONFIG_DIR / "cache"

_DEFAULTS: dict[str, Any] = {
    "namespace": None,
    "github": {
        "repo": "ssrishabh96/hatch-backup",
        "token": None,
    },
    "ntfy": {
        "server": "https://ntfy.sh",
    },
    "timeout": 120,
    "poll_interval": 3,
    "theme": "dark",
    "show_timestamps": True,
    "max_history": 1000,
}


class Config:
    """Manage gabs CLI configuration."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as fh:
                self._data = yaml.safe_load(fh) or {}
        else:
            self._data = {}
        for key, val in _DEFAULTS.items():
            if key not in self._data:
                self._data[key] = val
            elif isinstance(val, dict):
                for k2, v2 in val.items():
                    if k2 not in self._data[key]:
                        self._data[key][k2] = v2

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as fh:
            yaml.dump(self._data, fh, default_flow_style=False, sort_keys=False)
        CONFIG_FILE.chmod(0o600)

    @property
    def namespace(self) -> str | None:
        return self._data.get("namespace")

    @namespace.setter
    def namespace(self, value: str) -> None:
        self._data["namespace"] = value

    @property
    def github_repo(self) -> str:
        return self._data.get("github", {}).get("repo", "ssrishabh96/hatch-backup")

    @property
    def github_token(self) -> str | None:
        token = self._data.get("github", {}).get("token")
        if token:
            return token
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            return token
        return self._try_gh_cli_token()

    @github_token.setter
    def github_token(self, value: str) -> None:
        if "github" not in self._data:
            self._data["github"] = {}
        self._data["github"]["token"] = value

    @property
    def inbox_path(self) -> str:
        return f"gabs-inbox/{self.namespace}"

    @property
    def command_path(self) -> str:
        return f"{self.inbox_path}/command.json"

    @property
    def response_path(self) -> str:
        return f"{self.inbox_path}/response.json"

    @property
    def ntfy_server(self) -> str:
        return self._data.get("ntfy", {}).get("server", "https://ntfy.sh")

    @property
    def collab_path(self) -> str:
        return "gabs-collab/COLLAB.md"

    @property
    def ntfy_cmd_topic(self) -> str:
        return f"gabs-{self.namespace}-cmd"

    @property
    def ntfy_res_topic(self) -> str:
        return f"gabs-{self.namespace}-res"

    @property
    def timeout(self) -> int:
        return self._data.get("timeout", 120)

    @timeout.setter
    def timeout(self, value: int) -> None:
        self._data["timeout"] = value

    @property
    def poll_interval(self) -> int:
        return self._data.get("poll_interval", 3)

    @property
    def theme(self) -> str:
        return self._data.get("theme", "dark")

    @theme.setter
    def theme(self, value: str) -> None:
        self._data["theme"] = value

    @property
    def show_timestamps(self) -> bool:
        return self._data.get("show_timestamps", True)

    @property
    def max_history(self) -> int:
        return self._data.get("max_history", 1000)

    def is_configured(self) -> bool:
        return self.namespace is not None and self.github_token is not None

    def generate_namespace(self) -> str:
        ns = uuid.uuid4().hex[:16]
        self.namespace = ns
        self.save()
        return ns

    def reset(self) -> None:
        self._data = {}
        for key, val in _DEFAULTS.items():
            self._data[key] = val
        self.save()

    def as_dict(self) -> dict[str, Any]:
        d = dict(self._data)
        gh = d.get("github", {})
        if gh.get("token"):
            gh = dict(gh)
            gh["token"] = gh["token"][:8] + "..." + gh["token"][-4:]
            d["github"] = gh
        return d

    @staticmethod
    def _try_gh_cli_token() -> str | None:
        import subprocess
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None
