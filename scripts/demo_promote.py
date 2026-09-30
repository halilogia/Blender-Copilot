"""Put chosen bench runs into demos/ (the git-tracked library) and rebuild demos/README.md.

    python scripts/demo_promote.py 20260930-010632-crate 20260930-011500-barrel
    python scripts/demo_promote.py --rebuild            # only regenerate demos/README.md

A run folder name comes from archives/bench-runs/. Copies the .glb, the picture sheet, the readable chat and the
measurements; the raw stream (chat.jsonl) stays in the archive. Promoting a name again replaces the old demo and
moves it to archives/demos-replaced/.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "archives" / "bench-runs"
DEMOS = ROOT / "demos"
REPLACED = ROOT / "archives" / "demos-replaced"


def promote(run_name):
    run = RUNS / run_name
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    name = result["name"]
    if result.get("status") != "ok":
        raise SystemExit(f"{run_name}: status is {result.get('status')}, not promoting")
    dest = DEMOS / name
    if dest.exists():
        REPLACED.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(REPLACED / f"{run_name}-old"))
    (dest / "BENCH").mkdir(parents=True)
    shutil.copy2(run / f"{name}.glb", dest / f"{name}.glb")
    shutil.copy2(run / "sheet.png", dest / "sheet.png")
    shutil.copy2(run / "shots" / "final-iso.png", dest / "screenshot.png")
    for file in ("prompt.txt", "result.json", "chat.md"):
        shutil.copy2(run / file, dest / "BENCH" / file)
    shots = dest / "BENCH" / "shots"
    shots.mkdir()
    for png in sorted((run / "shots").glob("agent-*.png")):
        shutil.copy2(png, shots / png.name)
    (dest / "BENCH" / "run.txt").write_text(run_name + "\n", encoding="utf-8")
    print("promoted", run_name, "->", dest)


def rebuild():
    rows, gallery = [], []
    for folder in sorted(p for p in DEMOS.iterdir() if p.is_dir()):
        result = json.loads((folder / "BENCH" / "result.json").read_text(encoding="utf-8"))
        prompt = (folder / "BENCH" / "prompt.txt").read_text(encoding="utf-8").strip()
        size = "x".join(f"{v:.2f}" for v in result.get("size_m", [])) + " m"
        who = ("Blender Copilot ajanı (9router)" if result.get("agent") == "in-Blender agent" else "Claude Code (MCP)") + f" · {result.get('model') or 'claude-opus-5-5'}"
        rows.append(f"| [{folder.name}]({folder.name}/) | {who} | {prompt} | {result['seconds'] / 60:.1f} dk | "
                    f"{result.get('tool_calls', '-')} | {result.get('triangles', '-')} | {size} | {result['date'][:8]} |")
        gallery.append(f"**{folder.name}**\n\n![{folder.name}]({folder.name}/sheet.png)\n")
    text = (
        "# Demo kütüphanesi\n\n"
        "Her model, boş bir Blender sahnesinde tek bir istemle bir ajanın izin listeli araçlarla (rastgele Python yok) "
        "modellediği bir `.glb` dosyasıdır: ya **Claude Code** Blender Copilot MCP köprüsü üzerinden, ya da eklentinin "
        "**kendi Blender içi ajanı** 9router üzerinden (`Ajan` sütunu hangisi olduğunu söyler) "
        "(`scripts/demo_bench_mcp.py`). İstem, sohbet ve ölçüm her demonun `BENCH/` klasöründe. Sayfada dört görünüm: "
        "izometrik, ön, sağ, üst.\n\n"
        "Kullanmak için: `.glb` dosyasını Godot, Unity ya da Blender'a sürükle (Godot: "
        "`res://assets/models/` altına at).\n\n"
        "| Model | Ajan | İstem | Süre | Araç çağrısı | Üçgen | Boyut | Tarih |\n|---|---|---|---|---|---|---|---|\n"
        + "\n".join(rows) + "\n\n## Galeri\n\n" + "\n".join(gallery))
    (DEMOS / "README.md").write_text(text, encoding="utf-8")
    print("rebuilt", DEMOS / "README.md")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--from-file", help="secim.txt from the history page (one run name per line)")
    args = ap.parse_args()
    DEMOS.mkdir(exist_ok=True)
    runs = list(args.runs)
    if args.from_file:
        runs += [l.strip() for l in Path(args.from_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    for run in runs:
        promote(run)
    rebuild()


if __name__ == "__main__":
    sys.exit(main())
