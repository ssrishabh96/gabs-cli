#!/usr/bin/env python3
"""Server-side gabs bridge — runs on the Hatch VM via cron.

Uses git (pull/push) for the GitHub repo and curl for ntfy.sh notifications.
Both are proven to work from this VM.

Usage:
    python3 server/listener.py check          # Returns command JSON or exits 1
    python3 server/listener.py respond -m "text" [-t "title"]
    python3 server/listener.py clear          # Remove the pending command
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_DIR = Path.home() / "workspace" / "gabs-inbox-repo"
REPO_URL = "https://github.com/ssrishabh96/hatch-backup.git"
NTFY_SERVER = "https://ntfy.sh"
INBOX_ROOT = "gabs-inbox"


def _detect_namespace() -> str | None:
    """Find the first namespace dir with a command.json, or the only namespace."""
    inbox = REPO_DIR / INBOX_ROOT
    if not inbox.exists():
        return None
    ns_dirs = [d.name for d in inbox.iterdir() if d.is_dir() and d.name != ".git"]
    if not ns_dirs:
        return None
    # If any has a pending command, prefer that
    for ns in ns_dirs:
        if (inbox / ns / "command.json").exists():
            return ns
    # Otherwise return first one
    return ns_dirs[0]


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    """Run a shell command, return stdout."""
    result = subprocess.run(
        cmd,
        cwd=cwd or REPO_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def _ensure_repo() -> None:
    """Clone or pull the repo."""
    if not REPO_DIR.exists():
        _run(["git", "clone", "--depth", "1", "--filter=blob:none",
              "--sparse", REPO_URL, str(REPO_DIR)], cwd=Path.home())
        _run(["git", "sparse-checkout", "set", "gabs-inbox"])
    else:
        # Reset any dirty state before pulling
        _run(["git", "reset", "HEAD", "--", "."], check=False)
        _run(["git", "checkout", "--", "."], check=False)
        _run(["git", "pull", "--rebase", "--quiet"])


def _git_push(message: str) -> None:
    """Stage, commit, and push."""
    _run(["git", "add", "-A"])
    # Check if there's anything to commit
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=REPO_DIR, capture_output=True,
    )
    if result.returncode != 0:  # There are staged changes
        _run(["git", "commit", "-m", message])
        _run(["git", "push", "--quiet"])


def _ntfy_ping(topic: str, message: str) -> None:
    """Send a notification via ntfy.sh using curl."""
    subprocess.run(
        ["curl", "-s", "-d", message,
         "-H", "Title: gabs",
         f"{NTFY_SERVER}/{topic}"],
        capture_output=True, timeout=15,
    )


# ── Commands ───────────────────────────────────────────────────────────────────

def check_command() -> str | None:
    """Check for a pending command across all namespaces. Returns JSON string or None."""
    _ensure_repo()
    ns = _detect_namespace()
    if not ns:
        return None
    cmd_file = REPO_DIR / INBOX_ROOT / ns / "command.json"
    if cmd_file.exists():
        content = cmd_file.read_text().strip()
        if content:
            # Stash namespace for respond/clear to use
            _ACTIVE_NS_FILE.write_text(ns)
            return content
    return None


def _get_active_ns() -> str | None:
    """Get the namespace from the last check_command call."""
    if _ACTIVE_NS_FILE.exists():
        return _ACTIVE_NS_FILE.read_text().strip()
    return _detect_namespace()


_ACTIVE_NS_FILE = Path("/tmp/gabs-active-ns")


def publish_response(message: str, title: str | None = None) -> bool:
    """Write response.json, push, and notify."""
    _ensure_repo()
    ns = _get_active_ns()
    if not ns:
        print("No active namespace found", file=sys.stderr)
        return False

    payload = {
        "v": 1,
        "type": "response",
        "text": message,
        "ts": time.time(),
    }
    if title:
        payload["title"] = title

    resp_dir = REPO_DIR / INBOX_ROOT / ns
    resp_dir.mkdir(parents=True, exist_ok=True)
    resp_file = resp_dir / "response.json"
    resp_file.write_text(json.dumps(payload, indent=2))

    try:
        _git_push("gabs: response")
        _ntfy_ping(f"gabs-{ns}-res", "response ready")
        return True
    except Exception as e:
        print(f"Push failed: {e}", file=sys.stderr)
        return False


def clear_command() -> bool:
    """Remove the pending command file."""
    _ensure_repo()
    ns = _get_active_ns()
    if not ns:
        return True
    cmd_file = REPO_DIR / INBOX_ROOT / ns / "command.json"
    if cmd_file.exists():
        cmd_file.unlink()
        try:
            _git_push("gabs: command processed")
            return True
        except Exception as e:
            print(f"Push failed: {e}", file=sys.stderr)
            return False
    return True


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="gabs server-side bridge")
    parser.add_argument("action", choices=["check", "respond", "clear"])
    parser.add_argument("--message", "-m", help="Response message")
    parser.add_argument("--title", "-t", help="Response title")
    args = parser.parse_args()

    if args.action == "check":
        result = check_command()
        if result:
            print(result)
            sys.exit(0)
        else:
            sys.exit(1)

    elif args.action == "respond":
        if not args.message:
            print("--message required", file=sys.stderr)
            sys.exit(1)
        ok = publish_response(args.message, args.title)
        sys.exit(0 if ok else 1)

    elif args.action == "clear":
        ok = clear_command()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
