"""Built-in command handlers for gabs CLI.

Each command is a shortcut that maps to a specific agent query with
structured metadata so the server-side listener can fast-path it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# ── Command Registry ───────────────────────────────────────────────────────────

@dataclass
class Command:
    name: str
    aliases: list[str]
    description: str
    cmd_type: str           # "query" | "builtin" | "space_action"
    agent_command: str       # What gets sent to the agent
    metadata: dict | None = None


# All built-in commands
COMMANDS: list[Command] = [
    Command(
        name="market",
        aliases=["m"],
        description="Watchlist snapshot (META, QQQ, TSLA, SPCX, SMH)",
        cmd_type="space_action",
        agent_command="Give me a quick watchlist snapshot — current prices, daily change, and Arete+KayKim signals for META, QQQ, TSLA, SPCX, SMH.",
        metadata={"space": "stock-screener", "fast_path": "market_snapshot"},
    ),
    Command(
        name="blogs",
        aliases=["b"],
        description="Latest engineering blogs",
        cmd_type="space_action",
        agent_command="Show me the latest engineering blog posts from Career Intelligence — newest first, with source and relevance.",
        metadata={"space": "career-intelligence", "action": "listEngineeringBlogs"},
    ),
    Command(
        name="deals",
        aliases=["d"],
        description="Active deal alerts",
        cmd_type="space_action",
        agent_command="What active deals do I have in Deal Radar? Show prices, AI verdicts, and any price drops.",
        metadata={"space": "deal-radar-2", "fast_path": "deal_summary"},
    ),
    Command(
        name="jobs",
        aliases=["j"],
        description="Latest job listings",
        cmd_type="space_action",
        agent_command="Show me the latest job listings from Career Intelligence — role, company, location, H-1B sponsorship status.",
        metadata={"space": "career-intelligence", "fast_path": "job_listings"},
    ),
    Command(
        name="signals",
        aliases=["s", "sig"],
        description="Trading signals (Arete + KayKim)",
        cmd_type="space_action",
        agent_command="Give me current Arete and KayKim signals for my watchlist tickers, with confluence status.",
        metadata={"space": "stock-screener", "fast_path": "signals"},
    ),
    Command(
        name="spaces",
        aliases=["sp"],
        description="List all active Spaces",
        cmd_type="builtin",
        agent_command="List all my active Hatch Spaces with a one-line summary of each.",
        metadata={"fast_path": "list_spaces"},
    ),
    Command(
        name="forge",
        aliases=["f"],
        description="The Forge — resilience log",
        cmd_type="space_action",
        agent_command="Show my latest Forge entries — recent reps, streaks, and current challenge.",
        metadata={"space": "the-forge", "fast_path": "forge_summary"},
    ),
    Command(
        name="immigration",
        aliases=["imm", "visa"],
        description="Immigration tracker status",
        cmd_type="space_action",
        agent_command="Give me a quick immigration status update — timeline, upcoming deadlines, any new policy changes.",
        metadata={"space": "india-immigration-tracker", "fast_path": "immigration_status"},
    ),
]


def find_command(name: str) -> Command | None:
    """Look up a command by name or alias (case-insensitive)."""
    name_lower = name.lower().lstrip("/")
    for cmd in COMMANDS:
        if cmd.name == name_lower or name_lower in cmd.aliases:
            return cmd
    return None


def all_command_names() -> list[str]:
    """Return all command names and aliases, prefixed with /."""
    names: list[str] = []
    for cmd in COMMANDS:
        names.append(f"/{cmd.name}")
        for alias in cmd.aliases:
            names.append(f"/{alias}")
    # Add meta-commands
    names.extend(["/help", "/h", "/?", "/status", "/st", "/config", "/c",
                  "/clear", "/cl", "/quit", "/q", "/exit", "/timeout"])
    return sorted(set(names))
