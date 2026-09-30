"""Demo bench: a fresh Claude Code agent models one asset through the Blender Copilot MCP bridge.

    python scripts/demo_bench_mcp.py --only crate               # one default prompt
    python scripts/demo_bench_mcp.py --name lamp --prompt "model a street lamp"
    python scripts/demo_bench_mcp.py                            # every default prompt, one after another
    python scripts/demo_bench_mcp.py --via 9router --only crate # the add-on's OWN in-Blender agent + 9router

Per run it starts a headless Blender bridge (scratch scene, gated tools allowed), lets `claude -p` work with
only the `blender` MCP server, and writes ``archives/bench-runs/<date>-<name>/`` (git-ignored):

    prompt.txt   chat.jsonl (raw stream)   chat.md (readable chat)   <name>.glb
    shots/       every capture_viewport the agent made + four final views (iso, front, right, top)
    sheet.png    the four final views in one picture      result.json   measurements

Promote the best runs into ``demos/`` with ``scripts/demo_promote.py``.
"""

import argparse
import base64
import json
import os
import re
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "archives" / "bench-runs"
BLENDER = os.environ.get("BLENDER_BIN", r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")

# Short prompts, like a person would type them. The agent gets no recipe beyond the bridge's own instructions.
DEFAULTS = {
    "crate": "Bir oyun için düşük poligonlu ahşap sandık modelle, dışa aktar.",
    "barrel": "Oyun için düşük poligonlu metal varil modelle (bantlı, kapaklı), dışa aktar.",
    "tree": "Oyun için düşük poligonlu bir çam ağacı modelle, dışa aktar.",
    "rock": "Oyun için düşük poligonlu bir kaya modelle (köşeli, düzensiz), dışa aktar.",
    "sword": "Oyun için düşük poligonlu bir kılıç modelle (bıçak, siper, kabza, topuz), dışa aktar.",
    "house": "Oyun için düşük poligonlu küçük bir köy evi modelle (duvar, çatı, kapı, pencere, baca), dışa aktar.",
    "lamp": "Oyun için düşük poligonlu bir sokak lambası modelle (direk, kol, abajur), dışa aktar.",
    "car": "Oyun için düşük poligonlu basit bir araba modelle (gövde, kabin, dört tekerlek), dışa aktar.",
    "tank": "Oyun için düşük poligonlu bir tank modelle (gövde, palet, kule, namlu), dışa aktar.",
    "campfire": "Oyun için düşük poligonlu bir kamp ateşi modelle (taş halka, odunlar, alev), dışa aktar.",
}

SUFFIX = (
    "\n\nÇalışma sahnesi bir deneme sahnesi: varsayılan Cube'u silebilirsin. Modeli viewport'ta kendi gözünle "
    "kontrol et (frame_view + capture_viewport), sonunda `{name}.glb` olarak export_gltf ile dışa aktar ve "
    "kısaca ne yaptığını ve üçgen sayısını yaz."
)

# Shots: model, light, camera move, render an MP4. Names start with "shot-".
SHOTS = {
    "shot-castle-orbit": "Bir kale modelle (kuleler, surlar), gün batımı ışığı kur ve kamerayı kalenin etrafında yavaşça döndürüp 5 saniyelik bir MP4 çek.",
    "shot-soldier-dolly": "Elinde tüfek tutan düşük poligonlu bir asker modelle, kapalı hava (overcast) ışığı kur ve kamerayı askere yavaşça yaklaştıran (dolly_in) 4 saniyelik bir MP4 çek.",
    "shot-tank-crane": "Düşük poligonlu bir tank modelle (gövde, palet, kule, namlu), gün batımı ışığında kamerayı yukarı kaldıran (crane_up) 4 saniyelik bir MP4 çek.",
    "shot-house-night": "Küçük bir köy evi modelle (duvar, çatı, kapı, pencere, baca), gece ışığı kur ve kamerayı evin çevresinde yay çizdirerek (arc) 4 saniyelik bir MP4 çek.",
    "shot-robot-vertigo": "Sevimli bir robot modelle, neon ışık kur ve dolly zoom (vertigo) efektiyle 3 saniyelik bir MP4 çek.",
    "shot-campfire-handheld": "Taş halkalı bir kamp ateşi modelle (odunlar, alev), gece ışığı kur ve elde çekilmiş gibi hafif titreyen (handheld) 4 saniyelik bir MP4 çek.",
    # characters that move: parts stay separate, rig_character, animate_character, camera follows
    "shot-soldier-walk": "Düşük poligonlu bir asker modelle: kafa, kask, gövde, iki kol, iki bacak, botlar, sırt çantası ve tüfek AYRI parçalar olsun (birleştirme). Karakteri rig_character ile bağla, 5 metre yürüt, gün batımı ışığı kur, kamerayı onu takip ettirerek (follow) çek ve 5 saniyelik bir MP4 al.",
    "shot-robot-wave": "Sevimli bir robot karakter modelle (kafa, anten, gövde, iki kol, iki bacak ayrı parçalar olsun, birleştirme). rig_character ile bağla, el salla (wave), stüdyo ışığı kur, kamera yavaşça yaklaşsın (dolly_in) ve 4 saniyelik bir MP4 al.",
    "shot-knight-run": "Zırhlı düşük poligonlu bir şövalye modelle (kafa, miğfer, gövde, kollar, bacaklar, kalkan ayrı parçalar olsun, birleştirme). rig_character ile bağla, koştur (run, 8 metre), kapalı hava ışığı kur, kamera onu takip etsin (follow) ve 4 saniyelik MP4 al.",
    "shot-soldier-aim": "Düşük poligonlu bir asker modelle (kafa, kask, gövde, kollar, bacaklar, tüfek ayrı parçalar olsun, birleştirme). rig_character ile bağla, nişan alma (aim) animasyonu ver, gece ışığı kur, kamera askerin çevresinde yay çizsin (arc_left) ve 4 saniyelik bir MP4 al.",
    "shot-zombie-walk": "Yeşil tenli, yırtık giysili sevimli düşük poligonlu bir zombi modelle (kafa, gövde, kollar, bacaklar ayrı parçalar olsun, birleştirme). rig_character ile bağla, yürüt (3 metre, yavaş), gece ışığı kur, kamera takip etsin (follow) ve 5 saniyelik MP4 al.",
    # bending elbows and knees, polished parts, the character kept in the library
    "shot-runner-bent": "Düşük poligonlu bir koşucu modelle: kafa, gövde, üst kollar ile ön kollar (ForearmL, ForearmR), üst bacaklar ile alt bacaklar (ShinL, ShinR) ve ayakkabılar AYRI parçalar olsun (birleştirme; ön kolun ve alt bacağın üstü, üst parçanın alt ucuna denk gelsin). polish_model ile parçaları yumuşat, rig_character ile bağla, character_library ile 'Runner' adıyla kaydet, koştur (run, 8 metre), sunset ışığı ve cinematic look kur, kamera takip etsin (follow) ve 4 saniyelik MP4 al.",
    # a face that talks (lip sync from text) and a film with a composed soundtrack
    "shot-talker-music": "Sevimli düşük poligonlu bir robot karakter modelle: kafa, gövde, kollar, bacaklar ve yüz için EyeL, EyeR, Mouth adlı küçük kutular (ayrı parçalar, birleştirme). rig_character ile bağla ve animate_character ile talk animasyonunu şu metinle ver: 'Merhaba, ben yeni robotunuzum. Bugün birlikte harika şeyler yapacağız!'. Sonra render_shots ile iki planlık film çek: 1) studio ışığında eyes_in (3 sn), 2) studio ışığında dolly_out (3 sn), cinematic look; müzik olarak 'playful' kullan.",
    # a film: several shots joined (render_shots)
    "shot-film-village": "Küçük bir köy sahnesi modelle: bir köy evi (duvar, çatı, kapı, pencere, baca) ve yanında iki çam ağacı. Sonra render_shots ile üç planlık kısa bir film çek: 1) gün batımı ışığında aerial_pullback (4 sn), 2) gün batımı ışığında dolly_left (3 sn) ve cinematic look, 3) gece ışığında hero_cam (3 sn). Planlar arası crossfade olsun.",
}

SUFFIX_SHOT = (
    "\n\nÇalışma sahnesi bir deneme sahnesi: varsayılan Cube'u silebilirsin. Önce modeli yap, sonra set_environment, "
    "camera_move ve render_image ile bir kareye bakıp ışığı ve kadrajı düzelt, en sonunda render_animation ile "
    "`{name}` adıyla MP4 al ve kısaca ne yaptığını yaz."
)


def is_shot(name):
    return name.startswith("shot-")


def media_summary(path):
    """Frames, duration and size of a video through ffprobe (empty when ffprobe is missing)."""
    import shutil
    ffprobe = shutil.which("ffprobe")
    info = {"video_bytes": Path(path).stat().st_size}
    if not ffprobe:
        return info
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                          "stream=width,height,nb_read_packets,duration", "-of", "json", str(path)],
                         capture_output=True, text=True).stdout
    try:
        stream = json.loads(out)["streams"][0]
        info.update({"video_width": int(stream["width"]), "video_height": int(stream["height"]),
                     "video_frames": int(stream["nb_read_packets"]), "video_seconds": round(float(stream.get("duration", 0)), 2)})
    except (ValueError, KeyError, IndexError):
        pass
    return info


