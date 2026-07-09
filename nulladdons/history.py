"""
Null's Addons -- lightweight price history.

A single Bazaar snapshot cannot tell you whether a price is *stable* or wildly
swinging, and volatility is the biggest hidden risk in a flip.  So every time
the tool fetches the market it appends the mid price of each product to a local
JSONL log.  The more you run Null's Addons, the smarter its risk model gets:

* **Volatility** -> coefficient of variation of recent mids.  High CV means the
  spread you see now may evaporate before your orders fill.
* **Mean reversion** -> z-score of the current mid vs its recent average.  A
  price far *below* its mean is a better buy; far *above*, a better sell.

History is optional: if the log is empty the engine simply skips these terms and
leans on live liquidity instead.  Nothing here ever blocks a run.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from collections import defaultdict

DEFAULT_HISTORY_PATH = os.path.join(
    os.path.expanduser("~"), ".nulladdons", "price_history.jsonl"
)

#: Cap the log so it never grows without bound (keep most recent N snapshots).
MAX_SNAPSHOTS = 500


def record_snapshot(market, path: str = DEFAULT_HISTORY_PATH) -> None:
    """Append the current mid price of every product to the history log."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mids = {pid: round(p.mid, 3) for pid, p in market.products.items()}
        line = json.dumps({"ts": int(time.time()), "mids": mids})
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        _truncate(path)
    except OSError:
        # History is a nice-to-have; never let disk issues break a run.
        pass


def _truncate(path: str) -> None:
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > MAX_SNAPSHOTS:
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-MAX_SNAPSHOTS:])
    except OSError:
        pass


def load_series(path: str = DEFAULT_HISTORY_PATH) -> dict[str, list[float]]:
    """Return ``{product_id -> [mid, mid, ...]}`` ordered oldest -> newest."""
    series: dict[str, list[float]] = defaultdict(list)
    if not os.path.exists(path):
        return series
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                snap = json.loads(raw)
                for pid, mid in snap.get("mids", {}).items():
                    series[pid].append(float(mid))
    except (OSError, ValueError):
        return defaultdict(list)
    return series


class PriceHistory:
    """Read-only convenience wrapper over the loaded series."""

    def __init__(self, series: dict[str, list[float]]):
        self.series = series

    @classmethod
    def load(cls, path: str = DEFAULT_HISTORY_PATH) -> PriceHistory:
        return cls(load_series(path))

    def samples(self, pid: str) -> int:
        return len(self.series.get(pid, ()))

    def volatility(self, pid: str) -> float | None:
        """
        Coefficient of variation (stdev / mean) of recent mids, or ``None`` if
        there is not enough history to be meaningful (needs >= 3 samples).
        """
        vals = self.series.get(pid, [])
        if len(vals) < 3:
            return None
        mean = statistics.fmean(vals)
        if mean <= 0:
            return None
        return statistics.pstdev(vals) / mean

    def movers(self, window: int = 8, min_samples: int = 3) -> dict[str, float]:
        """
        Fractional price change over the recent ``window`` snapshots, per product.

        A creative reuse of the history log: sharp moves flag pumps/dumps, event
        spikes, or manipulation the caller can turn into a warning or an entry.
        Returns ``{product_id -> pct_change}`` (empty until history exists).
        """
        out: dict[str, float] = {}
        for pid, vals in self.series.items():
            if len(vals) < min_samples:
                continue
            recent = vals[-window:]
            old, new = recent[0], recent[-1]
            if old > 0:
                out[pid] = (new - old) / old
        return out

    def zscore(self, pid: str, current_mid: float) -> float | None:
        """
        How many standard deviations the current mid sits from its recent mean.
        Negative => currently cheap (good to buy); positive => currently rich.
        """
        vals = self.series.get(pid, [])
        if len(vals) < 3:
            return None
        mean = statistics.fmean(vals)
        sd = statistics.pstdev(vals)
        if sd <= 0:
            return 0.0
        return (current_mid - mean) / sd
