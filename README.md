# gabs CLI

Talk to Gabs from your terminal. Open source, runs on macOS.

## Install

```bash
pip3 install git+https://github.com/ssrishabh96/gabs-cli.git
```

If `gabs` isn't found after install, add Python's bin to your PATH:
```bash
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Setup

```bash
gabs setup
```

You'll need a GitHub Personal Access Token with `repo` scope for the
`ssrishabh96/hatch-backup` private repo. Create one at
[github.com/settings/tokens](https://github.com/settings/tokens/new?scopes=repo).

Or if you have the `gh` CLI installed, gabs auto-detects your token.

## Usage

### Interactive REPL
```bash
gabs          # Full REPL with history, tab completion, Rich output
gabs -c       # Compact mode (no banner)
```

### One-shot
```bash
gabs "how's the market looking?"
gabs /market
gabs /signals
```

### Built-in commands

| Command | Alias | Description |
|---------|-------|-------------|
| `/market` | `/m` | Watchlist snapshot |
| `/signals` | `/s` | Trading signals (Arete + KayKim) |
| `/blogs` | `/b` | Latest engineering blogs |
| `/deals` | `/d` | Active deal alerts |
| `/jobs` | `/j` | Job listings |
| `/spaces` | `/sp` | List all Spaces |
| `/forge` | `/f` | Resilience log |
| `/immigration` | `/imm` | Immigration tracker |
| `/hermes` | `/hm` | Hermes Agent handoff status |
| `/help` | `/h` | Show all commands |

Extra text after a command is passed through:
```bash
gabs "/market how's Monday looking?"
```

## Hermes Agent Integration

Bridge gabs with [Hermes Agent](https://github.com/NousResearch/hermes-agent)
running locally on your Mac.

```bash
# Install the gabs skill into Hermes
gabs hermes install

# Initialize the shared handoff doc
gabs hermes init

# Check handoff status
gabs hermes status

# Integration info
gabs hermes info
```

Once installed, Hermes can call `gabs "query"` as a terminal tool for
cloud tasks (market data, web search, Spaces, scheduling). COLLAB.md
in the hatch-backup repo provides async handoffs between both agents.

## Architecture

```
Mac (local):
  Terminal → gabs CLI → GitHub API (writes command.json)
                       ← GitHub API (reads response.json)
  Hermes Agent → gabs CLI (terminal tool)
               → COLLAB.md (async handoffs)

Cloud (Hatch VM):
  Cron (30s) → listener.py → reads command.json
                            → agent processes with full capabilities
                            → writes response.json + ntfy.sh ping
```

- Transport: GitHub API (HTTPS) + ntfy.sh (open source push)
- Config: `~/.gabs/config.yaml` (chmod 600)
- History: `~/.gabs/history`

## Upgrading

```bash
pip3 install --force-reinstall git+https://github.com/ssrishabh96/gabs-cli.git
```

## License

MIT
