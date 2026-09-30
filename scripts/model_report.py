"""Which chat model can drive Blender Copilot? Reads archives/bench-runs/*/result.json and prints (or writes) a table per model.

    python scripts/model_report.py                 # prints the table
    python scripts/model_report.py --write         # writes docs/MODELS.md

A run counts as a success when its status is ok (the agent finished, the file or film exists). The standard tasks are the
``bench-*`` prompts of scripts/demo_bench_mcp.py, run with the same text for every model; other runs are listed only in the
totals. Numbers are from single runs on the day: a model can do better or worse on another day.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "archives" / "bench-runs"
TASKS = ("bench-model-check", "bench-baked-bench", "bench-terrain-forest")
ALIASES = {"bench-baked-bench": ("bench-baked-bench", "model-baked-bench"), "bench-model-check": ("bench-model-check", "model-check-fix"),
           "bench-terrain-forest": ("bench-terrain-forest", "shot-terrain-forest")}


def task_of(name: str) -> str:
    for task, names in ALIASES.items():
        if any(name.startswith(n) for n in names):
            return task
    return ""


def load():
    rows = []
    for path in sorted(RUNS.glob("*/result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("agent") != "in-Blender agent" or not data.get("model"):
            continue
        rows.append(data)
    return rows


def build(rows) -> str:
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    lines = ["# Model report: who can drive Blender Copilot", "",
             "Single runs of the standard tasks through the add-on's own agent (9router). `ok` = the agent finished and the file or film exists; "
             "calls and errors are tool calls and failed tool calls. A free model that finishes in few calls is better than a fast one that needs many.", ""]
    lines += ["| Model | Runs | Finished | Avg calls | Avg tool errors | Avg minutes |", "|---|---|---|---|---|---|"]
    for model, runs in sorted(by_model.items(), key=lambda kv: -sum(r.get("status") == "ok" for r in kv[1]) / len(kv[1])):
        ok = sum(r.get("status") == "ok" for r in runs)
        calls = sum(r.get("tool_calls", 0) for r in runs) / len(runs)
        errs = sum(r.get("tool_errors", 0) for r in runs) / len(runs)
        mins = sum(r.get("seconds", 0) for r in runs) / len(runs) / 60
        lines.append(f"| `{model}` | {len(runs)} | {ok}/{len(runs)} | {calls:.0f} | {errs:.1f} | {mins:.1f} |")
    lines += ["", "Finished means the agent reached the end and produced the file or film; it does not say the result is beautiful (look at the "
              "pictures in `demos/`). Numbers come from one run per task, so read them as a first impression.", ""]
    lines += ["", "## Standard tasks", "",
              "| Task | " + " | ".join(f"`{m}`" for m in sorted(by_model)) + " |", "|---|" + "---|" * len(by_model)]
    for task in TASKS:
        cells = []
        for model in sorted(by_model):
            runs = [r for r in by_model[model] if task_of(str(r.get("name", ""))) == task]
            if not runs:
                cells.append("not run")
                continue
            last = runs[-1]
            mark = "ok" if last.get("status") == "ok" else f"FAILED ({last.get('status')})"
            cells.append(f"{mark}, {last.get('tool_calls', 0)} calls, {last.get('tool_errors', 0)} errors")
        lines.append(f"| {task} | " + " | ".join(cells) + " |")
    lines += ["", "Tasks: model-check = build a table with deliberate defects and fix them with `check_model`; baked-bench = wood and metal "
              "bench, `bake_material`, export; terrain-forest = terrain, house, 40 scattered trees, lamps along a path, orbit film.", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write docs/MODELS.md")
    args = ap.parse_args()
    text = build(load())
    if args.write:
        (ROOT / "docs" / "MODELS.md").write_text(text, encoding="utf-8")
        print("wrote docs/MODELS.md")
    else:
        print(text)


if __name__ == "__main__":
    main()
