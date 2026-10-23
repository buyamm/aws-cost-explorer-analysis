"""Incident bookkeeping around one run: load state → merge → deliver what's new → save."""

from datetime import date
from typing import Callable, Protocol

from .config import Settings
from .detect import Anomaly
from .state import Change, State, mark_alerted, merge


class StateStore(Protocol):
    def load(self) -> State: ...
    def save(self, state: State) -> None: ...


def process(
    anomalies: list[Anomaly],
    settings: Settings,
    fetch_start: date,
    store: StateStore,
    deliver: Callable[[list[Change]], None],
    now: str,
    save: bool = True,
) -> list[Change]:
    """Return the new/worse incidents. If `deliver` raises, nothing is saved, so they are sent next run."""
    state, changes = merge(store.load(), anomalies, settings, fetch_start)
    if changes:
        deliver(changes)
        state = mark_alerted(state, changes, now)
    if save:
        store.save(state)
    return changes
