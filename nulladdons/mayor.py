"""
Null's Addons -- Mayor / Election awareness (the game's macro-economy).

Every ~5 SkyBlock days the community elects a Mayor whose perks reshape the
economy.  Most players' spreadsheets ignore this; a *game-aware* tool must not,
because the effects are huge and completely change flip maths:

* **Derpy** ("Tax Evasion") removes the Bazaar & Auction House tax entirely.
  With tax at 0% instead of 1.25%, every flip margin fattens -- the tool zeroes
  the tax and tells you to flip aggressively.
* **Mining mayors** (Cole / Mining Fiesta) flood the market with ore -> raw
  mineral prices soften.  Great time to *buy* ores cheap; enchanted-ore flip
  spreads compress, and you should sell what you're holding *before* the dump.
* **Farming** (Finnegan) and **Fishing** (Marina) mayors do the same for crops
  and sea-creature drops.

The current mayor comes from the public ``resources/skyblock/election`` endpoint
(no key).  Upcoming candidates are surfaced as a heads-up, and ``--mayor NAME``
lets you *simulate* any mayor (e.g. plan your next Derpy binge).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Effect tags -> the emoji + note shown to the player.
_MINING_NOTE = ("⛏️ Mining mayor: ore/mineral supply is rising → raw ore prices "
                "soften. Buy ores cheap; sell enchanted-ore stock BEFORE the dump "
                "(flip spreads on minerals compress).")
_FARMING_NOTE = ("🌾 Farming mayor: crop supply rises → crop prices soften. Buy "
                 "crops cheap; sell enchanted crops before they slide.")
_FISHING_NOTE = ("🎣 Fishing mayor: sea-creature/fish supply rises → related item "
                 "prices soften.")
_TAX_NOTE = ("🎪 TAX EVASION is active — Bazaar & AH tax is 0%! Every flip margin "
             "is fatter than normal. Flip big, especially high-volume items.")


@dataclass
class MayorContext:
    name: str
    perks: list[str] = field(default_factory=list)
    tax_multiplier: float = 1.0
    notes: list[str] = field(default_factory=list)
    candidates: list[tuple[str, list[str]]] = field(default_factory=list)
    simulated: bool = False

    @property
    def tax_free(self) -> bool:
        return self.tax_multiplier <= 1e-6

    def headline(self) -> str:
        who = f"{self.name} (simulated)" if self.simulated else self.name
        tag = "  · TAX-FREE 🎪" if self.tax_free else ""
        return f"Mayor: {who}{tag}"


def _econ_tags(text: str) -> list[str]:
    """Classify a blob of mayor/perk text into economic effect tags."""
    text = text.lower()
    tags = []
    if "tax evasion" in text or "derpy" in text:
        tags.append("tax_free")
    if any(k in text for k in ("mining fiesta", "molten forge", "prospection",
                               "mining xp", "cole")):
        tags.append("mining")
    if any(k in text for k in ("farming", "blooming business", "pelt", "trevor",
                               "finnegan", "goated")):
        tags.append("farming")
    if any(k in text for k in ("fishing festival", "marina", "luck of the sea")):
        tags.append("fishing")
    return tags


def _apply_tags(ctx: MayorContext, tags: list[str]) -> None:
    if "tax_free" in tags:
        ctx.tax_multiplier = 0.0
        ctx.notes.append(_TAX_NOTE)
    if "mining" in tags:
        ctx.notes.append(_MINING_NOTE)
    if "farming" in tags:
        ctx.notes.append(_FARMING_NOTE)
    if "fishing" in tags:
        ctx.notes.append(_FISHING_NOTE)
    if not ctx.notes:
        ctx.notes.append(f"{ctx.name} is mayor — no direct Bazaar effect right now.")


def build_context(payload: dict | None) -> MayorContext:
    """Build a :class:`MayorContext` from an election payload."""
    if not payload:
        return MayorContext(name="Unknown")
    mayor = payload.get("mayor") or {}
    perks = mayor.get("perks") or []
    perk_names = [p.get("name", "") for p in perks if isinstance(p, dict)]
    perk_text = " ".join(
        f"{p.get('name', '')} {p.get('description', '')}"
        for p in perks if isinstance(p, dict))
    name = mayor.get("name", "Unknown")

    ctx = MayorContext(name=name, perks=perk_names)
    _apply_tags(ctx, _econ_tags(f"{name} {perk_text}"))

    # Upcoming candidates, tagged for economic relevance.
    for cand in (payload.get("current") or {}).get("candidates", []):
        if not isinstance(cand, dict):
            continue
        ctext = cand.get("name", "") + " " + " ".join(
            p.get("name", "") + " " + p.get("description", "")
            for p in cand.get("perks", []) if isinstance(p, dict))
        tags = [t for t in _econ_tags(ctext) if t != ""]
        if tags:
            ctx.candidates.append((cand.get("name", "?"), tags))
    return ctx


#: Known effects for the simulator (when we can't fetch a live term).
_SIMULATED = {
    "derpy": ["tax_free"], "cole": ["mining"], "finnegan": ["farming"],
    "marina": ["fishing"],
}


def simulate(name: str) -> MayorContext:
    """Build a context for a named mayor without hitting the API (for planning)."""
    key = (name or "").strip().lower()
    ctx = MayorContext(name=(name or "Unknown").title(), simulated=True)
    _apply_tags(ctx, _SIMULATED.get(key, _econ_tags(key)))
    return ctx


TAG_EMOJI = {"tax_free": "🎪", "mining": "⛏️", "farming": "🌾", "fishing": "🎣"}


def candidates_line(ctx: MayorContext) -> str | None:
    """One-line heads-up about economically-relevant upcoming candidates."""
    if not ctx.candidates:
        return None
    parts = [f"{name} " + "".join(TAG_EMOJI.get(t, "") for t in tags)
             for name, tags in ctx.candidates]
    return "Next election: " + ", ".join(parts)
