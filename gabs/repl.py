"""Interactive REPL for gabs CLI.

Full-featured terminal chat with command history, tab completion,
and rich formatting. Uses prompt_toolkit for the input line and
Rich for output rendering.
"""

from __future__ import annotations

import signal
import threading
import time
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.live import Live
from rich.spinner import Spinner

from . import __version__
from .client import GabsClient
from .commands import all_command_names, find_command, extract_command_extra
from .config import Config, HISTORY_FILE, CONFIG_DIR
from .display import (
    console,
    print_banner,
    print_mini_banner,
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

PROMPT_STYLE = Style.from_dict({
    "prompt": "#00d7af bold",
    "arrow":  "#00d7af",
})


class Repl:
    """Interactive gabs REPL session."""

    def __init__(self, config: Config, compact: bool = False) -> None:
        self.config = config
        self.compact = compact
        self.client = GabsClient(config)
        self._running = False

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

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

    def run(self) -> None:
        self._running = True

        if not self._connect():
            return

        if self.compact:
            print_mini_banner()
        else:
            print_banner(__version__)

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
            self.client.disconnect()

    def _handle_input(self, text: str) -> None:
        low = text.lower()

        # ── Local meta commands (no agent round-trip) ──────────────────
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
            self._handle_timeout(text)
            return

        # ── Hermes local commands ──────────────────────────────────────
        if low in ("/hermes", "/hm"):
            self._hermes_status()
            return

        # ── Built-in commands (agent round-trip) ───────────────────────
        if text.startswith("/"):
            cmd = find_command(text)
            if cmd:
                extra = extract_command_extra(text)
                agent_text = (
                    f"{cmd.agent_command} {extra}".strip()
                    if extra
                    else cmd.agent_command
                )
                self._send_and_display(agent_text, cmd.cmd_type, cmd.metadata)
            else:
                print_error(
                    f"Unknown command: {text.split()[0]}. Type /help for commands."
                )
            return

        # ── Free-form query ────────────────────────────────────────────
        self._send_and_display(text)

    def _send_and_display(
        self,
        command: str,
        cmd_type: str = "query",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.client.is_connected:
            print_error("Not connected. Reconnecting…")
            if not self._connect():
                return

        if not self.client.send_command(command, cmd_type, metadata):
            print_error("Failed to send command — check GitHub access.")
            return

        # Poll in background thread
        result_holder: list[dict[str, Any] | None] = [None]

        def _poll():
            result_holder[0] = self.client.wait_for_response()

        poll_thread = threading.Thread(target=_poll, daemon=True)
        poll_thread.start()

        with Live(
            Spinner("dots", text="[dim cyan]gabs is thinking…[/dim cyan]"),
            console=console,
            transient=True,
        ) as live:
            start = time.monotonic()
            while time.monotonic() - start < self.config.timeout:
                poll_thread.join(timeout=0.5)
                if not poll_thread.is_alive():
                    break
                elapsed = int(time.monotonic() - start)
                if elapsed > 5:
                    live.update(
                        Spinner(
                            "dots",
                            text=f"[dim cyan]gabs is thinking… ({elapsed}s)[/dim cyan]",
                        )
                    )

        response = result_holder[0]

        if response is None:
            print_warn(
                f"No response after {self.config.timeout}s. "
                f"Gabs might be offline."
            )
            print_info(
                "Your command was queued — it'll process when the listener runs."
            )
            return

        resp_text = response.get("text", response.get("response", str(response)))
        title = response.get("title")

        if title:
            print_gabs_panel(title, resp_text)
        else:
            print_gabs(resp_text, self.config.show_timestamps)

    def _connect(self) -> bool:
        console.print(
            "[gabs.muted]🔌 connecting…[/gabs.muted]", end="\r"
        )
        if self.client.connect():
            console.print(
                "[gabs.success]✓[/gabs.success] "
                "[gabs.muted]connected to GitHub[/gabs.muted]          "
            )
            return True
        else:
            print_error(
                "Could not connect to GitHub — check your token with /config"
            )
            print_info("Run [bold]gabs setup[/bold] to reconfigure.")
            return False

    def _show_status(self) -> None:
        status = "🟢 connected" if self.client.is_connected else "🔴 disconnected"
        print_gabs_panel(
            "Status",
            f"""
**Connection:** {status}
**GitHub repo:** `{self.config.github_repo}`
**Namespace:** `{self.config.namespace}`
**ntfy topic:** `{self.config.ntfy_res_topic}`
**Timeout:** {self.config.timeout}s
**History:** `{HISTORY_FILE}`
""",
        )

    def _handle_timeout(self, text: str) -> None:
        parts = text.split()
        if len(parts) == 2:
            try:
                val = int(parts[1])
                self.config.timeout = val
                self.config.save()
                print_success(f"Timeout set to {val}s")
            except ValueError:
                print_error("Usage: /timeout <seconds>")
        else:
            print_info(f"Current timeout: {self.config.timeout}s")

    def _hermes_status(self) -> None:
        """Quick Hermes handoff check from the REPL."""
        from .hermes import read_collab, format_collab_status

        content = read_collab(self.client)
        status_text = format_collab_status(content)
        print_gabs_panel("Hermes ↔ Gabs", status_text)

    def _handle_interrupt(self, signum: int, frame: Any) -> None:
        console.print()
        print_info("Press Ctrl-D or type /quit to exit.")
