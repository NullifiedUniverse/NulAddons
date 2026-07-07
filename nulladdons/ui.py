"""
Null's Addons -- tiny terminal UI toolkit (colour + prompts).

Keeps the onboarding wizard and diagnostics friendly and readable without any
third-party dependency.  Colour auto-disables when output is piped, when
``NO_COLOR`` is set, or on a dumb terminal, so it never corrupts logs or
Discord posts.  Every prompt is EOF-safe: piped/exhausted input falls back to
the supplied default instead of crashing, which keeps non-interactive runs sane.
"""

from __future__ import annotations

import getpass
import os
import sys

_CODES = {
    "reset": "0", "bold": "1", "dim": "2",
    "red": "31", "green": "32", "yellow": "33", "blue": "34",
    "magenta": "35", "cyan": "36", "grey": "90",
}


def color_enabled() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def c(text: str, *styles: str) -> str:
    """Wrap ``text`` in ANSI styles when colour is enabled, else return as-is."""
    if not styles or not color_enabled():
        return text
    seq = "".join(f"\033[{_CODES[s]}m" for s in styles if s in _CODES)
    return f"{seq}{text}\033[0m"


# --- output markers ---------------------------------------------------------

def banner(title: str, subtitle: str = "") -> None:
    line = "═" * max(len(title) + 4, 40)
    print(c(line, "cyan"))
    print(c(f"  {title}", "cyan", "bold"))
    if subtitle:
        print(c(f"  {subtitle}", "grey"))
    print(c(line, "cyan"))


def section(title: str) -> None:
    print("\n" + c(f"── {title} ──", "bold"))


def ok(msg: str) -> None:
    print(f"  {c('✓', 'green')} {msg}")


def warn(msg: str) -> None:
    print(f"  {c('!', 'yellow')} {msg}")


def err(msg: str) -> None:
    print(f"  {c('✗', 'red')} {msg}")


def info(msg: str) -> None:
    print(f"  {c('·', 'grey')} {msg}")


# --- prompts ----------------------------------------------------------------

def _read(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def ask(label: str, default: str | None = None) -> str:
    hint = f" [{default}]" if default not in (None, "") else ""
    raw = _read(c(f"› {label}{hint}: ", "bold")).strip()
    return raw or (default or "")


def ask_secret(label: str, default: str | None = None) -> str:
    hint = " [keep current]" if default else ""
    try:
        raw = getpass.getpass(f"› {label}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raw = ""
    except Exception:
        raw = _read(f"› {label}{hint}: ").strip()
    return raw or (default or "")


def ask_yes_no(label: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = _read(c(f"› {label} {suffix}: ", "bold")).strip().lower()
    if not raw:
        return default
    return raw[0] == "y"


def ask_int(label: str, default: int = 0) -> int:
    raw = ask(label, str(default))
    raw = raw.replace(",", "").replace("_", "").strip().lower()
    mult = 1
    if raw.endswith("b"):
        mult, raw = 1_000_000_000, raw[:-1]
    elif raw.endswith("m"):
        mult, raw = 1_000_000, raw[:-1]
    elif raw.endswith("k"):
        mult, raw = 1_000, raw[:-1]
    try:
        return int(float(raw) * mult)
    except (TypeError, ValueError):
        return default


def ask_choice(label: str, choices: list[str], default: str) -> str:
    opts = "/".join(c(ch, "bold") if ch == default else ch for ch in choices)
    while True:
        raw = _read(c(f"› {label} ({opts}): ", "bold")).strip().lower()
        if not raw:
            return default
        matches = [ch for ch in choices if ch.lower().startswith(raw)]
        if len(matches) == 1:
            return matches[0]
        warn(f"choose one of: {', '.join(choices)}")
        # (An empty line returns the default above, so piped/EOF input can't loop.)
