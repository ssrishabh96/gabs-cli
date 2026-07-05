"""Hermes Agent integration for gabs CLI.

Handles:
- Installing the gabs skill into Hermes (~/.hermes/skills/gabs/SKILL.md)
- Reading/writing COLLAB.md for async handoffs between Gabs and Hermes
- Checking Hermes handoff status
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

HERMES_DIR = Path.home() / ".hermes"
HERMES_SKILLS_DIR = HERMES_DIR / "skills" / "gabs"
COLLAB_PATH = "gabs-collab/COLLAB.md"

# ── Hermes Skill File ──────────────────────────────────────────────────────────

SKILL_MD = '''---
name: gabs
description: Bridge to Gabs — your Hatch AI assistant in the cloud
version: 1.0.0
category: integration
author: gabs-cli
tags: [ai, assistant, cloud, hatch, market-data, automation]
---

# Gabs — Cloud AI Bridge

Gabs is your personal AI assistant running on Hatch (cloud). It has persistent
state, scheduled jobs, live market data, web search, social media access, and
12+ interactive Spaces. Use this skill to delegate cloud tasks to Gabs.

## When to use Gabs (vs doing it locally)

**Delegate to Gabs when you need:**
- Live market data, trading signals, or watchlist snapshots
- Web research or social media search
- Hatch Space actions (stock screener, deal radar, career intelligence, etc.)
- Scheduled/recurring tasks (cron jobs, monitors, alerts)
- Cloud-persistent state (goals, memory, relationship tracking)
- Information that requires internet access from a cloud server

**Handle locally when you need:**
- Local file operations on this Mac
- Running local scripts or builds
- Interacting with local apps
- Tasks that need low latency
- Private computation that shouldn't leave this machine

## How to call Gabs

### Quick command (terminal tool)
```bash
gabs "your question or task here"
```

### Built-in shortcuts
```bash
gabs /market              # Watchlist: META, QQQ, TSLA, SPCX, SMH with signals
gabs /signals             # Arete + KayKim trading signals
gabs /blogs               # Latest engineering blog posts
gabs /deals               # Active deal alerts with AI verdicts
gabs /jobs                # PE/infra job listings (H-1B friendly)
gabs /spaces              # List all active Hatch Spaces
gabs /forge               # Resilience log and streaks
gabs /immigration         # Immigration tracker status
```

### Free-form queries
```bash
gabs "what's the latest on META earnings?"
gabs "search for SpaceX Vandenberg launch schedule"
gabs "add a progress entry to my resilience goal: completed cold plunge"
```

## Response format

Gabs returns markdown-formatted text. Responses typically arrive in 30-75
seconds (30s cron interval + processing time). If Gabs is processing a
complex query, it may take longer.

## Async handoffs via COLLAB.md

For multi-step workflows where both agents contribute, use the shared
COLLAB.md at `gabs-collab/COLLAB.md` in the `ssrishabh96/hatch-backup` repo.

### Reading handoffs
```bash
gabs /hermes              # Check for pending handoffs
```

### Writing a handoff (from Hermes)
To leave a task for Gabs, write to COLLAB.md via git:
```bash
cd ~/hatch-backup  # or wherever you have the repo cloned
git pull
# Edit gabs-collab/COLLAB.md — add an entry under "## Hermes → Gabs"
git add -A && git commit -m "hermes: task for gabs" && git push
```

Or just tell Gabs directly:
```bash
gabs "Hermes finished the local benchmark. Results at ~/projects/results.csv. Please analyze and add to the stock screener."
```

## Gabs capabilities reference

| Capability | Details |
|-----------|---------|
| Market data | Finnhub API (META, QQQ, TSLA, SPCX, SMH), Arete + KayKim signals |
| Spaces (12) | Stock Screener, wawve, BuyItHood, SPCX Tracker, Career Intelligence, Deal Radar, The Forge, Value Learnings, Bay Area Rentals, Immigration Tracker, Reading Companion, Sheep Siege |
| Web search | Full browser + search engine access |
| Social media | Instagram, Facebook, Threads search |
| Goals | Resilience goal, wealth/greatness goal — progress tracking + study briefs |
| Scheduling | Cron jobs, reminders, recurring monitors |
| Memory | Persistent cross-session memory of user context |
| Media | Image/video generation, podcasts, TTS |

## Notes

- Gabs runs on a Linux VM in the cloud — no access to your local Mac filesystem
- Response time is 30-75s due to cron polling interval
- The GitHub repo `ssrishabh96/hatch-backup` is the transport layer
- ntfy.sh provides push notifications for faster wake-up
- All communication is over HTTPS (GitHub API + ntfy.sh)
'''


def is_hermes_installed() -> bool:
    """Check if Hermes Agent is installed on this machine."""
    return HERMES_DIR.exists()


def is_skill_installed() -> bool:
    """Check if the gabs skill is installed in Hermes."""
    skill_file = HERMES_SKILLS_DIR / "SKILL.md"
    return skill_file.exists()


def install_skill() -> tuple[bool, str]:
    """Install the gabs skill into Hermes. Returns (success, message)."""
    if not is_hermes_installed():
        return False, (
            "Hermes Agent not found at ~/.hermes\n"
            "Install it first: curl -fsSL https://raw.githubusercontent.com/"
            "NousResearch/hermes-agent/main/scripts/install.sh | bash"
        )

    try:
        HERMES_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        skill_file = HERMES_SKILLS_DIR / "SKILL.md"
        skill_file.write_text(SKILL_MD)
        return True, f"Skill installed at {skill_file}"
    except Exception as e:
        return False, f"Failed to write skill: {e}"


def uninstall_skill() -> tuple[bool, str]:
    """Remove the gabs skill from Hermes."""
    skill_file = HERMES_SKILLS_DIR / "SKILL.md"
    if skill_file.exists():
        skill_file.unlink()
        try:
            HERMES_SKILLS_DIR.rmdir()
        except OSError:
            pass
        return True, "Skill removed"
    return True, "Skill was not installed"


# ── COLLAB.md ──────────────────────────────────────────────────────────────────

COLLAB_TEMPLATE = """# COLLAB.md — Gabs ↔ Hermes

