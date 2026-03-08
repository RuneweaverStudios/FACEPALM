#!/usr/bin/env python3
"""
FACEPALM -- Crosscheck OpenClaw console logs with chat history and use an LLM to troubleshoot.

Usage:
  python3 facepalm.py [--minutes N] [--json] [--model MODEL_ID]

All defaults are loaded from config.json in the skill root directory.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"

# ---------------------------------------------------------------------------
# Config loading with ${OPENCLAW_HOME} expansion
# ---------------------------------------------------------------------------

def _expand_path(value: str) -> str:
    """Expand ${OPENCLAW_HOME} and ${SKILL_DIR} placeholders."""
    if not isinstance(value, str):
        return value
    openclaw_home = os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw"))
    value = value.replace("${OPENCLAW_HOME}", openclaw_home)
    value = value.replace("${SKILL_DIR}", str(SKILL_DIR))
    return value


def load_config() -> dict:
    """Load config.json with defaults."""
    defaults = {
        "time_window_minutes": 5,
        "model": "openrouter/openai/gpt-4o",
        "log_paths": {
            "gateway_log": "${OPENCLAW_HOME}/logs/gateway.log",
            "sessions_json": "${OPENCLAW_HOME}/agents/main/sessions/sessions.json",
            "sessions_dir": "${OPENCLAW_HOME}/agents/main/sessions",
        },
        "max_log_lines": 200,
        "max_chat_messages": 100,
        "cli_timeout_seconds": 130,
        "agent_timeout_ms": 120000,
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                user = json.load(f)
            # Merge log_paths
            if "log_paths" in user:
                defaults["log_paths"].update(user.pop("log_paths"))
            defaults.update(user)
        except (json.JSONDecodeError, OSError):
            pass
    # Expand paths
    for key in defaults["log_paths"]:
        defaults["log_paths"][key] = _expand_path(defaults["log_paths"][key])
    return defaults


CONFIG = load_config()

GATEWAY_LOG = Path(CONFIG["log_paths"]["gateway_log"])
SESSIONS_JSON = Path(CONFIG["log_paths"]["sessions_json"])
SESSIONS_DIR = Path(CONFIG["log_paths"]["sessions_dir"])
DEFAULT_MODEL = CONFIG["model"]


def parse_iso_ts(line: str):
    """Extract ISO timestamp from log line; return None if not found."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)", line.strip())
    if m:
        s = m.group(1).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return None


def read_tail(path: Path, max_lines: int = 500) -> list[str]:
    """Read last N lines from a file."""
    if not path.exists():
        return []
    with open(path, "r") as f:
        lines = f.readlines()
    return lines[-max_lines:] if len(lines) > max_lines else lines


