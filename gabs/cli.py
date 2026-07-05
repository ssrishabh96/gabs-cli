"""CLI entry point for gabs — Click-based with subcommands.

Usage:
    gabs                          # Interactive REPL
    gabs "what's my watchlist"    # One-shot query
    gabs /market                  # Built-in command shortcut
    gabs setup                    # First-run configuration
    gabs hermes install           # Install Hermes Agent bridge
    gabs hermes status            # Check Hermes handoffs
"""

from __future__ import annotations

import sys
import time

import click

from . import __version__
from .config import Config
from .client import GabsClient
from .commands import find_command, extract_command_extra, COMMANDS
from .display import (
    console,
    print_gabs,
    print_gabs_panel,
    print_error,
    print_success,
    print_info,
    print_warn,
    print_config,
)


def _ensure_config() -> Config:
    """Load config, prompting setup if needed."""
    config = Config()
    if not config.is_configured():
        click.echo("First run detected — running setup…\n")
        if not _do_setup(config):
            sys.exit(1)
    return config


def _do_setup(config: Config) -> bool:
    """Interactive first-run setup. Returns True on success."""
    from .display import LOGO
    console.print(LOGO)
    console.print("[bold]Welcome to gabs CLI[/bold] — let's get you connected.\n")

    # Generate namespace
    ns = config.generate_namespace()
    console.print(
        f"[gabs.success]✓[/gabs.success] Generated namespace: [bold cyan]{ns}[/bold cyan]"
    )
    console.print()
    console.print(
        "[gabs.muted]Transport: GitHub API (private repo) + ntfy.sh (notifications)[/gabs.muted]"
    )
    console.print()

    # ── GitHub token ───────────────────────────────────────────────────
    detected_token = config._try_gh_cli_token()
    token = None

    if detected_token:
        console.print(
            "[gabs.success]✓[/gabs.success] Found GitHub token from [bold]gh[/bold] CLI"
        )
        if click.confirm("  Use this token?", default=True):
            token = detected_token

    if not token:
        console.print(
            "[gabs.muted]  Need a GitHub PAT with repo scope for ssrishabh96/hatch-backup[/gabs.muted]"
        )
        console.print(
            "[gabs.muted]  Create one: https://github.com/settings/tokens/new?scopes=repo[/gabs.muted]"
        )
        token = click.prompt("  GitHub token", hide_input=True)

    if not token or len(token) < 10:
        print_error("Token looks invalid. Run `gabs setup` to try again.")
        return False

    config.github_token = token

    # ── GitHub repo ────────────────────────────────────────────────────
    repo = click.prompt(
        "  GitHub repo",
        default=config.github_repo,
        show_default=True,
    )
    # Validate repo format
    if "/" not in repo or len(repo.split("/")) != 2:
        print_error(f"Invalid repo format: '{repo}'. Expected: owner/repo-name")
        return False

    config._data["github"]["repo"] = repo
    config.save()

    # ── Verify read access ─────────────────────────────────────────────
    client = GabsClient(config)
    console.print("[gabs.muted]  Verifying GitHub access…[/gabs.muted]", end="\r")

    if not client.connect():
        print_error(
            "Cannot read repo. Check that the token has `repo` scope "
            "and the repo exists."
        )
        console.print(
            f"[gabs.error]  GitHub API 403[/gabs.error]: "
            f"token may lack `repo` scope for [bold]{repo}[/bold]"
        )
        return False

    print_success("GitHub read access verified                    ")

    # ── Verify write access ────────────────────────────────────────────
    console.print("[gabs.muted]  Verifying write access…[/gabs.muted]", end="\r")
    if not client.verify_write_access():
        print_error(
            "Token can read but NOT write. "
            "Make sure the PAT has full `repo` scope (not just public_repo)."
        )
        return False

    print_success("GitHub write access verified                   ")

    # ── Create namespace dir ───────────────────────────────────────────
    console.print("[gabs.muted]  Creating inbox…[/gabs.muted]", end="\r")
    ok = client.write_file(
        f"gabs-inbox/{ns}/.gitkeep",
        "",
        f"gabs-cli: init namespace {ns}",
    )
    if ok:
        print_success("Inbox created                                  ")
    else:
        print_warn("Could not create inbox dir (may already exist)")

    # ── Done ───────────────────────────────────────────────────────────
    console.print()
    print_success("Setup complete!")
    console.print()
    console.print("[gabs.muted]Config saved at ~/.gabs/config.yaml (chmod 600)[/gabs.muted]")
    console.print(f"[gabs.muted]Namespace: [bold]{ns}[/bold][/gabs.muted]")
    console.print()

    # Offer Hermes setup
    from .hermes import is_hermes_installed
    if is_hermes_installed():
        console.print(
            "[gabs.info]ℹ[/gabs.info] Hermes Agent detected! "
            "Run [bold]gabs hermes install[/bold] to bridge them."
        )
        console.print()

    return True


# ── One-shot ───────────────────────────────────────────────────────────────────

