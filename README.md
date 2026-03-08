# FACEPALM

**Crosscheck OpenClaw console logs with chat history to troubleshoot issues intelligently.**

## Quick start

```bash
# Install from GitHub
git clone https://github.com/RuneweaverStudios/FACEPALM.git
cp -r FACEPALM ~/.openclaw/workspace/skills/

# Or install via ClawHub
clawhub install FACEPALM

# Run with defaults
python3 ~/.openclaw/workspace/skills/FACEPALM/scripts/facepalm.py

# Analyze last 10 minutes, JSON output
python3 ~/.openclaw/workspace/skills/FACEPALM/scripts/facepalm.py --minutes 10 --json

# Use a different model
python3 ~/.openclaw/workspace/skills/FACEPALM/scripts/facepalm.py --model openrouter/anthropic/claude-sonnet-4
```

## What it does

FACEPALM reads your OpenClaw gateway log and recent chat history, then sends the combined context to an LLM for intelligent root-cause analysis. It returns actionable diagnosis with specific errors found and recommended fixes.

## Requirements

- OpenClaw with `gateway.log` and session transcripts
- OpenRouter API key configured in OpenClaw platform settings
- `openclaw` CLI on PATH

## Configuration

Edit `config.json` to customize behavior:

```json
{
  "time_window_minutes": 5,
  "model": "openrouter/openai/gpt-4o",
  "log_paths": {
    "gateway_log": "${OPENCLAW_HOME}/logs/gateway.log",
    "sessions_json": "${OPENCLAW_HOME}/agents/main/sessions/sessions.json",
    "sessions_dir": "${OPENCLAW_HOME}/agents/main/sessions"
  }
}
```

All paths support `${OPENCLAW_HOME}` placeholder expansion. See `SKILL.md` for the full configuration reference and detailed documentation.

## Integration

FACEPALM can be called from other skills or automation pipelines:

```bash
# Machine-readable output for integration
python3 scripts/facepalm.py --minutes 5 --json
```

## Related skills

- **[Agent Swarm](https://github.com/RuneweaverStudios/agent-swarm-openclaw-skill)** - Can automatically invoke FACEPALM when troubleshooting loops are detected
- **[gateway-guard](https://github.com/RuneweaverStudios/gateway-guard)** - Keeps gateway auth stable
- **[what-just-happened](https://github.com/RuneweaverStudios/what-just-happened)** - Summarizes gateway restarts

## License

MIT
