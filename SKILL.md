---
name: FACEPALM
displayName: FACEPALM
description: Crosscheck OpenClaw console logs with chat history and use an LLM to troubleshoot issues. Config-driven time windows, model selection, and log paths.
version: 1.1.0
---

# FACEPALM

**Crosscheck console logs with chat history to troubleshoot issues intelligently.**

FACEPALM analyzes OpenClaw console logs (`gateway.log`) and chat history from a configurable time window, then uses an LLM (default: GPT-4o via OpenRouter) to diagnose and troubleshoot issues. It can be invoked automatically by Agent Swarm or run manually.

## When to use

- **Automatic:** Invoked by Agent Swarm when a troubleshooting loop is detected (repeated errors, failed attempts)
- **Manual:** Run directly when you need intelligent troubleshooting analysis

## Features

- Reads `gateway.log` from a configurable time window (default: 5 minutes)
- Extracts chat history from active session transcripts
- Crosschecks console errors with chat context
- Uses a configurable LLM model (default: `openrouter/openai/gpt-4o`) for intelligent troubleshooting
- Returns actionable diagnosis with root cause analysis and recommended fixes
- All paths and parameters are config-driven via `config.json`

## Usage

```bash
python3 <skill-dir>/scripts/facepalm.py [--minutes N] [--json] [--model MODEL_ID]
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--minutes N` | Look at last N minutes of logs | `5` (from config) |
| `--json` | Output machine-readable JSON | `false` |
| `--model MODEL_ID` | Override the LLM model | `openrouter/openai/gpt-4o` (from config) |

### Examples

```bash
# Analyze last 5 minutes (uses config defaults)
python3 scripts/facepalm.py

# Analyze last 10 minutes with JSON output
python3 scripts/facepalm.py --minutes 10 --json

# Use a different model
python3 scripts/facepalm.py --model openrouter/anthropic/claude-sonnet-4
```

## Configuration (`config.json`)

All parameters are configurable. Paths support `${OPENCLAW_HOME}` placeholder expansion.

| Key | Description | Default |
|-----|-------------|---------|
| `time_window_minutes` | Default time window for log analysis | `5` |
| `model` | Default LLM model for diagnosis | `openrouter/openai/gpt-4o` |
| `log_paths.gateway_log` | Path to gateway log file | `${OPENCLAW_HOME}/logs/gateway.log` |
| `log_paths.sessions_json` | Path to sessions index | `${OPENCLAW_HOME}/agents/main/sessions/sessions.json` |
| `log_paths.sessions_dir` | Path to session transcript directory | `${OPENCLAW_HOME}/agents/main/sessions` |
| `max_log_lines` | Maximum log lines to include in context | `200` |
| `max_chat_messages` | Maximum chat messages to include | `100` |
| `cli_timeout_seconds` | Subprocess timeout for LLM invocation | `130` |
| `agent_timeout_ms` | OpenClaw agent timeout in milliseconds | `120000` |

## How it works

1. **Log collection:** Reads the gateway log and filters lines from the last N minutes
2. **Chat history extraction:** Finds the main session and reads its transcript (`.jsonl` file) for recent messages
3. **Context formatting:** Combines logs and chat history into a structured prompt
4. **LLM invocation:** Uses `openclaw agent --message <prompt> --model <model> --deliver`
5. **Diagnosis return:** Returns structured diagnosis with root cause, errors found, fixes, and resolution steps

## Output format

**Human-readable:**
```
FACEPALM Troubleshooting Analysis

Analyzed 45 log lines and 12 chat messages
Model: openrouter/openai/gpt-4o

============================================================
[LLM diagnosis here]
============================================================
```

**JSON (`--json`):**
```json
{
  "logs_count": 45,
  "chat_messages_count": 12,
  "diagnosis": "[LLM diagnosis]",
  "model_used": "openrouter/openai/gpt-4o",
  "time_window_minutes": 5
}
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (no logs found, LLM failure, etc.) |

## Requirements

- **OpenClaw** with `gateway.log` and session transcripts
- **OpenRouter API key** configured in OpenClaw platform settings
- **`openclaw` CLI** on PATH

## Links

- **GitHub:** https://github.com/RuneweaverStudios/FACEPALM
- **Related:** [Agent Swarm](https://github.com/RuneweaverStudios/agent-swarm-openclaw-skill) - Can automatically invoke FACEPALM
