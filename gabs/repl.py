"""Interactive REPL for gabs CLI.

Full-featured terminal chat with command history, tab completion,
and rich formatting. Uses prompt_toolkit for the input line and
Rich for output rendering.
"""

from __future__ import annotations

import sys
import time
import signal
import threading
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.live import Live
from rich.spinner import Spinner

from . import __version__
from .client import GabsClient
from .commands import all_command_names, find_command
from .config import Config, HISTORY_FILE, CONFIG_DIR
from .display import (
    console,
    print_banner,
    print_mini_banner,
    print_you,
    print_gabs,
    print_gabs_panel,
    print_error,
    print_success,
    print_info,
    print_warn,
    print_help,
    print_config,
    clear_screen,
)

# ── Prompt Style ───────────────────────────────────────────────────────────────

PROMPT_STYLE = Style.from_dict({
    "prompt": "#00d7af bold",     # Cyan-green
    "arrow":  "#00d7af",
})


class Repl:
    """Interactive gabs REPL session."""

    def __init__(self, config: Config, compact: bool = False) -> None:
        self.config = config
        self.compact = compact
        self.client = GabsClient(config)
        self._running = False

        # Ensure config dir exists for history
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Prompt session with history + completion
        self.session = PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            completer=WordCompleter(
                all_command_names(),
                ignore_case=True,
                sentence=True,
            ),
            style=PROMPT_STYLE,
            enable_history_search=True,
        )

    # ── Main Loop ──────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the REPL."""
        self._running = True

        # Connect
        if not self._connect():
            return

        # Banner
        if self.compact:
            print_mini_banner()
        else:
            print_banner(__version__)

        # Handle Ctrl-C gracefully
        signal.signal(signal.SIGINT, self._handle_interrupt)

        try:
            while self._running:
                try:
                    user_input = self.session.prompt(
                        [("class:prompt", "you"), ("class:arrow", " → ")],
                    )
                except KeyboardInterrupt:
                    continue
                except EOFError:
                    break

                text = user_input.strip()
                if not text:
                    continue

                self._handle_input(text)

        finally:
            self._disconnect()

    # ── Input Handler ──────────────────────────────────────────────────────

    def _handle_input(self, text: str) -> None:
        """Route user input to the right handler."""

        # Meta commands (local, no agent round-trip)
        low = text.lower()

        if low in ("/quit", "/q", "/exit"):
            print_info("see ya ✌️")
            self._running = False
            return

        if low in ("/help", "/h", "/?"):
            print_help()
            return

        if low in ("/clear", "/cl"):
            clear_screen()
            return

        if low in ("/status", "/st"):
            self._show_status()
            return

        if low in ("/config", "/c"):
            print_config(self.config.as_dict())
            return

        if low.startswith("/timeout"):
            parts = text.split()
            if len(parts) == 2:
                try:
                    new_timeout = int(parts[1])
                    self.config.timeout = new_timeout
                    self.config.save()
                    print_success(f"Timeout set to {new_timeout}s")
                except ValueError:
                    print_error("Usage: /timeout <seconds>")
            else:
                print_info(f"Current timeout: {self.config.timeout}s")
            return

        # Built-in commands (agent round-trip with structured metadata)
        if text.startswith("/"):
            cmd = find_command(text)
            if cmd:
                self._send_and_display(cmd.agent_command, cmd.cmd_type, cmd.metadata)
            else:
                print_error(f"Unknown command: {text.split()[0]}. Type /help for commands.")
            return

        # Free-form query
        self._send_and_display(text)

    # ── Send & Display ─────────────────────────────────────────────────────

    def _send_and_display(
        self,
        command: str,
        cmd_type: str = "query",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Send command to agent and display response with a spinner."""
        if not self.client.is_connected:
            print_error("Not connected. Reconnecting…")
            if not self._connect():
                return

        # Show what we're sending (only for free-form, not built-in commands)
        # print_you(command, self.config.show_timestamps)

        # Send
        self.client.send_command(command, cmd_type, metadata)

        # Wait with spinner
        response = None
        spinner_text = "gabs is thinking…"

        with Live(
            Spinner("dots", text=f"[dim cyan]{spinner_text}[/dim cyan]"),
            console=console,
            transient=True,
        ) as live:
            start = time.monotonic()
            while time.monotonic() - start < self.config.timeout:
                if self.client._response_event.wait(timeout=0.1):
                    response = self.client._response
                    break
                elapsed = int(time.monotonic() - start)
                if elapsed > 5:
                    live.update(
                        Spinner("dots", text=f"[dim cyan]{spinner_text} ({elapsed}s)[/dim cyan]")
                    )

        if response is None:
            print_warn(f"No response after {self.config.timeout}s. Gabs might be offline.")
            print_info("Your command was queued — it'll be processed when the listener runs.")
            return

        # Display response
        text = response.get("text", response.get("response", str(response)))
        title = response.get("title")

        if title:
            print_gabs_panel(title, text)
        else:
            print_gabs(text, self.config.show_timestamps)

    # ── Connection ─────────────────────────────────────────────────────────

    def _connect(self) -> bool:
        """Verify GitHub API access."""
        console.print("[gabs.muted]🔌 connecting…[/gabs.muted]", end="\r")
        ok = self.client.connect()
        if ok:
            console.print("[gabs.success]✓[/gabs.success] [gabs.muted]connected to GitHub[/gabs.muted]          ")
            return True
        else:
            print_error("Could not connect to GitHub — check your token with /config")
            print_info("Run [bold]gabs setup[/bold] to reconfigure.")
            return False

    def _disconnect(self) -> None:
        self.client.disconnect()

    # ── Status ─────────────────────────────────────────────────────────────

    def _show_status(self) -> None:
        status = "🟢 connected" if self.client.is_connected else "🔴 disconnected"
        print_gabs_panel("Status", f"""
**Connection:** {status}
**GitHub repo:** `{self.config.github_repo}`
**Namespace:** `{self.config.namespace}`
**ntfy.sh topic:** `{self.config.ntfy_res_topic}`
**Timeout:** {self.config.timeout}s
**History:** `{HISTORY_FILE}`
""")

    # ── Signal Handling ────────────────────────────────────────────────────

    def _handle_interrupt(self, signum: int, frame: Any) -> None:
        console.print()
        print_info("Press Ctrl-D or type /quit to exit.")