def _oneshot(query: str, config: Config) -> None:
    """Send a single query and print the response."""
    from rich.live import Live
    from rich.spinner import Spinner

    client = GabsClient(config)

    if not client.connect():
        print_error("Could not connect to GitHub — check your token")
        sys.exit(1)

    try:
        # Check if it's a built-in command
        cmd = find_command(query)
        if cmd:
            extra = extract_command_extra(query)
            text = f"{cmd.agent_command} {extra}".strip() if extra else cmd.agent_command
            client.send_command(text, cmd.cmd_type, cmd.metadata)
        else:
            client.send_command(query)

        # Wait with spinner
        with Live(
            Spinner("dots", text="[dim cyan]gabs is thinking…[/dim cyan]"),
            console=console,
            transient=True,
        ):
            response = client.wait_for_response()

        if response is None:
            print_warn(
                "No response yet — your command was queued for when Gabs is online."
            )
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
        gabs /market                  # Built-in shortcut
        gabs hermes install           # Set up Hermes bridge
        gabs --compact                # Compact REPL
    """
    if version:
        click.echo(f"gabs-cli v{__version__}")
        return

    if ctx.invoked_subcommand:
        return

    config = _ensure_config()

    # One-shot mode
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


@main.command(name="config")
def show_config():
    """Show current configuration."""
    cfg = _ensure_config()
    print_config(cfg.as_dict())


@main.command()
def status():
    """Check connection status."""
    cfg = _ensure_config()
    client = GabsClient(cfg)

    print_info("Connecting…")
    if client.connect(timeout=5):
        print_success("Connected to GitHub ✓")
        print_info(f"Namespace: {cfg.namespace}")
        print_info(f"Repo: {cfg.github_repo}")
        print_info(f"ntfy topic: {cfg.ntfy_res_topic}")
        client.disconnect()
    else:
        print_error("Could not connect to GitHub")


# ── Hermes subcommand group ────────────────────────────────────────────────────

@main.group()
def hermes():
    """Hermes Agent integration — bridge Gabs and Hermes."""
    pass


@hermes.command()
def install():
    """Install the gabs skill into Hermes Agent."""
    from .hermes import install_skill, is_hermes_installed

    if not is_hermes_installed():
        print_warn("Hermes Agent not found at ~/.hermes")
        console.print()
        console.print("Install Hermes first:")
        console.print(
            '  [bold]curl -fsSL https://raw.githubusercontent.com/'
            'NousResearch/hermes-agent/main/scripts/install.sh | bash[/bold]'
        )
        console.print()
        console.print("Then run [bold]gabs hermes install[/bold] again.")
        return

    ok, msg = install_skill()
    if ok:
        print_success(msg)
        console.print()
        console.print("[gabs.muted]Hermes can now use gabs as a tool:[/gabs.muted]")
        console.print('  [bold]gabs "your query"[/bold]')
        console.print()
        console.print("[gabs.muted]The skill teaches Hermes when to delegate to Gabs[/gabs.muted]")
        console.print("[gabs.muted]vs handle locally. View it: hermes skill view gabs[/gabs.muted]")
    else:
        print_error(msg)


@hermes.command()
def uninstall():
    """Remove the gabs skill from Hermes Agent."""
    from .hermes import uninstall_skill

    ok, msg = uninstall_skill()
    if ok:
        print_success(msg)
    else:
        print_error(msg)


@hermes.command(name="status")
def hermes_status():
    """Check Hermes handoff queue (COLLAB.md)."""
    from .hermes import read_collab, format_collab_status

    cfg = _ensure_config()
    client = GabsClient(cfg)

    if not client.connect():
        print_error("Could not connect to GitHub")
        return

    content = read_collab(client)
    status_text = format_collab_status(content)
    print_gabs_panel("Hermes ↔ Gabs", status_text)


@hermes.command()
def init():
    """Initialize COLLAB.md for Gabs ↔ Hermes handoffs."""
    from .hermes import init_collab

    cfg = _ensure_config()
    client = GabsClient(cfg)

    if not client.connect():
        print_error("Could not connect to GitHub")
        return

    ok, msg = init_collab(client)
    if ok:
        print_success(msg)
    else:
        print_error(msg)


@hermes.command(name="info")
def hermes_info():
    """Show Hermes integration details."""
    from .hermes import is_hermes_installed, is_skill_installed

    hermes_ok = is_hermes_installed()
    skill_ok = is_skill_installed()

    status_lines = [
        f"**Hermes Agent:** {'🟢 installed' if hermes_ok else '🔴 not found'}",
        f"**Gabs skill:** {'🟢 installed' if skill_ok else '⚪ not installed'}",
        "",
        "**How it works:**",
        "- Hermes runs locally on your Mac with terminal, file I/O, browser",
        "- Gabs runs in the cloud with Spaces, market data, scheduling",
        "- Hermes calls `gabs \"query\"` for cloud tasks",
        "- COLLAB.md in hatch-backup for async handoffs",
        "",
        "**Commands:**",
        "- `gabs hermes install` — install the skill into Hermes",
        "- `gabs hermes status` — check handoff queue",
        "- `gabs hermes init` — create COLLAB.md",
        "- `gabs hermes info` — this screen",
    ]
    print_gabs_panel("Hermes Integration", "\n".join(status_lines))


# ── Dynamic shortcut subcommands ───────────────────────────────────────────────

for _cmd in COMMANDS:
    if _cmd.name == "hermes":
        continue  # hermes is handled by the group above

    def _make_handler(cmd=_cmd):
        @main.command(name=cmd.name, help=cmd.description)
        @click.argument("extra", nargs=-1, required=False)
        def handler(extra: tuple[str, ...]):
            cfg = _ensure_config()
            query = cmd.name
            if extra:
                query += " " + " ".join(extra)
            _oneshot(query, cfg)
        return handler

    _make_handler()


if __name__ == "__main__":
    main()