def get_recent_logs(minutes: int) -> list[str]:
    """Get gateway.log lines from the last N minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    recent_lines = []

    if not GATEWAY_LOG.exists():
        return recent_lines

    for line in read_tail(GATEWAY_LOG, 1000):
        ts = parse_iso_ts(line)
        if ts and ts >= cutoff:
            recent_lines.append(line.strip())
        elif not ts:
            recent_lines.append(line.strip())

    max_lines = CONFIG.get("max_log_lines", 200)
    return recent_lines[-max_lines:]


def get_recent_chat_history(minutes: int) -> list[dict]:
    """Get chat history from active session transcripts in the last N minutes."""
    cutoff_ms = int((datetime.now(timezone.utc) - timedelta(minutes=minutes)).timestamp() * 1000)
    chat_messages = []

    if not SESSIONS_JSON.exists():
        return chat_messages

    try:
        with open(SESSIONS_JSON, "r") as f:
            sessions = json.load(f)
    except (json.JSONDecodeError, OSError):
        return chat_messages

    # Find the main session
    main_session = None
    for key, session in sessions.items():
        if key == "agent:main" or (isinstance(key, str) and "main" in key.lower()):
            main_session = session
            break

    if not main_session:
        sessions_list = [(k, v) for k, v in sessions.items() if isinstance(v, dict)]
        if sessions_list:
            main_session = max(sessions_list, key=lambda x: x[1].get("updatedAt", 0))[1]

    if not main_session:
        return chat_messages

    session_id = main_session.get("id")
    if not session_id:
        return chat_messages

    transcript_path = SESSIONS_DIR / f"{session_id}.jsonl"
    if not transcript_path.exists():
        return chat_messages

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    timestamp = event.get("timestamp") or event.get("createdAt") or event.get("time")
                    if timestamp:
                        if isinstance(timestamp, str):
                            try:
                                ts_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                                ts_ms = int(ts_dt.timestamp() * 1000)
                            except Exception:
                                continue
                        else:
                            ts_ms = int(timestamp) if timestamp > 1000000000000 else int(timestamp * 1000)

                        if ts_ms >= cutoff_ms:
                            chat_messages.append(event)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass

    max_messages = CONFIG.get("max_chat_messages", 100)
    return chat_messages[-max_messages:]


def format_context(logs: list[str], chat_history: list[dict], minutes: int) -> str:
    """Format logs and chat history into a prompt for the LLM."""
    context_parts = []

    context_parts.append(f"=== OpenClaw Console Logs (Last {minutes} minutes) ===\n")
    context_parts.append("\n".join(logs[-100:]))

    context_parts.append(f"\n\n=== Chat History (Last {minutes} minutes) ===\n")
    for msg in chat_history[-50:]:
        role = msg.get("role", "unknown")
        content = msg.get("content", msg.get("text", ""))
        if content:
            context_parts.append(f"[{role}]: {content}")

    context_parts.append("\n\n=== Troubleshooting Request ===\n")
    context_parts.append("Analyze the console logs and chat history above. Identify any errors, issues, or troubleshooting loops.")
    context_parts.append("Provide:")
    context_parts.append("1. Root cause analysis")
    context_parts.append("2. Specific errors found")
    context_parts.append("3. Recommended fixes")
    context_parts.append("4. Steps to resolve the issue")

    return "\n".join(context_parts)


def invoke_llm(prompt: str, model: str) -> str:
    """Invoke the configured LLM via OpenClaw CLI."""
    timeout_ms = str(CONFIG.get("agent_timeout_ms", 120000))
    cli_timeout = CONFIG.get("cli_timeout_seconds", 130)
    try:
        cmd = [
            "openclaw", "agent", "--message", prompt,
            "--model", model,
            "--deliver",
            "--timeout-ms", timeout_ms,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=cli_timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error invoking LLM: {result.stderr or 'Unknown error'}"
    except subprocess.TimeoutExpired:
        return "Error: LLM invocation timed out"
    except FileNotFoundError:
        return "Error: openclaw CLI not found in PATH"
    except Exception as e:
        return f"Error invoking LLM: {str(e)}"


def troubleshoot(minutes: int, model: str, json_out: bool) -> dict:
    """Main troubleshooting function."""
    logs = get_recent_logs(minutes)
    chat_history = get_recent_chat_history(minutes)

    if not logs and not chat_history:
        return {
            "error": f"No logs or chat history found in the last {minutes} minutes",
            "logs_count": 0,
            "chat_messages_count": 0,
        }

    context = format_context(logs, chat_history, minutes)
    diagnosis = invoke_llm(context, model)

    return {
        "logs_count": len(logs),
        "chat_messages_count": len(chat_history),
        "diagnosis": diagnosis,
        "model_used": model,
        "time_window_minutes": minutes,
    }


def main():
    ap = argparse.ArgumentParser(description="FACEPALM -- Crosscheck logs with chat history and troubleshoot")
    ap.add_argument("--minutes", type=int, default=CONFIG["time_window_minutes"], help="Look at last N minutes")
    ap.add_argument("--json", action="store_true", help="Output JSON only")
    ap.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    args = ap.parse_args()

    result = troubleshoot(args.minutes, args.model, args.json)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("FACEPALM Troubleshooting Analysis\n")
        print(f"Analyzed {result.get('logs_count', 0)} log lines and {result.get('chat_messages_count', 0)} chat messages")
        print(f"Model: {result.get('model_used', 'unknown')}\n")
        print("=" * 60)
        print(result.get("diagnosis", "No diagnosis available"))
        print("=" * 60)


if __name__ == "__main__":
    main()