Async handoff document. Both agents read and write this file via the
`ssrishabh96/hatch-backup` GitHub repo.

**Convention:** Add entries under the appropriate heading. Mark completed
entries with ✅. Clear old entries periodically.

---

## Hermes → Gabs

_Tasks from Hermes for Gabs to handle in the cloud._

<!-- Example:
### [2026-07-04 18:30] Analyze SPX seasonality for July
- **Status:** pending
- **Context:** Running local backtest, need cloud data cross-reference
- **Request:** Pull July seasonality data for SPX from the last 20 years
-->

## Gabs → Hermes

_Tasks from Gabs for Hermes to handle locally._

<!-- Example:
### [2026-07-04 19:00] Run local benchmark script
- **Status:** pending
- **Context:** Market analysis ready, need local compute
- **Request:** Execute ~/projects/backtest/run.py with the latest data
-->

## Shared Context

_Persistent notes both agents should know about._

- **User:** Rishabh Agrawal, PE at Meta, Bay Area
- **Gabs namespace:** Check ~/.gabs/config.yaml
- **Gabs capabilities:** Market data, Spaces, web search, scheduling, goals
- **Hermes capabilities:** Local filesystem, code execution, local apps
"""


def read_collab(client: Any) -> str | None:
    """Read COLLAB.md from the GitHub repo."""
    return client.read_file(COLLAB_PATH)


def write_collab(client: Any, content: str) -> bool:
    """Write COLLAB.md to the GitHub repo."""
    return client.write_file(COLLAB_PATH, content, "gabs: update COLLAB.md")


def init_collab(client: Any) -> tuple[bool, str]:
    """Initialize COLLAB.md if it doesn't exist."""
    existing = client.read_file(COLLAB_PATH)
    if existing:
        return True, "COLLAB.md already exists"
    ok = client.write_file(COLLAB_PATH, COLLAB_TEMPLATE, "gabs: init COLLAB.md")
    if ok:
        return True, "COLLAB.md created"
    return False, "Failed to create COLLAB.md"


def format_collab_status(content: str | None) -> str:
    """Parse COLLAB.md and return a human-readable status summary."""
    if not content:
        return "No COLLAB.md found. Run `gabs hermes init` to create it."

    hermes_to_gabs: list[str] = []
    gabs_to_hermes: list[str] = []

    current_section = None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Hermes → Gabs"):
            current_section = "h2g"
        elif stripped.startswith("## Gabs → Hermes"):
            current_section = "g2h"
        elif stripped.startswith("## "):
            current_section = None
        elif stripped.startswith("### ") and current_section:
            # Check if it's not completed
            if "✅" not in stripped:
                entry = stripped.lstrip("# ").strip()
                if current_section == "h2g":
                    hermes_to_gabs.append(entry)
                elif current_section == "g2h":
                    gabs_to_hermes.append(entry)

    lines = ["**Hermes ↔ Gabs Handoff Status**\n"]

    if hermes_to_gabs:
        lines.append(f"📥 **Hermes → Gabs:** {len(hermes_to_gabs)} pending")
        for entry in hermes_to_gabs:
            lines.append(f"  - {entry}")
    else:
        lines.append("📥 **Hermes → Gabs:** No pending tasks")

    lines.append("")

    if gabs_to_hermes:
        lines.append(f"📤 **Gabs → Hermes:** {len(gabs_to_hermes)} pending")
        for entry in gabs_to_hermes:
            lines.append(f"  - {entry}")
    else:
        lines.append("📤 **Gabs → Hermes:** No pending tasks")

    return "\n".join(lines)
