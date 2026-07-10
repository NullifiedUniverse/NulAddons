"""
Null's Addons -- a tiny parallel task scheduler (standard-library threads).

Almost all of the tool's latency is I/O: it hits several *independent* Hypixel
endpoints (Bazaar, election, ended auctions, skills, your profile) and, until
now, waited for each in turn. This runs the independent ones concurrently and
collapses a handful of sequential round-trips into roughly one.

Threads, not processes, on purpose: the work is I/O-bound and ``urllib`` releases
the GIL while a socket is in flight, so threads give real overlap with zero
serialization cost and no extra dependencies. Every task is isolated -- one slow
or failing endpoint is captured as an error on *its* result and never sinks the
others -- and each result carries how long it took, which the ``--profile`` view
and telemetry both use.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class TaskResult:
    """The outcome of one scheduled task: its value, or the error it raised."""

    name: str
    value: Any = None
    error: Exception | None = None
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


def gather(tasks: dict[str, Callable[[], Any]], *, max_workers: int = 8) -> dict[str, TaskResult]:
    """Run ``{name: zero-arg callable}`` concurrently; return ``{name: TaskResult}``.

    Blocks until every task finishes. A task that raises has its exception
    captured on the result (``ok == False``) rather than propagated, so a single
    dead endpoint degrades gracefully instead of taking the whole command down.
    """
    if not tasks:
        return {}

    def run(name: str, fn: Callable[[], Any]) -> TaskResult:
        started = time.monotonic()
        try:
            value = fn()
            return TaskResult(name, value, None, time.monotonic() - started)
        except Exception as exc:  # isolation is the whole point: capture, don't raise
            return TaskResult(name, None, exc, time.monotonic() - started)

    workers = max(1, min(max_workers, len(tasks)))
    results: dict[str, TaskResult] = {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nulls") as pool:
        futures = [pool.submit(run, name, fn) for name, fn in tasks.items()]
        for future in futures:
            result = future.result()  # run() never raises, so this can't either
            results[result.name] = result
    return results


def values(results: dict[str, TaskResult], default: Any = None) -> dict[str, Any]:
    """Collapse results to ``{name: value}``, substituting ``default`` on error."""
    return {name: (r.value if r.ok else default) for name, r in results.items()}


def total_saved(results: dict[str, TaskResult]) -> float:
    """Rough wall-clock saved vs running the tasks serially: sum(times) - max(time).

    (The parallel run costs about the slowest task; serial would have cost the
    sum. The difference is what the concurrency bought you.)
    """
    if not results:
        return 0.0
    times = [r.seconds for r in results.values()]
    return max(0.0, sum(times) - max(times))
