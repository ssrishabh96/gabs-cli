"""Terminal display helpers — Rich-powered formatting for gabs CLI."""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich import box

# ── Theme ──────────────────────────────────────────────────────────────────────

GABS_THEME = Theme({
    "gabs.accent":   "bold cyan",
    "gabs.you":      "bold green",
    "gabs.gabs":     "bold cyan",
    "gabs.muted":    "dim white",
    "gabs.error":    "bold red",
    "gabs.warn":     "bold yellow",
    "gabs.success":  "bold green",
    "gabs.info":     "bold blue",
    "gabs.header":   "bold magenta",
    "gabs.cmd":      "bold white",
    "gabs.ts":       "dim cyan",
})

console = Console(theme=GABS_THEME)


# ── Banners ────────────────────────────────────────────────────────────────────

LOGO = r"""[bold cyan]
   ██████   █████  ██████  ███████
  ██       ██   ██ ██   ██ ██
  ██   ███ ███████ ██████  ███████
  ██    ██ ██   ██ ██   ██      ██
   ██████  ██   ██ ██████  ███████
[/bold cyan]"""

LOGO_MINI = "[bold cyan]⚡ gabs[/bold cyan]"


def print_banner(version: str = "1.1.0") -> None:
    """Print the startup banner."""
    console.print(LOGO)
    console.print(
        f"  [gabs.muted]v{version} — Talk to Gabs from your terminal[/gabs.muted]"
    )
    console.print(
        "  [gabs.muted]Type [bold]/help[/bold] for commands, [bold]/quit[/bold] to exit[/gabs.muted]"
    )
    console.print()


def print_mini_banner() -> None:
    console.print(f"{LOGO_MINI} [gabs.muted]connected[/gabs.muted]")


# ── Messages ───────────────────────────────────────────────────────────────────

def print_you(text: str, show_ts: bool = True) -> None:
    ts = _ts() if show_ts else ""
    console.print(f"{ts}[gabs.you]you →[/gabs.you] {text}")


def print_gabs(text: str, show_ts: bool = True) -> None:
    ts = _ts() if show_ts else ""
    console.print()
    console.print(f"{ts}[gabs.gabs]gabs →[/gabs.gabs]")
    try:
        console.print(Markdown(text), width=min(console.width, 100))
    except Exception:
        console.print(text)
    console.print()


def print_gabs_panel(title: str, body: str) -> None:
    console.print()
    panel = Panel(
        Markdown(body),
        title=f"[gabs.accent]{title}[/gabs.accent]",
        border_style="cyan",
        box=box.ROUNDED,
        width=min(console.width, 100),
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


def print_table(title: str, headers: list[str], rows: list[list[str]]) -> None:
    table = Table(
        title=title,
        box=box.SIMPLE_HEAVY,
        title_style="gabs.accent",
        header_style="bold white",
        border_style="dim cyan",
        width=min(console.width, 100),
    )
    for h in headers:
        table.add_column(h)
    for row in rows:
        table.add_row(*row)
    console.print()
    console.print(table)
    console.print()


# ── Status / Feedback ─────────────────────────────────────────────────────────

def print_error(msg: str) -> None:
    console.print(f"[gabs.error]✗[/gabs.error] {msg}")


def print_warn(msg: str) -> None:
    console.print(f"[gabs.warn]⚠[/gabs.warn] {msg}")


def print_success(msg: str) -> None:
    console.print(f"[gabs.success]✓[/gabs.success] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[gabs.info]ℹ[/gabs.info] {msg}")


def print_connecting() -> None:
    console.print("[gabs.muted]🔌 connecting…[/gabs.muted]", end="\r")


def print_config(data: dict[str, Any]) -> None:
    lines = []
    for key, val in data.items():
        if isinstance(val, dict):
            lines.append(f"**{key}:**")
            for k2, v2 in val.items():
                lines.append(f"  {k2}: `{v2}`")
        else:
            lines.append(f"**{key}:** `{val}`")
    print_gabs_panel("⚙ Configuration", "\n".join(lines))


def print_help() -> None:
    help_text = """
**Built-in Commands**

| Command | Alias | Description |
|---------|-------|-------------|
| `/market` | `/m` | Watchlist snapshot |
| `/signals` | `/s` | Trading signals (Arete + KayKim) |
| `/blogs` | `/b` | Latest engineering blogs |
| `/deals` | `/d` | Active deal alerts |
| `/jobs` | `/j` | Latest job listings |
| `/spaces` | `/sp` | List all Spaces |
| `/forge` | `/f` | The Forge — resilience log |
| `/immigration` | `/imm` | Immigration tracker |
| `/hermes` | `/hm` | Hermes Agent handoff status |

**Meta Commands**

| Command | Alias | Description |
|---------|-------|-------------|
| `/help` | `/h`, `/?` | Show this help |
| `/status` | `/st` | Connection status |
| `/config` | `/c` | Show configuration |
| `/timeout N` | | Set response timeout |
| `/clear` | `/cl` | Clear screen |
| `/quit` | `/q`, `/exit` | Exit gabs |

**Tips**
- Add text after any command: `/market how's Monday looking?`
- Free-form: just type anything for a full agent response
- One-shot: `gabs "your question"` from your shell
- Hermes: `gabs hermes install` to set up the Hermes Agent bridge
"""
    print_gabs_panel("Help", help_text)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ts() -> str:
    return f"[gabs.ts]{time.strftime('%H:%M')}[/gabs.ts] "


def clear_screen() -> None:
    console.clear()
