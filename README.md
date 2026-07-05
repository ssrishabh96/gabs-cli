# gabs-cli

Talk to **Gabs** from your terminal. A GitHub-powered CLI that bridges your MacBook to your Hatch AI assistant, with instant ntfy.sh notifications.

```
   ██████   █████  ██████  ███████
  ██       ██   ██ ██   ██ ██
  ██   ███ ███████ ██████  ███████
  ██    ██ ██   ██ ██   ██      ██
   ██████  ██   ██ ██████  ███████
```

## Install

```bash
# One command — pip from GitHub
pip install git+https://github.com/ssrishabh96/gabs-cli.git

# Or clone first
git clone https://github.com/ssrishabh96/gabs-cli.git
cd gabs-cli
pip install .
```

### Shell alias (optional)

`pip install` creates the `gabs` command automatically. If you want a shorter alias:

```bash
echo 'alias g="gabs"' >> ~/.zshrc && source ~/.zshrc
```

## Quick Start

```bash
gabs
```

First run auto-configures everything:

```
   ██████   █████  ██████  ███████
  ██       ██   ██ ██   ██ ██
  ██   ███ ███████ ██████  ███████
  ██    ██ ██   ██ ██   ██      ██
   ██████  ██   ██ ██████  ███████

Welcome to gabs CLI — let's get you connected.

✓ Generated namespace: 24b68cb80f424126
✓ Found GitHub token from gh CLI
  Use this token? [Y/n]: Y
  GitHub repo [ssrishabh96/hatch-backup]:
✓ GitHub connection verified
✓ Setup complete!
```

If you have the `gh` CLI installed and authenticated, gabs auto-detects the token. Otherwise, paste a [GitHub PAT](https://github.com/settings/tokens) with repo scope.

## Usage

### Interactive Chat

```bash
gabs
```

Opens a REPL with history, tab completion, and rich markdown rendering:

```
you → what's happening with META today?

gabs →
META is at $612.91, up 8.8%…

you → /market

gabs →
┌ Watchlist Snapshot ─────────────────────────┐
│ META  $612.91  ▲8.8%  Arete:BUY  KK:NEUTRAL │
│ QQQ   $523.15  ▲1.2%  Arete:BUY  KK:BUY     │
│ …                                             │
└───────────────────────────────────────────────┘
```

### One-Shot Queries

```bash
gabs "what's my watchlist looking like?"
gabs market
gabs blogs
gabs deals
```

### Built-in Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `/market` | `/m` | Watchlist snapshot (META, QQQ, TSLA, SPCX, SMH) |
| `/blogs` | `/b` | Latest engineering blog posts |
| `/deals` | `/d` | Active deal alerts |
| `/jobs` | `/j` | Latest job listings |
| `/signals` | `/s` | Trading signals (Arete + KayKim) |
| `/spaces` | `/sp` | List all active Spaces |
| `/forge` | `/f` | Resilience log from The Forge |
| `/immigration` | `/imm` | Immigration tracker status |
| `/status` | `/st` | Connection status |
| `/config` | `/c` | Show configuration |
| `/timeout N` | — | Set response timeout (seconds) |
| `/help` | `/h`, `/?` | Show help |
| `/clear` | `/cl` | Clear screen |
| `/quit` | `/q`, `/exit` | Exit |

### Subcommands

```bash
gabs setup     # Re-run first-time setup
gabs config    # Show current config
gabs status    # Check GitHub connection
```

## How It Works

```
┌──────────────┐    GitHub API   ┌───────────────┐    git pull     ┌──────────────┐
│  MacBook CLI │ ──────────────► │   GitHub      │ ◄──────────── │  Hatch VM    │
│  (gabs)      │                 │   (private    │ ──────────── ► │  (Gabs)      │
│              │ ◄─── ntfy.sh ── │    repo)      │   git push     │              │
└──────────────┘   notification  └───────────────┘                └──────────────┘
```

1. **You** type a command in `gabs`
2. CLI writes `command.json` to your private GitHub repo via API
3. CLI pings **ntfy.sh** (open source) as a notification
4. **Gabs** (Hatch cron) checks for pending commands every minute
5. Gabs processes the command with full agent capabilities
6. Gabs writes `response.json` to GitHub + pings ntfy.sh
7. **CLI** gets the ntfy notification, reads the response, renders it with Rich

Average latency: **30-60 seconds**. All data travels through your private GitHub repo — nothing on public brokers.

## Configuration

Stored at `~/.gabs/config.yaml` (chmod 600):

```yaml
namespace: 24b68cb80f424126
github:
  repo: ssrishabh96/hatch-backup
  token: ghp_...
ntfy:
  server: https://ntfy.sh
timeout: 120
poll_interval: 3
theme: dark
show_timestamps: true
max_history: 1000
```

## Requirements

- Python 3.10+
- macOS (M1/M2/M3) or Linux
- GitHub account with repo access
- Internet connection

## Dependencies

All pure Python:

- `rich` — terminal formatting & markdown rendering
- `click` — CLI framework
- `prompt-toolkit` — interactive REPL with history & completion
- `pyyaml` — config management

No native extensions. No compiled binaries. Installs in seconds on M1.

## Uninstall

```bash
pip uninstall gabs-cli
rm -rf ~/.gabs
```

## License

MIT — [Rishabh Agrawal](https://github.com/ssrishabh96)
