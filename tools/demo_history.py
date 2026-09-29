"""Build archives/history/index.html: every bench run, newest first, with zoom, chat link and picks.

    python tools/demo_history.py

Open the page, tick "demos'a koy" on the best run of each model, download secim.txt, then
``python tools/demo_promote.py --from-file secim.txt``. Runs already in demos/ carry a star.
"""

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "archives" / "bench-runs"
OUT = ROOT / "archives" / "history"

STYLE = (
    "body{font-family:sans-serif;background:#12141c;color:#e8e8ee;margin:24px}h2{margin-top:36px;border-bottom:1px solid #333;"
    "padding-bottom:6px}.g{display:flex;flex-wrap:wrap;gap:14px}.c{width:320px}.w{position:relative}.c img{width:320px;display:block;"
    "border:1px solid #333;border-radius:6px;background:#000;cursor:zoom-in}.z{position:absolute;right:6px;top:6px;border:0;"
    "border-radius:50%;width:32px;height:32px;font-size:18px;cursor:pointer;background:rgba(18,20,28,.8);color:#fff}.z:hover{background:#3b82f6}"
    ".star{position:absolute;left:6px;top:6px;background:#f5b301;color:#1a1400;font-weight:bold;font-size:12px;padding:3px 8px;border-radius:12px}"
    ".c.lib img{border:2px solid #f5b301}.pick{display:block;margin-top:4px;font-size:12px;color:#cfd;cursor:pointer}.c.sel img{outline:3px solid #22c55e}"
    "#bar{position:sticky;top:0;z-index:5;background:#0d0f16;border-bottom:1px solid #333;padding:10px 0;display:flex;gap:10px;align-items:center}"
    "#bar button{background:#22c55e;color:#04140a;border:0;border-radius:6px;padding:8px 14px;font-weight:bold;cursor:pointer}"
    ".t{font-size:12px;color:#aab;margin-top:4px}.t a{color:#8ab4ff}.bad{color:#f88}#lb{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;"
    "align-items:center;justify-content:center;flex-direction:column;z-index:9;cursor:zoom-out}#lb.on{display:flex}#lb img{max-width:94vw;max-height:84vh;"
    "border-radius:8px;background:#000}#lb p{margin:12px 0 0;color:#dde;font-size:14px}"
)

SCRIPT = (
    "(function(){var K='blenderDemoPicks',P={};try{P=JSON.parse(localStorage.getItem(K)||'null')}catch(e){P=null}"
    "if(!P){P={};document.querySelectorAll('.c.lib').forEach(function(c){P[c.dataset.model]=c.dataset.run})}"
    "function paint(){var n=0;document.querySelectorAll('.c').forEach(function(c){var on=P[c.dataset.model]===c.dataset.run;"
    "c.classList.toggle('sel',on);c.querySelector('.pk').checked=on});for(var g in P)n++;"
    "document.getElementById('cnt').textContent='Secili model: '+n}"
    "document.querySelectorAll('.c').forEach(function(c){c.querySelector('.pk').onchange=function(){"
    "if(this.checked)P[c.dataset.model]=c.dataset.run;else if(P[c.dataset.model]===c.dataset.run)delete P[c.dataset.model];"
    "try{localStorage.setItem(K,JSON.stringify(P))}catch(e){}paint()}});"
    "document.getElementById('dl').onclick=function(){var o=[];for(var g in P)o.push(P[g]);var a=document.createElement('a');"
    "a.href=URL.createObjectURL(new Blob([o.join(String.fromCharCode(10))+String.fromCharCode(10)],{type:'text/plain'}));a.download='secim.txt';a.click()};"
    "var imgs=[].slice.call(document.querySelectorAll('img.s')),cur=0,lb=document.getElementById('lb'),li=document.getElementById('lbi'),lt=document.getElementById('lbt');"
    "function show(i){cur=(i+imgs.length)%imgs.length;li.src=imgs[cur].src;lt.textContent=imgs[cur].dataset.cap;lb.classList.add('on')}"
    "imgs.forEach(function(im,i){im.onclick=function(){show(i)};im.parentNode.querySelector('.z').onclick=function(){show(i)}});"
    "lb.onclick=function(){lb.classList.remove('on')};"
    "document.onkeydown=function(e){if(!lb.classList.contains('on'))return;if(e.key==='Escape')lb.classList.remove('on');"
    "if(e.key==='ArrowRight')show(cur+1);if(e.key==='ArrowLeft')show(cur-1)};paint()})();"
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shots").mkdir(exist_ok=True)
    library = {}
    for run_file in (ROOT / "demos").glob("*/BENCH/run.txt"):
        library[run_file.parent.parent.name] = run_file.read_text(encoding="utf-8").strip()
    cards = []
    for run in sorted(RUNS.iterdir(), reverse=True):
        result_path = run / "result.json"
        if not result_path.exists():
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        name = result["name"]
        sheet = run / "sheet.png"
        image = ""
        if sheet.exists():
            shutil.copy2(sheet, OUT / "shots" / f"{run.name}.png")
            cap = html.escape(f"{run.name}: {result.get('triangles', '-')} ucgen, {result.get('tool_calls', '-')} arac cagrisi")
            image = (f"<div class='w'><img class='s' src='shots/{run.name}.png' data-cap='{cap}'>"
                     f"<button class='z'>&#128269;</button>{'<span class=star>&#9733; demos' + chr(39) + 'ta</span>' if library.get(name) == run.name else ''}</div>")
        else:
            image = "<div class='t bad'>gorsel yok (model olusmamis)</div>"
        chat = (run / "chat.md").resolve().as_uri() if (run / "chat.md").exists() else ""
        status = result["status"]
        info = (f"{status if status != 'ok' else ''} {result.get('triangles', '-')} ucgen | {result.get('tool_calls', '-')} arac | "
                f"{result['seconds']:.0f} sn | {result.get('model', '')} <a href='{chat}'>sohbet</a>")
        lib = " lib" if library.get(name) == run.name else ""
        cards.append(
            f"<div class='c{lib}' data-model='{name}' data-run='{run.name}'><h3>{name}</h3>{image}"
            f"<label class='pick'><input type='checkbox' class='pk'> demos'a koy</label><div class='t{' bad' if status != 'ok' else ''}'>{info}</div></div>")
    page = (f"<!doctype html><meta charset='utf-8'><title>Blender Copilot demo gecmisi</title><style>{STYLE}</style>"
            "<h1>Demo gecmisi (yeniden eskiye)</h1><div id='bar'><span id='cnt'></span><button id='dl'>Secimi indir (secim.txt)</button></div>"
            "<div id='lb'><img id='lbi'><p id='lbt'></p></div><div class='g'>" + "".join(cards) + f"</div><script>{SCRIPT}</script>")
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print("wrote", OUT / "index.html", len(cards), "runs")


if __name__ == "__main__":
    sys.exit(main())
