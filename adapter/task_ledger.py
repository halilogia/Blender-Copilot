"""Task ledger: one AI task = one unit you can look at and take back.

A task is everything done since the last ``report`` (or ``rollback``, or the start of a chat message in the add-on's own
agent). The ledger keeps a semantic snapshot taken before the first tool of the task and the number of undo steps the task
pushed. ``report`` compares the scene now with that snapshot (core.scene_diff); ``rollback`` undoes exactly that many steps
and then checks, by another comparison, that the scene really is back where it started.
"""

from typing import Any, Dict, Optional

from adapter.mutators import undo_manager
from adapter.readers import scene_snapshot
from core.scene_diff import diff, headline


class TaskLedger:
    def __init__(self) -> None:
        self._baseline: Optional[Dict[str, Any]] = None
        self._steps_at_baseline = 0
        self._label = ""

    @property
    def is_open(self) -> bool:
        return self._baseline is not None

    def ensure_baseline(self, label: str = "") -> None:
        """Take the snapshot if no task is open (called before every tool; cheap when a task is already open)."""
        if self._baseline is None:
            self._baseline = scene_snapshot.take()
            self._steps_at_baseline = undo_manager.undo_counter()
            self._label = label

    def begin(self, label: str = "") -> None:
        """Start a fresh task now, forgetting the old baseline (a new chat message)."""
        self._baseline = None
        self.ensure_baseline(label)

    def _steps(self) -> int:
        return max(undo_manager.undo_counter() - self._steps_at_baseline, 0)

    def report(self, close: bool = True) -> Dict[str, Any]:
        """What the task changed so far. With ``close`` the next tool starts a new task."""
        self.ensure_baseline()
        result = diff(self._baseline, scene_snapshot.take())
        out = {"changes": result["summary"], "headline": headline(result), "empty": result["empty"], "counts": result["counts"],
               "undo_steps": self._steps(), "task": self._label}
        if close:
            self._baseline = None
        return out

    def rollback(self) -> Dict[str, Any]:
        """Undo the whole task and verify the scene matches the snapshot taken before it."""
        if self._baseline is None:
            return {"rolled_back": False, "reason": "No open task: nothing was changed since the last report or rollback."}
        steps = self._steps()
        before = diff(self._baseline, scene_snapshot.take())
        if steps == 0 and before["empty"]:
            self._baseline = None
            return {"rolled_back": False, "reason": "The task changed nothing."}
        done = undo_manager.rollback_steps(steps)
        remaining = diff(self._baseline, scene_snapshot.take())
        out = {"rolled_back": remaining["empty"], "undo_steps_done": done, "undo_steps_expected": steps,
               "undone": before["summary"], "remaining_differences": remaining["summary"],
               "verified": remaining["empty"]}
        if not remaining["empty"]:
            out["note"] = ("The scene is not exactly as it was: something changed outside the AI's steps (manual edits) or a step "
                           "could not be undone. Check the remaining differences; Ctrl+Z in Blender continues from here.")
        self._baseline = None
        return out


LEDGER = TaskLedger()
