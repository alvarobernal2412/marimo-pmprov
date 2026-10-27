from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Snapshot:
    """The whole analysis as it stood at one recorded state.

    `state_id` is None for the live analysis (an analyst's view); then `get()`
    hands back the live value, so a notebook cell renders the same code path
    either way. At a recorded state, each variable holds exactly the value it
    was bound to there. Values load lazily, one name at a time, so a cell that
    shows one table does not read the whole notebook from disk.

    `bound` lists the names bound at the state (None when the source cannot
    say). It is what tells "never computed at this step" apart from "was
    computed but is not stored".
    """

    state_id: str | None
    operation: str | None = None
    params: dict = field(default_factory=dict)
    step: int | None = None
    bound: frozenset[str] | None = None
    error: str | None = None
    loader: Callable[[list[str]], dict] | None = field(default=None, repr=False, compare=False)
    _cache: dict = field(default_factory=dict, repr=False, compare=False)
    _tried: set = field(default_factory=set, repr=False, compare=False)

    @property
    def is_live(self) -> bool:
        return self.state_id is None

    def _load(self, names: list[str]) -> None:
        todo = [n for n in names if n not in self._cache and n not in self._tried]
        if not todo or self.loader is None:
            return
        self._tried.update(todo)
        self._cache.update(self.loader(todo))

    def get(self, name: str, live: Any = None) -> Any:
        """`live` while following the live analysis, else the value at this
        state, or None if it is not available (see `missing()` for why)."""
        if self.is_live:
            return live
        self._load([name])
        return self._cache.get(name)

    @property
    def variables(self) -> dict[str, Any]:
        """Every variable bound at the state that could be loaded (loads them all)."""
        if not self.is_live and self.bound is not None:
            self._load(sorted(self.bound))
        return dict(self._cache)

    def status(self, name: str) -> str:
        """"live", "ok", "not_stored" (bound here but pmprov holds no loadable
        value) or "not_computed" (not bound at this state)."""
        if self.is_live:
            return "live"
        if self.get(name) is not None:
            return "ok"
        if self.bound is not None and name in self.bound:
            return "not_stored"
        return "not_computed"

    def missing(self, name: str) -> str:
        """Markdown explaining why `name` has no value here."""
        if self.error:
            return f"_Snapshot unavailable: {self.error}_"
        if self.status(name) == "not_stored":
            return "_This variable exists at this step, but its value was not stored by pmprov._"
        return "_Not computed yet at this step._"

    def banner(self) -> str:
        """One-line description of the state being shown."""
        if self.is_live:
            return "Live analysis"
        parts = [f"Snapshot of the analysis after “{self.operation}”"]
        if self.step is not None:
            parts[0] += f" (step {self.step})"
        if self.params:
            parts.append("parameters: " + ", ".join(f"{k} = {v!r}" for k, v in self.params.items()))
        return " · ".join(parts)
