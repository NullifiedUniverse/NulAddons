"""
Null's Addons -- Google Gemini client (the SkyBlock-expert brain of the brief).

Sends the daily brief's structured facts to Gemini and gets back a human summary
with insights.  Stdlib-only HTTP, same proxy/CA-aware TLS as the rest of the tool.

Everything degrades gracefully: no key, a network error, or a safety block all
return ``None`` so :mod:`nulladdons.brief` can fall back to a deterministic local
brief.  The LLM adds prose and judgement on top of numbers we already computed --
it is never load-bearing for correctness.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .hypixel import _ssl_context

GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent?key={key}")
DEFAULT_MODEL = "gemini-2.5-flash"

#: Persona: a knowledgeable, numbers-driven SkyBlock economy & progression coach.
SYSTEM_PROMPT = (
    "You are a Hypixel SkyBlock economy and progression expert embedded in a "
    "tool called Null's Addons. You are given FACTS computed from the live "
    "Hypixel API: an account's day-over-day progress and current Bazaar / "
    "Auction House / Magical Power opportunities. Write a concise, upbeat daily "
    "brief for the player. Requirements: (1) open with one sentence on how the "
    "day went; (2) call out the most important progress changes; (3) give 3-6 "
    "specific, prioritised, actionable recommendations grounded ONLY in the "
    "facts provided — never invent prices, items, or numbers; (4) if a flip or "
    "craft is listed, tell them to act on the best one. Keep it under ~250 "
    "words, use short bullet points, and speak directly to the player."
)


def gemini_generate(prompt: str, system: str | None = None,
                    api_key: str | None = None, model: str = DEFAULT_MODEL,
                    temperature: float = 0.6, max_tokens: int = 1024,
                    timeout: float = 45.0) -> str | None:
    """Call Gemini and return the text, or ``None`` on any failure."""
    if not api_key:
        return None
    body: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature,
                             "maxOutputTokens": max_tokens},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    data = json.dumps(body).encode("utf-8")
    url = GEMINI_URL.format(model=model, key=api_key)
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "NullsAddons/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    return _extract_text(payload)


def _extract_text(payload: dict) -> str | None:
    candidates = payload.get("candidates") or []
    if not candidates:
        return None
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    return text or None