def video_sheet(video, out):
    """Four evenly spaced frames of the video in one 2x2 picture (needs ffmpeg and PIL)."""
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    frames = media_summary(video).get("video_frames") or 0
    if frames < 4:
        return False
    step = max(1, frames // 4)
    tmp = Path(out).parent / "shots"
    tmp.mkdir(exist_ok=True)
    for i in range(4):
        subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(video), "-vf", f"select=eq(n\\,{min(frames - 1, i * step + step // 2)})",
                        "-frames:v", "1", str(tmp / f"video-{i + 1}.png")], capture_output=True)
    paths = [tmp / f"video-{i + 1}.png" for i in range(4)]
    return all(p.exists() for p in paths) and make_sheet(paths, out)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Bridge:
    """A headless Blender serving the MCP bridge for the duration of one run."""

    def __init__(self, export_dir):
        self.export_dir = export_dir
        self.port = free_port()
        self.token = secrets.token_hex(24)
        self.info_path = Path(tempfile.gettempdir()) / "blender_copilot_mcp.json"
        self.stop_path = Path(tempfile.gettempdir()) / "blender_copilot_mcp.stop"
        self.proc = None
        self._id = 0

    def start(self):
        if self.info_path.exists():
            self.info_path.unlink()
        if self.stop_path.exists():
            self.stop_path.unlink()
        self.proc = subprocess.Popen(
            [BLENDER, "--background", "--python", str(ROOT / "tools" / "serve_mcp_headless.py"), "--",
             "--port", str(self.port), "--token", self.token, "--export-dir", str(self.export_dir), "--allow-gated"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(120):
            if self.info_path.exists():
                return
            time.sleep(0.5)
        raise RuntimeError("the Blender bridge did not start")

    def stop(self):
        if self.proc is None:
            return
        self.stop_path.write_text("stop", encoding="utf-8")
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        if self.stop_path.exists():
            self.stop_path.unlink()

    def endpoint(self):
        return f"http://127.0.0.1:{self.port}/mcp"

    def call(self, tool, **args):
        self._id += 1
        body = {"jsonrpc": "2.0", "id": self._id, "method": "tools/call", "params": {"name": tool, "arguments": args}}
        req = urllib.request.Request(self.endpoint(), data=json.dumps(body).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("MCP-Protocol-Version", "2026-07-28")
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["result"]


def glb_summary(path):
    """Triangles, materials and size (meters, Y-up) read from the .glb JSON chunk."""
    data = Path(path).read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + length])
    tris = 0
    lo, hi = [1e9] * 3, [-1e9] * 3
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if "indices" in prim:
                tris += doc["accessors"][prim["indices"]]["count"] // 3
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            for i in range(3):
                lo[i] = min(lo[i], acc["min"][i])
                hi[i] = max(hi[i], acc["max"][i])
    size = [round(hi[i] - lo[i], 3) for i in range(3)] if tris else [0, 0, 0]
    return {"triangles": tris, "materials": len(doc.get("materials", [])), "nodes": len(doc.get("nodes", [])),
            "size_m": size, "bytes": len(data)}


def clean_text(value, limit=1500):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + f" ... [{len(text) - limit} more characters]"


def write_chat(events, run_dir, shots_dir):
    """chat.md from the stream-json events; agent captures are saved as shots/agent-NN.png."""
    lines, shot_n, tools, errors, model = [], 0, 0, 0, ""
    names = {}
    for ev in events:
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "init":
            model = ev.get("model", "")
        elif kind == "assistant":
            for block in ev["message"]["content"]:
                if block.get("type") == "text" and block["text"].strip():
                    lines.append("**Ajan:** " + block["text"].strip() + "\n")
                elif block.get("type") == "tool_use":
                    tools += 1
                    names[block["id"]] = block["name"]
                    lines.append(f"- `{block['name']}` {clean_text(block['input'], 400)}")
        elif kind == "user":
            content = ev["message"]["content"]
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") != "tool_result":
                    continue
                if block.get("is_error"):
                    errors += 1
                parts = block.get("content")
                if isinstance(parts, str):
                    parts = [{"type": "text", "text": parts}]
                for part in parts or []:
                    if part.get("type") == "image":
                        shot_n += 1
                        name = f"agent-{shot_n:02d}.png"
                        (shots_dir / name).write_bytes(base64.b64decode(part["source"]["data"]))
                        lines.append(f"  ![]({'shots/' + name})")
                    elif part.get("type") == "text":
                        lines.append("  > " + clean_text(part["text"], 300).replace("\n", " "))
        elif kind == "result":
            lines.append("\n---\n**Sonuç:** " + str(ev.get("result", "")).strip())
    (run_dir / "chat.md").write_text("# Sohbet\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return {"model": model, "tool_calls": tools, "tool_errors": errors, "agent_shots": shot_n}


def final_views(bridge, shots_dir):
    """Four clean views of whatever the scene holds when the agent finished."""
    made = []
    for direction in ("ISO", "FRONT", "RIGHT", "TOP"):
        bridge.call("frame_view", direction=direction, shading="MATERIAL", overlays=False)
        res = bridge.call("capture_viewport", width=800, height=600)
        for block in res["content"]:
            if block["type"] == "image":
                path = shots_dir / f"final-{direction.lower()}.png"
                path.write_bytes(base64.b64decode(block["data"]))
                made.append(path)
    return made


def make_sheet(paths, out):
    try:
        from PIL import Image
    except ImportError:
        return False
    if len(paths) != 4:
        return False
    images = [Image.open(p).convert("RGB") for p in paths]
    w, h = images[0].size
    sheet = Image.new("RGB", (w * 2, h * 2))
    for i, img in enumerate(images):
        sheet.paste(img, ((i % 2) * w, (i // 2) * h))
    sheet.save(out)
    return True


def run_one(name, prompt, timeout_min, max_turns, model):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / f"{stamp}-{name}"
    shots_dir = run_dir / "shots"
    shots_dir.mkdir(parents=True)
    full_prompt = prompt + (SUFFIX_SHOT if is_shot(name) else SUFFIX).format(name=name)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    bridge = Bridge(run_dir)
    started = time.time()
    events, status = [], "ok"
    try:
        bridge.start()
        cfg = run_dir / "mcp.json"
        cfg.write_text(json.dumps({"mcpServers": {"blender": {
            "type": "http", "url": bridge.endpoint(), "headers": {"Authorization": "Bearer " + bridge.token}}}}),
            encoding="utf-8")
        cmd = ["claude", "-p", full_prompt, "--mcp-config", str(cfg), "--strict-mcp-config",
               "--allowedTools", "mcp__blender__*", "--max-turns", str(max_turns),
               "--output-format", "stream-json", "--verbose"]
        if model:
            cmd += ["--model", model]
        try:
            proc = subprocess.run(cmd, cwd=run_dir, capture_output=True, text=True, encoding="utf-8",
                                  timeout=timeout_min * 60)
            raw = proc.stdout
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            raw = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        (run_dir / "chat.jsonl").write_text(raw, encoding="utf-8")
        for line in raw.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        duration = time.time() - started
        stats = write_chat(events, run_dir, shots_dir)
        try:
            finals = final_views(bridge, shots_dir)
            make_sheet(finals, run_dir / "sheet.png")
            if is_shot(name) and (run_dir / f"{name}.mp4").exists():
                video_sheet(run_dir / f"{name}.mp4", run_dir / "sheet.png")
        except Exception as exc:  # the scene may be empty when the agent failed
            status = status if status != "ok" else f"no-final-views: {exc}"
    finally:
        bridge.stop()
        (run_dir / "mcp.json").unlink(missing_ok=True)  # holds the one-run token
    result = {"name": name, "date": stamp, "status": status, "seconds": round(duration or time.time() - started, 1)}
    result.update(stats if events else {})
    artifact = run_dir / (f"{name}.mp4" if is_shot(name) else f"{name}.glb")
    if artifact.exists():
        result.update(media_summary(artifact) if is_shot(name) else glb_summary(artifact))
    else:
        result["status"] = "no-output" if result["status"] == "ok" else result["status"]
    for ev in events:
        if ev.get("type") == "result":
            result["final_message"] = str(ev.get("result", ""))[:2000]
            result["turns"] = ev.get("num_turns")
            result["cost_usd"] = ev.get("total_cost_usd")
    if any(ev.get("type") == "result" and ev.get("api_error_status") for ev in events):
        # the API refused (rate or session limit): nothing was modelled, keep no archive and stop the queue
        import shutil
        shutil.rmtree(run_dir, ignore_errors=True)
        raise SystemExit(f"[bench] {name}: API limit reached ({events[-1].get('result', '')}); run discarded")
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[bench] {name}: {result['status']} {result.get('triangles', '-')} tris, "
          f"{result.get('tool_calls', '-')} calls, {result['seconds']}s -> {run_dir}", flush=True)
    return run_dir


def router_env(base_url, model):
    """Provider settings for the in-Blender agent: 9router profile of the Godot AI Sidebar store, or BLENDER_AI_* env."""
    env = dict(os.environ)
    if not env.get("BLENDER_AI_API_KEY"):
        store = Path(os.environ.get("APPDATA", "")) / "Godot" / "godot_ai_sidebar" / "providers.json"
        profiles = json.loads(store.read_text(encoding="utf-8")).get("provider_profiles", [])
        profile = next((p for p in profiles if p.get("api_key") and base_url in p.get("base_url", "")), None)
        if profile is None:
            raise SystemExit(f"no provider profile with a key for {base_url}; set BLENDER_AI_API_KEY")
        env["BLENDER_AI_API_KEY"] = profile["api_key"]
    env["BLENDER_AI_BASE_URL"] = base_url
    env["BLENDER_AI_MODEL"] = model
    env.setdefault("BLENDER_AI_TIMEOUT", "180")
    env["BLENDER_AI_CONTINUE_ON_TOOL_ERROR"] = "1"  # a failed call goes back to the model instead of ending the run
    return env


def run_one_agent(name, prompt, timeout_min, base_url, model):
    """The add-on's own agent (headless Blender, OpenAI-compatible provider such as 9router) models one asset."""
    name = f"{name}-{re.sub(r'[^A-Za-z0-9]', '', model.split('/')[-1])}"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / f"{stamp}-{name}"
    (run_dir / "shots").mkdir(parents=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    started = time.time()
    try:
        subprocess.run([BLENDER, "--background", "--python", str(ROOT / "scripts" / "agent_run_headless.py"), "--",
                        "--prompt-file", str(run_dir / "prompt.txt"), "--out-dir", str(run_dir), "--name", name,
                        "--kind", "shot" if is_shot(name) else "model",
                        "--timeout", str(timeout_min * 60 - 30)],
                       env=router_env(base_url, model), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=timeout_min * 60)
    except subprocess.TimeoutExpired:
        pass
    stats_path = run_dir / "stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {"status": "crashed"}
    stats_path.unlink(missing_ok=True)
    finals = [run_dir / "shots" / f"final-{d}.png" for d in ("iso", "front", "right", "top")]
    if all(p.exists() for p in finals):
        make_sheet(finals, run_dir / "sheet.png")
    if is_shot(name) and (run_dir / f"{name}.mp4").exists():
        video_sheet(run_dir / f"{name}.mp4", run_dir / "sheet.png")
    result = {"name": name, "date": stamp, "seconds": round(time.time() - started, 1), "agent": "in-Blender agent",
              "via": base_url}
    result.update(stats)
    artifact = run_dir / (f"{name}.mp4" if is_shot(name) else f"{name}.glb")
    if artifact.exists():
        result.update(media_summary(artifact) if is_shot(name) else glb_summary(artifact))
        if result["status"] in ("error", "timeout"):
            result["note"] = f"exported despite {result['status']}"
    elif result["status"] == "ok":
        result["status"] = "no-output"
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[bench] {name}: {result['status']} {result.get('triangles', '-')} tris, "
          f"{result.get('tool_calls', '-')} calls, {result['seconds']}s -> {run_dir}", flush=True)
    return run_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma separated names from the default prompts")
    ap.add_argument("--name")
    ap.add_argument("--prompt")
    ap.add_argument("--timeout-min", type=int, default=20)
    ap.add_argument("--max-turns", type=int, default=90)
    ap.add_argument("--model", default="")
    ap.add_argument("--via", choices=["claude", "9router"], default="claude",
                    help="claude: Claude Code over MCP (default); 9router: the add-on's own in-Blender agent")
    ap.add_argument("--router-url", default="http://localhost:20128/v1")
    ap.add_argument("--shots", action="store_true", help="with no --only: run every shot prompt instead of the model prompts")
    args = ap.parse_args()
    if args.name and args.prompt:
        jobs = [(re.sub(r"[^A-Za-z0-9_-]", "-", args.name), args.prompt)]
    else:
        pool = {**DEFAULTS, **SHOTS}
        names = args.only.split(",") if args.only else (list(SHOTS) if args.shots else list(DEFAULTS))
        jobs = [(n, pool[n]) for n in names]
    for name, prompt in jobs:
        if args.via == "9router":
            run_one_agent(name, prompt, args.timeout_min, args.router_url, args.model or "a")
        else:
            run_one(name, prompt, args.timeout_min, args.max_turns, args.model)


if __name__ == "__main__":
    sys.exit(main())
