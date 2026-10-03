"""All interaction with the locally-authenticated Claude Code CLI.

No Anthropic API key is used or required anywhere in this file. Every
subprocess call strips ANTHROPIC_API_KEY from its environment so an
accidentally-configured key on the machine is never picked up.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Optional, Tuple

from pydantic import ValidationError

import prompts
from schemas import JobRequirements, CandidateAssessment

CLAUDE_BIN = "claude"
DEFAULT_TIMEOUT = 120
NOT_AUTHENTICATED_MSG = (
    "Claude Code is not installed or authenticated. Open Terminal and run "
    "`claude` first."
)

# This app only ever needs a plain text/JSON answer -- it must never let
# Claude Code read/write files or run shell commands on this machine, and a
# non-interactive call has no terminal to show a permission prompt on
# anyway. Disallowing every built-in tool guarantees each call is auto-
# denied (never silently stuck waiting on a prompt that can't appear).
DISALLOWED_TOOLS = (
    "Bash,Edit,Write,Read,Glob,Grep,WebSearch,WebFetch,NotebookEdit,Task"
)


def _clean_env() -> dict:
    """A copy of the current environment with ANTHROPIC_API_KEY removed."""
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def check_claude() -> Tuple[bool, str]:
    """Checks `claude --version`. Returns (ok, message)."""
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_clean_env(),
        )
        if result.returncode == 0:
            return True, (result.stdout or "").strip() or "claude CLI detected"
        return False, (result.stderr or "").strip() or NOT_AUTHENTICATED_MSG
    except FileNotFoundError:
        return False, NOT_AUTHENTICATED_MSG
    except subprocess.TimeoutExpired:
        return False, f"Timed out checking Claude Code. {NOT_AUTHENTICATED_MSG}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Could not check Claude Code: {exc}"


def _extract_json(raw: str) -> Optional[str]:
    """Pull the first {...} JSON object out of a CLI response, tolerating
    stray markdown fences or commentary around it."""
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def run_claude(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, str]:
    """Runs `claude -p <prompt>` (with all tool use disallowed) and returns
    (ok, stdout_or_error_message)."""
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--disallowedTools", DISALLOWED_TOOLS],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_clean_env(),
        )
    except subprocess.TimeoutExpired:
        return False, "Claude Code timed out for this request."
    except FileNotFoundError:
        return False, NOT_AUTHENTICATED_MSG
    except Exception as exc:  # noqa: BLE001
        return False, f"Claude Code call failed: {exc}"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or "no output on stdout or stderr"
        return False, f"Claude Code exited with code {result.returncode}: {detail}"

    return True, result.stdout


def _call_and_validate(prompt: str, model_cls, timeout: int = DEFAULT_TIMEOUT):
    """Runs a prompt, validates the JSON against model_cls, retries once
    on invalid JSON. Returns (model_instance_or_None, error_message_or_None)."""
    ok, raw = run_claude(prompt, timeout=timeout)
    if not ok:
        return None, raw

    json_str = _extract_json(raw)
    if json_str is not None:
        try:
            data = json.loads(json_str)
            return model_cls.model_validate(data), None
        except (json.JSONDecodeError, ValidationError) as exc:
            first_error = str(exc)
        except Exception as exc:  # noqa: BLE001
            first_error = str(exc)
    else:
        first_error = "No JSON object found in the response."

    # Retry exactly once, explicitly telling Claude the previous response
    # was invalid.
    retry_prompt = f"{prompt}\n\n{prompts.RETRY_NOTICE}"
    ok2, raw2 = run_claude(retry_prompt, timeout=timeout)
    if not ok2:
        return None, raw2

    json_str2 = _extract_json(raw2)
    if json_str2 is None:
        return None, f"Invalid JSON after retry. First error: {first_error}"
    try:
        data2 = json.loads(json_str2)
        return model_cls.model_validate(data2), None
    except (json.JSONDecodeError, ValidationError) as exc:
        return None, f"Invalid JSON after retry: {exc}"
    except Exception as exc:  # noqa: BLE001
        return None, f"Unexpected error validating retry response: {exc}"


def analyse_job_description(jd_text: str) -> Tuple[Optional[JobRequirements], Optional[str]]:
    prompt = prompts.build_jd_prompt(jd_text)
    return _call_and_validate(prompt, JobRequirements)


def analyse_candidate(
    jd: JobRequirements, cv_text: str, jd_raw_text: str = ""
) -> Tuple[Optional[CandidateAssessment], Optional[str]]:
    prompt = prompts.build_cv_prompt(jd, cv_text, jd_raw_text)
    return _call_and_validate(prompt, CandidateAssessment)