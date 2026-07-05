"""CLI entry point for gabs — Click-based with subcommands.

Usage:
    gabs                        # Interactive REPL
    gabs "what's my watchlist"  # One-shot query
    gabs market                 # Built-in command shortcut
    gabs setup                  # First-run configuration
    gabs config                 # Show configuration
    gabs status                 # Connection status
"""

from __future__ import annotations

import sys
import time
import json

import click

from . import __version__
from .config import Config
from .client import GabsClient
from .commands import find_command, COMMANDS
from .display import (
    console,
    print_banner,
    print_gabs,
    print_gabs_panel,
    print_error,
    print_success,
    print_info,
    print_warn,
    print_config,
)

# ── Shared Config ──────────────────────────────────────────────────────────────

def _ensure_config() -> Config:
    """Load config, running setup if needed."""
    config = Config()
    if not config.is_configured():
        click.echo("First run detected — running setup…\n")
        _do_setup(config)
    return config


def _do_setup(config: Config) -> None:
    """Interactive first-run setup."""
    from .display import LOGO
    console.print(LOGO)
    console.print("[bold]Welcome to gabs CLI[/bold] — let's get you connected.\n")

    # Generate namespace
    ns = config.generate_namespace()
    console.print(f"[gabs.success]✓[/gabs.success] Generated namespace: [bold cyan]{ns}[/bold cyan]")

    # GitHub auth
    console.print()
    console.print("[gabs.muted]Transport: GitHub API (private repo) + ntfy.sh (notifications)[/gabs.muted]")
    console.print()

    # Try to detect gh CLI token first
    detected_token = config._try_gh_cli_token()
    if detected_token:
        console.print(f"[gabs.success]✓[/gabs.success] Found GitHub token from [bold]gh[/bold] CLI")
        use_it = click.confirm("  Use this token?", default=True)
        if use_it:
            config.github_token = detected_token
        else:
            detected_token = None

    if not detected_token:
        console.print("[gabs.muted]  Need a GitHub PAT with repo scope for ssrishabh96/hatch-backup[/gabs.muted]")
        console.print("[gabs.muted]  Create one at: https://github.com/settings/tokens[/gabs.muted]")
        token = click.prompt("  GitHub token", hide_input=True)
        config.github_token = token

    repo = click.prompt(
        "  GitHub repo",
        default=config.github_repo,
        show_default=True,
    )
    config._data["github"]["repo"] = repo
    config.save()

    # Verify connection
    from .client import GabsClient
    client = GabsClient(config)
    console.print("[gabs.muted]  Verifying GitHub access…[/gabs.muted]", end="\r")
    if client.connect():
        print_success("GitHub connection verified                ")
    else:
        print_warn("Could not reach GitHub — check your token and try again")

    console.print()
    print_success("Setup complete!")
    console.print()
    console.print("[gabs.muted]Config saved at ~/.gabs/config.yaml (chmod 600)[/gabs.muted]")
    console.print(f"[gabs.muted]Namespace: [bold]{ns}[/bold][/gabs.muted]")
    console.print()


# ── One-shot query ─────────────────────────────────────────────────────────────

def _oneshot(query: str, config: Config) -> None:
    """Send a single query and print the response."""
    from rich.live import Live
    from rich.spinner import Spinner

    client = GabsClient(config)

    # Connect
    if not client.connect():
        print_error(f"Could not connect to {config.broker_host}:{config.broker_port}")
        sys.exit(1)

    try:
        # Check if it's a built-in command
        cmd = find_command(query)
        if cmd:
            client.send_command(cmd.agent_command, cmd.cmd_type, cmd.metadata)
        else:
            client.send_command(query)

        # Wait with spinner
        with Live(
            Spinner("dots", text="[dim cyan]gabs is thinking…[/dim cyan]"),
            console=console,
            transient=True,
        ) as live:
            response = client.wait_for_response()

        if response is None:
            print_warn("No response yet — your command was queued for when Gabs is online.")
            sys.exit(0)

        text = response.get("text", response.get("response", str(response)))
        title = response.get("title")

        if title:
            print_gabs_panel(title, text)
        else:
            print_gabs(text, show_ts=False)

    finally:
        client.disconnect()


# ── Click CLI ──────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.argument("query", nargs=-1, required=False)
@click.option("--compact", "-c", is_flag=True, help="Compact mode (no banner)")
@click.option("--version", "-v", is_flag=True, help="Show version")
@click.pass_context
def main(ctx: click.Context, query: tuple[str, ...], compact: bool, version: bool) -> None:
    """Talk to Gabs from your terminal.

    \b
    Examples:
        gabs                          # Interactive chat
        gabs "what's my watchlist"    # One-shot query
        gabs market                   # Built-in shortcut
        gabs --compact                # Compact REPL
    """
    if version:
        click.echo(f"gabs-cli v{__version__}")
        return

    # If a subcommand was invoked, let Click handle it
    if ctx.invoked_subcommand:
        return

    config = _ensure_config()

    # One-shot mode: gabs "query" or gabs market
    if query:
        full_query = " ".join(query)
        _oneshot(full_query, config)
        return

    # Interactive REPL
    from .repl import Repl
    repl = Repl(config, compact=compact)
    repl.run()


@main.command()
def setup():
    """Run or re-run first-time setup."""
    config = Config()
    _do_setup(config)


@main.command()
def config():
    """Show current configuration."""
    cfg = _ensure_config()
    print_config(cfg.as_dict())


@main.command()
def status():
    """Check connection status."""
    cfg = _ensure_config()
    client = GabsClient(cfg)

    print_info(f"Connecting to {cfg.broker_host}:{cfg.broker_port}…")

    if client.connect(timeout=5):
        print_success("Connected ✓")
        print_info(f"Namespace: {cfg.namespace}")
        print_info(f"Command topic: {cfg.cmd_topic}")
        print_info(f"Response topic: {cfg.res_topic}")
        client.disconnect()
    else:
        print_error("Could not connect to broker")


# Dynamic subcommands for built-in shortcuts
for _cmd in COMMANDS:
    def _make_handler(cmd=_cmd):
        @main.command(name=cmd.name, help=cmd.description)
        def handler():
            cfg = _ensure_config()
            _oneshot(cmd.name, cfg)
        return handler
    _make_handler()


if __name__ == "__main__":
    main()
