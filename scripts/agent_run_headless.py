"""Run Blender Copilot's OWN in-Blender agent headless on one prompt (any OpenAI-compatible provider, e.g. 9router).

    blender --background --python scripts/agent_run_headless.py -- --prompt-file P --out-dir D --name crate

Provider comes from the environment: BLENDER_AI_BASE_URL, BLENDER_AI_API_KEY, BLENDER_AI_MODEL, BLENDER_AI_PROVIDER.
Writes into --out-dir: chat.json, chat.md, stats.json, <name>.glb (if the agent exported it) and shots/final-*.png.
Approvals are granted automatically (headless scratch scene). This is the counterpart of the MCP bench, where an
external agent (Claude Code) drives the same tools through the bridge.
"""

import base64
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse(argv):
    args = {"prompt_file": "", "out_dir": "", "name": "model", "timeout": 900.0, "kind": "model"}
    it = iter(argv)
    for a in it:
        if a == "--prompt-file":
            args["prompt_file"] = next(it)
        elif a == "--out-dir":
            args["out_dir"] = next(it)
        elif a == "--name":
            args["name"] = next(it)
        elif a == "--kind":
            args["kind"] = next(it)
        elif a == "--timeout":
            args["timeout"] = float(next(it))
    return args


def clip(text, limit=400):
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + f" ... [{len(text) - limit} more characters]"


def main():
    args = parse(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    out = Path(args["out_dir"])
    (out / "shots").mkdir(parents=True, exist_ok=True)
    prompt = Path(args["prompt_file"]).read_text(encoding="utf-8").strip()
    os.environ["BLENDER_COPILOT_EXPORT_DIR"] = str(out)

    spec = importlib.util.spec_from_file_location("blender_ai_sidebar", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    ext = importlib.util.module_from_spec(spec)
    sys.modules["blender_ai_sidebar"] = ext
    spec.loader.exec_module(ext)
    ext.register()
    runtime, bridge = ext.get_runtime(), ext.get_timer_bridge()
    adapter = runtime.dispatcher.adapter
    adapter.export_dir = str(out)

    from agent.state_machine import AgentState

    started = time.time()
    shot = args["kind"] == "shot"
    if shot:
        tail = (f"\n\nÇalışma sahnesi bir deneme sahnesi (varsayılan Cube'u silebilirsin). Önce modeli yap, sonra set_environment, camera_move ve "
                f"render_image ile bir kareye bakıp ışığı ve kadrajı düzelt, en sonunda render_animation ile `{args['name']}` adıyla MP4 al ve kısaca ne yaptığını yaz.")
    else:
        tail = (f"\n\nÇalışma sahnesi bir deneme sahnesi (varsayılan Cube'u silebilirsin). Modeli viewport'ta kontrol et, "
                f"sonunda `{args['name']}.glb` adıyla export_gltf ile dışa aktar ve kısaca ne yaptığını yaz.")
    runtime.submit_prompt(prompt + tail)
    approvals = 0
    status = "ok"
    followups = 0
    glb = out / (f"{args['name']}.mp4" if shot else f"{args['name']}.glb")
    while True:
        bridge.tick()
        try:
            if runtime.pending_approval is not None:
                runtime.approve(runtime.pending_approval.approval_id)
                approvals += 1
            elif getattr(runtime, "pending_plan_review", None) is not None:
                runtime.approve_plan(runtime.pending_plan_review.approval_id)
                approvals += 1
        except Exception as exc:  # a stale approval must not stop the run
            print(f"[agent] approval: {exc}", flush=True)
        if runtime.current_state in (AgentState.IDLE, AgentState.ERROR) and runtime.current_turn_id is None:
            # A user would nudge a model that stopped before exporting: at most two follow-ups.
            if runtime.current_state == AgentState.IDLE and not glb.exists() and followups < 2:
                followups += 1
                runtime.submit_prompt(
                    (f"Video henüz render edilmedi. Eksik adımları tamamla (set_environment, camera_move) ve render_animation ile `{args['name']}` adıyla MP4 al."
                     if shot else
                     f"Model henüz dışa aktarılmadı. Kalan parçaları tamamla, join_objects ve set_origin ile tek nesne yap "
                     f"ve export_gltf ile `{args['name']}.glb` olarak dışa aktar."))
                continue
            break
        if time.time() - started > args["timeout"]:
            status = "timeout"
            break
        time.sleep(0.02)
    seconds = round(time.time() - started, 1)
    if runtime.current_state == AgentState.ERROR:
        status = "error"

    lines, calls, errors, chat = [], 0, 0, []
    names = {}
    for m in runtime.conversation.messages:
        role = m.role.value
        chat.append({"role": role, "content": m.content, "tool_calls": [
            {"name": tc.tool_name, "arguments": tc.arguments} for tc in (m.tool_calls or [])], "tool_call_id": m.tool_call_id})
        if role == "user":
            lines.append("**Kullanıcı:** " + (m.content or "") + "\n")
        elif role == "assistant":
            if m.content and m.content.strip():
                lines.append("**Ajan:** " + m.content.strip() + "\n")
            for tc in m.tool_calls or []:
                calls += 1
                names[tc.tool_call_id if hasattr(tc, "tool_call_id") else id(tc)] = tc.tool_name
                lines.append(f"- `{tc.tool_name}` {clip(tc.arguments)}")
        elif role == "tool":
            body = m.content or ""
            if body.startswith('{"error"'):
                errors += 1
            lines.append("  > " + clip(body.replace("\n", " "), 300))
    (out / "chat.json").write_text(json.dumps(chat, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "chat.md").write_text("# Sohbet\n\n" + "\n".join(lines) + "\n", encoding="utf-8")

    # Four clean final views of whatever the scene holds.
    shots = 0
    try:
        for direction in ("ISO", "FRONT", "RIGHT", "TOP"):
            adapter.frame_view(direction=direction, shading="MATERIAL", overlays=False)
            res = adapter.capture_viewport(width=800, height=600)
            data = res.data if hasattr(res, "data") else None
            if data and data.get("image_id"):
                png = adapter.get_viewport_screenshot(data["image_id"])
                if png:
                    (out / "shots" / f"final-{direction.lower()}.png").write_bytes(png)
                    shots += 1
    except Exception as exc:
        print(f"[agent] final views failed: {exc}", flush=True)

    stats = {"status": status, "seconds": seconds, "tool_calls": calls, "tool_errors": errors, "approvals": approvals,
             "followups": followups, "final_views": shots, "model": os.environ.get("BLENDER_AI_MODEL", ""), "provider_url": os.environ.get("BLENDER_AI_BASE_URL", "").split("@")[-1],
             "final_message": (runtime.last_result.final_text if getattr(runtime, "last_result", None) else "")[:2000]}
    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print("AGENT_DONE", json.dumps({k: stats[k] for k in ("status", "seconds", "tool_calls", "tool_errors")}), flush=True)
    runtime.shutdown()
    ext.unregister()


if __name__ == "__main__":
    main()
