"""High-performance 2D GPU drawing functions for Blender AI Viewport Overlay."""

import math
from typing import List, Tuple
import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

from .menu import mcp_summary, menu_items
from .settings import LABELS, display_value, online_status, provider_note, visible_fields
from .state import overlay_state
from .theme import (
    ACCENT, ACCENT_HOVER, ACCENT_INK, BORDER, CTRL, CTRL_HOVER, DANGER, DANGER_FILL, OK,
    OK_FILL, RADIUS_CTRL, SURFACE, SURFACE_2, TEXT, TEXT_DIM, TEXT_FAINT, WARN,
)
from ..text_formatting import format_tool_status_icon

# Cache compiled built-in shader
_uniform_shader = None


def get_uniform_shader():
    """Retrieve cached UNIFORM_COLOR shader."""
    global _uniform_shader
    if _uniform_shader is None:
        _uniform_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    return _uniform_shader


def build_rounded_rect_tris(
    x: float, y: float, w: float, h: float, radius: float, segments: int = 8
) -> List[Tuple[float, float]]:
    """Tessellate an anti-aliased rounded rectangle into triangles."""
    r = max(0.0, min(radius, w / 2.0, h / 2.0))
    if r <= 0.0:
        # Simple rectangle (2 triangles)
        return [
            (x, y), (x + w, y), (x + w, y + h),
            (x, y), (x + w, y + h), (x, y + h),
        ]

    tris: List[Tuple[float, float]] = []

    # Center box
    cx1, cx2 = x + r, x + w - r
    cy1, cy2 = y + r, y + h - r

    # Center core
    tris.extend([
        (cx1, cy1), (cx2, cy1), (cx2, cy2),
        (cx1, cy1), (cx2, cy2), (cx1, cy2),
    ])

    # Left & Right edges
    tris.extend([
        (x, cy1), (cx1, cy1), (cx1, cy2),
        (x, cy1), (cx1, cy2), (x, cy2),
        (cx2, cy1), (x + w, cy1), (x + w, cy2),
        (cx2, cy1), (x + w, cy2), (cx2, cy2),
    ])

    # Bottom & Top edges
    tris.extend([
        (cx1, y), (cx2, y), (cx2, cy1),
        (cx1, y), (cx2, cy1), (cx1, cy1),
        (cx1, cy2), (cx2, cy2), (cx2, y + h),
        (cx1, cy2), (cx2, y + h), (cx1, y + h),
    ])

    # 4 Corner Arcs
    corners = [
        (cx2, cy2, 0.0, 0.5 * math.pi),            # Top-Right
        (cx1, cy2, 0.5 * math.pi, math.pi),        # Top-Left
        (cx1, cy1, math.pi, 1.5 * math.pi),        # Bottom-Left
        (cx2, cy1, 1.5 * math.pi, 2.0 * math.pi),  # Bottom-Right
    ]

    for center_x, center_y, start_angle, end_angle in corners:
        angle_step = (end_angle - start_angle) / segments
        for i in range(segments):
            a1 = start_angle + i * angle_step
            a2 = start_angle + (i + 1) * angle_step
            p1 = (center_x + r * math.cos(a1), center_y + r * math.sin(a1))
            p2 = (center_x + r * math.cos(a2), center_y + r * math.sin(a2))
            tris.extend([(center_x, center_y), p1, p2])

    return tris


def draw_rounded_rect(
    x: float, y: float, w: float, h: float, radius: float, color: Tuple[float, float, float, float]
) -> None:
    """Draw a filled rounded rectangle with given color."""
    if w <= 0 or h <= 0:
        return
    shader = get_uniform_shader()
    tris = build_rounded_rect_tris(x, y, w, h, radius)
    batch = batch_for_shader(shader, "TRIS", {"pos": tris})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_rounded_shadow(
    x: float, y: float, w: float, h: float, radius: float, shadow_size: float = 12.0
) -> None:
    """Draw smooth multi-pass drop shadow behind a rounded rectangle."""
    passes = 4
    for i in range(passes):
        spread = shadow_size * ((i + 1) / passes)
        alpha = 0.04 * (1.0 - (i / passes))
        draw_rounded_rect(
            x - spread,
            y - spread - (shadow_size * 0.4),
            w + 2 * spread,
            h + 2 * spread,
            radius + spread,
            (0.02, 0.02, 0.03, alpha),
        )


def draw_text(
    text: str,
    x: float,
    y: float,
    size: int = 14,
    color: Tuple[float, float, float, float] = TEXT,
    font_id: int = 0,
) -> Tuple[float, float]:
    """Draw 2D text using Blender's blf module; returns (width, height)."""
    blf.size(font_id, size)
    blf.color(font_id, *color)
    blf.position(font_id, x, y, 0.0)
    blf.draw(font_id, text)
    return blf.dimensions(font_id, text)


def wrap_text(text: str, max_width: float, size: int, font_id: int = 0) -> List[str]:
    """Wrap text to pixel width while preserving explicit newlines."""
    blf.size(font_id, size)
    if max_width <= 0:
        return [text or ""]

    def split_long_word(word: str) -> Tuple[List[str], str]:
        """Split an unbroken token so it cannot escape the input rectangle."""
        fragments: List[str] = []
        current = ""
        for char in word:
            candidate = current + char
            if current and blf.dimensions(font_id, candidate)[0] > max_width:
                fragments.append(current)
                current = char
            else:
                current = candidate
        return fragments, current

    lines: List[str] = []
    for paragraph in (text or "").split("\n") or [""]:
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if current and blf.dimensions(font_id, candidate)[0] <= max_width:
                current = candidate
            elif current:
                lines.append(current)
                fragments, current = split_long_word(word)
                lines.extend(fragments)
            else:
                fragments, current = split_long_word(word)
                lines.extend(fragments)
        lines.append(current)
    return lines or [""]


def text_width(text: str, size: int, font_id: int = 0) -> float:
    """Pixel width of text at the given size."""
    blf.size(font_id, size)
    return blf.dimensions(font_id, text)[0]


def fit_text(text: str, max_width: float, size: int) -> str:
    """Shorten text with an ellipsis so it fits max_width pixels."""
    text = (text or "").replace("\n", " ")
    if text_width(text, size) <= max_width:
        return text
    while text and text_width(text + "…", size) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def draw_button(
    key: str,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    size: int = 10,
    accent: Tuple[float, float, float, float] = None,
) -> None:
    """Draw a small clickable pill and register its rect under `key` for hit testing."""
    overlay_state.buttons[key] = (x, y, w, h)
    hover = overlay_state.hover_element == key
    base = CTRL if not hover else CTRL_HOVER
    draw_rounded_rect(x, y, w, h, 7.0, base)
    color = accent or TEXT
    label = fit_text(label, w - 14.0, size)
    lw = text_width(label, size)
    draw_text(label, x + (w - lw) / 2.0, y + (h - size) / 2.0 + 1.0, size=size, color=color)


def draw_panel_frame(x: float, y: float, w: float, h: float) -> None:
    """Shared drawer chrome; also registered as a click sink so clicks do not reach the scene."""
    draw_rounded_shadow(x, y, w, h, 16.0, shadow_size=12.0)
    draw_rounded_rect(x - 1, y - 1, w + 2, h + 2, 17.0, BORDER)
    draw_rounded_rect(x, y, w, h, 16.0, SURFACE)
    overlay_state.buttons["panel_bg"] = (x, y, w, h)


def draw_menu_panel(x: float, y: float, w: float) -> float:
    """Menu drawer: MCP bridge, task undo, history clear, diagnostics, settings. Returns its height."""
    items = menu_items(overlay_state.mcp, overlay_state.task_open_steps)
    rows = (len(items) + 1) // 2
    btn_h, gap = 28.0, 8.0
    h = 18.0 + 22.0 + 22.0 + rows * (btn_h + gap) + 24.0
    draw_panel_frame(x, y, w, h)

    top = y + h
    draw_text("Menu", x + 18.0, top - 28.0, size=12, color=ACCENT)
    if overlay_state.model_label:
        label = fit_text(overlay_state.model_label, w * 0.55, 10)
        draw_text(label, x + w - 18.0 - text_width(label, 10), top - 27.0, size=10, color=TEXT_FAINT)
    running = overlay_state.mcp.get("running")
    dot = OK if running else TEXT_FAINT
    draw_text("●", x + 18.0, top - 50.0, size=10, color=dot)
    draw_text(fit_text(mcp_summary(overlay_state.mcp), w - 56.0, 10), x + 34.0, top - 50.0, size=10,
              color=TEXT_DIM)

    col_w = (w - 36.0 - gap) / 2.0
    row_top = top - 60.0
    for idx, (key, label) in enumerate(items):
        col, row = idx % 2, idx // 2
        bx = x + 18.0 + col * (col_w + gap)
        by = row_top - (row + 1) * (btn_h + gap) + gap
        accent = WARN if key == "task:undo" else None
        draw_button(key, bx, by, col_w, btn_h, label, size=11, accent=accent)

    if overlay_state.log_path:
        draw_text(fit_text("Log: " + overlay_state.log_path, w - 36.0, 9), x + 18.0, y + 10.0, size=9,
                  color=TEXT_FAINT)
    return h


def draw_settings_panel(x: float, y: float, w: float) -> float:
    """Settings drawer: provider, URL, model, masked API key, timeout, network status, test. Returns height."""
    values = overlay_state.settings_values
    provider = values.get("provider", "openai_compatible")
    fields = visible_fields(provider)
    row_h, row_gap, pad = 28.0, 6.0, 18.0
    note = provider_note(provider, values.get("model", ""))
    h = 44.0 + len(fields) * (row_h + row_gap) + 44.0 + (16.0 if note else 0.0) + 40.0 + (36.0 if provider == "agy_cli" else 0.0)
    draw_panel_frame(x, y, w, h)

    top = y + h
    draw_text("Settings", x + pad, top - 28.0, size=12, color=ACCENT)
    hint = "Enter applies · Esc cancels" if overlay_state.settings_editor else "Click a field to edit"
    draw_text(hint, x + w - pad - text_width(hint, 10), top - 27.0, size=10, color=TEXT_FAINT)

    label_w = 74.0
    box_x = x + pad + label_w
    box_w = w - 2 * pad - label_w
    cursor = top - 40.0
    editor = overlay_state.settings_editor
    for field in fields:
        by = cursor - row_h
        draw_text(LABELS[field], x + pad, by + 9.0, size=10, color=TEXT_DIM)
        editing = editor is not None and editor.field == field
        if field == "timeout":
            step_w = 28.0
            val_w = box_w - 2 * (step_w + 4.0)
            draw_button("set:timeout:-", box_x, by, step_w, row_h, "−", size=13)
            draw_rounded_rect(box_x + step_w + 4.0, by, val_w, row_h, RADIUS_CTRL, CTRL)
            label = display_value(field, values, None)
            draw_text(label, box_x + step_w + 4.0 + (val_w - text_width(label, 11)) / 2.0, by + 9.0, size=11, color=TEXT)
            draw_button("set:timeout:+", box_x + box_w - step_w, by, step_w, row_h, "+", size=13)
        else:
            overlay_state.buttons["set:" + field] = (box_x, by, box_w, row_h)
            hover = overlay_state.hover_element == "set:" + field
            if editing:
                draw_rounded_rect(box_x - 1, by - 1, box_w + 2, row_h + 2, RADIUS_CTRL + 1, ACCENT)
                draw_rounded_rect(box_x, by, box_w, row_h, RADIUS_CTRL, SURFACE_2)
            else:
                draw_rounded_rect(box_x, by, box_w, row_h, RADIUS_CTRL, CTRL_HOVER if hover else CTRL)
            text = display_value(field, values, editor)
            muted = field == "api_key" and not editing and text == "not set"
            shown = fit_text(text, box_w - 24.0, 11)
            if editing and overlay_state.cursor_visible:
                shown += "▏"
            suffix = "  ›" if field == "provider" else ""
            draw_text(shown + suffix, box_x + 10.0, by + 9.0, size=11, color=TEXT_FAINT if muted else TEXT)
        cursor = by - row_gap

    level, status = online_status(provider, values.get("base_url", ""), overlay_state.online_access)
    dot = {"ok": OK, "warn": WARN, "info": TEXT_FAINT}[level]
    draw_text("●", x + pad, cursor - 14.0, size=10, color=dot)
    draw_text(fit_text(status, w - 2 * pad - 16.0, 10), x + pad + 16.0, cursor - 14.0, size=10,
              color=WARN if level == "warn" else TEXT_DIM)
    test = overlay_state.settings_test
    if test["state"] != "idle":
        col = {"running": TEXT_DIM, "ok": OK, "fail": DANGER}[test["state"]]
        msg = "Testing…" if test["state"] == "running" else test["msg"]
        draw_text(fit_text(msg, w - 2 * pad - 16.0, 10), x + pad + 16.0, cursor - 30.0, size=10, color=col)
    if note:
        draw_text(note, x + pad, cursor - 46.0, size=10, color=TEXT_FAINT)

    if provider == "agy_cli":
        half = (w - 2 * pad - 8.0) / 2.0
        draw_button("set:agy_login", x + pad, y + 42.0, half, 26.0, "Sign in with Google", size=10)
        draw_button("set:agy_verify", x + pad + half + 8.0, y + 42.0, half, 26.0, "Verify sign-in", size=10)
    btn_w = (w - 2 * pad - 3 * 8.0) / 4.0
    for idx, (key, label) in enumerate((("set:test", "Test connection"), ("set:save", "Save"),
                                        ("set:reload", "Reload"), ("set:prefs", "Blender prefs"))):
        draw_button(key, x + pad + idx * (btn_w + 8.0), y + 10.0, btn_w, 26.0, label, size=10,
                    accent=ACCENT if key == "set:test" else None)
    return h


def draw_history_panel(x: float, y: float, w: float) -> float:
    """History drawer: last conversation turns, response copy and per-tool copy chips. Returns height."""
    turns = overlay_state.history[-3:]
    pad = 18.0
    blocks = []
    for turn in turns:
        body = turn["error"] or turn["response"]
        lines = wrap_text(body, w - 2 * pad, 10)[:2] if body else []
        chips_h = 26.0 if turn["tools"] else 0.0
        blocks.append((turn, lines, 8.0 + 18.0 + len(lines) * 14.0 + chips_h + 6.0))
    content_h = sum(b[2] for b in blocks) if blocks else 26.0
    h = 40.0 + content_h + 6.0
    draw_panel_frame(x, y, w, h)

    top = y + h
    total = len(overlay_state.history)
    draw_text("History" + (f" · {total}" if total else ""), x + pad, top - 28.0, size=12, color=ACCENT)
    if not blocks:
        draw_text("No conversation yet.", x + pad, top - 56.0, size=11, color=TEXT_FAINT)
        return h

    cursor = top - 40.0
    for turn, lines, bh in blocks:
        block_top = cursor
        draw_text("You", x + pad, block_top - 22.0, size=10, color=TEXT_DIM)
        copy_w = 52.0
        has_copy = bool(turn["response"])
        prompt_w = w - 2 * pad - 34.0 - (copy_w + 8.0 if has_copy else 0.0)
        draw_text(fit_text(turn["prompt"], prompt_w, 11), x + pad + 34.0, block_top - 22.0, size=11,
                  color=TEXT)
        if has_copy:
            draw_button("hist:copy:" + turn["turn_id"], x + w - pad - copy_w, block_top - 26.0, copy_w, 20.0, "Copy")
        ly = block_top - 40.0
        err = bool(turn["error"])
        for line in lines:
            draw_text(line, x + pad, ly, size=10,
                      color=DANGER if err else TEXT_DIM)
            ly -= 14.0
        if turn["tools"]:
            chip_x = x + pad
            chip_y = block_top - bh + 6.0
            shown = 0
            for t_idx, tool in enumerate(turn["tools"]):
                label = f"{format_tool_status_icon(tool['status'])} {tool['tool_name']}"
                cw = min(text_width(label, 10) + 16.0, 170.0)
                remaining = len(turn["tools"]) - t_idx
                if chip_x + cw > x + w - pad - (44.0 if remaining > 1 else 0.0):
                    break
                draw_button(f"hist:tool:{turn['turn_id']}:{t_idx}", chip_x, chip_y, cw, 20.0, label)
                chip_x += cw + 6.0
                shown += 1
            if shown < len(turn["tools"]):
                draw_text(f"+{len(turn['tools']) - shown}", chip_x + 2.0, chip_y + 5.0, size=10,
                          color=TEXT_DIM)
        cursor -= bh
    return h


def draw_overlay_hud(context) -> None:
    """Primary Viewport draw callback rendering the floating Blender Copilot HUD."""
    if not overlay_state.is_open:
        return

    region = context.region
    if not region:
        return

    reg_w = region.width
    reg_h = region.height

    # Responsive dimensions. The input grows vertically when a prompt wraps;
    # this keeps long prompts readable instead of drawing them beyond the HUD.
    bar_w = min(680.0, max(460.0, reg_w - 60.0))
    input_w = bar_w - 180.0
    prompt = overlay_state.prompt_text
    prompt_lines = wrap_text(prompt, input_w - 4.0, 14) if prompt else [""]
    input_line_count = max(1, len(prompt_lines))
    bar_h = 74.0 + max(0, input_line_count - 1) * 16.0
    bar_x = (reg_w - bar_w) / 2.0
    bar_y = 42.0
    corner_r = 18.0

    overlay_state.bar_rect = (bar_x, bar_y, bar_w, bar_h)
    overlay_state.response_copy_btn_rect = (0.0, 0.0, 0.0, 0.0)
    overlay_state.buttons = {}

    # Enable alpha blending
    gpu.state.blend_set("ALPHA")

    # 1. Outer Drop Shadow
    draw_rounded_shadow(bar_x, bar_y, bar_w, bar_h, corner_r, shadow_size=16.0)

    # 2. Main Background Container & Thin Border
    draw_rounded_rect(bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2, corner_r + 1, BORDER)
    draw_rounded_rect(bar_x, bar_y, bar_w, bar_h, corner_r, SURFACE)

    # -------------------------------------------------------------------------
    # 3. Upper Row: Prompt Input & Sparkle Icon
    # -------------------------------------------------------------------------
    sparkle_x = bar_x + 18.0
    sparkle_y = bar_y + bar_h - 28.0
    # Sparkle icon
    draw_text("✦", sparkle_x, sparkle_y, size=15, color=ACCENT)

    input_x = sparkle_x + 22.0
    input_y = sparkle_y
    input_h = input_line_count * 16.0 + 8.0
    overlay_state.input_rect = (input_x, input_y - input_h + 4.0, input_w, input_h)

    # Display prompt or placeholder
    if prompt:
        # Draw user typed text
        text_y = input_y
        for line in prompt_lines:
            draw_text(line, input_x, text_y, size=14, color=TEXT)
            text_y -= 16.0

        # Cursor line calculation uses the same wrapping rules as the prompt.
        prefix_lines = wrap_text(prompt[:overlay_state.cursor_pos], input_w - 4.0, 14)
        cursor_line = prefix_lines[-1] if prefix_lines else ""
        cursor_line_index = max(0, len(prefix_lines) - 1)
        blf.size(0, 14)
        cur_offset = blf.dimensions(0, cursor_line)[0]
        if overlay_state.cursor_visible:
            cur_x = input_x + cur_offset + 1.0
            cur_y = input_y - cursor_line_index * 16.0 - 2.0
            draw_rounded_rect(cur_x, cur_y, 2.0, 16.0, 1.0, ACCENT)
    else:
        # Placeholder
        draw_text("Ask Blender…", input_x, input_y, size=13, color=TEXT_FAINT)
        if overlay_state.cursor_visible:
            draw_rounded_rect(input_x, input_y - 2.0, 2.0, 16.0, 1.0, ACCENT)

    # -------------------------------------------------------------------------
    # 4. Action Button (right side)
    # -------------------------------------------------------------------------
    btn_w = 110.0
    btn_h = 44.0
    btn_x = bar_x + bar_w - btn_w - 14.0
    btn_y = bar_y + (bar_h - btn_h) / 2.0
    btn_r = 14.0

    is_processing = overlay_state.is_processing
    if not is_processing:
        overlay_state.send_btn_rect = (btn_x, btn_y, btn_w, btn_h)
        overlay_state.cancel_btn_rect = (0, 0, 0, 0)
        btn_hover = overlay_state.hover_element == "send"
        can_send = bool(overlay_state.prompt_text.strip())  # an empty prompt sends nothing: show it as idle
        if can_send:
            btn_color, ink = (ACCENT_HOVER if btn_hover else ACCENT), ACCENT_INK
        else:
            btn_color, ink = CTRL, TEXT_FAINT
        draw_rounded_rect(btn_x, btn_y, btn_w, btn_h, btn_r, btn_color)
        text_w = text_width("Send", 12)
        draw_text("Send", btn_x + (btn_w - text_w) / 2.0, btn_y + 15.0, size=12, color=ink)
    else:
        overlay_state.cancel_btn_rect = (btn_x, btn_y, btn_w, btn_h)
        overlay_state.send_btn_rect = (0, 0, 0, 0)
        btn_hover = overlay_state.hover_element == "cancel"
        draw_rounded_rect(btn_x, btn_y, btn_w, btn_h, btn_r, DANGER if btn_hover else DANGER_FILL)
        text_w = text_width("Stop", 12)
        draw_text("Stop", btn_x + (btn_w - text_w) / 2.0, btn_y + 15.0, size=12,
                  color=ACCENT_INK if btn_hover else DANGER)

    # -------------------------------------------------------------------------
    # 5. Bottom Row: pills
    # -------------------------------------------------------------------------
    pill_y = bar_y + 12.0
    pill_h = 22.0
    pill_r = 6.0

    # Pills: History and Menu toggles (clickable), then the status / toast pill.
    send_left = bar_x + bar_w - 110.0 - 14.0 - 10.0
    pill_x = sparkle_x

    hist_n = len(overlay_state.history)
    hist_label = f"History {hist_n}" if hist_n else "History"
    hist_w = text_width(hist_label, 10) + 20.0
    draw_button("pill:history", pill_x, pill_y, hist_w, pill_h, hist_label,
                accent=ACCENT if overlay_state.panel == "history" else TEXT_DIM)
    pill_x += hist_w + 8.0

    menu_w = text_width("Menu", 10) + 20.0
    draw_button("pill:menu", pill_x, pill_y, menu_w, pill_h, "Menu",
                accent=ACCENT if overlay_state.panel == "menu" else TEXT_DIM)
    pill_x += menu_w + 8.0

    toast = overlay_state.active_toast()
    status_label = f"✓ {toast}" if toast else f"● {overlay_state.status_text}"
    status_label = fit_text(status_label, max(60.0, send_left - pill_x - 18.0), 10)
    p2_w = text_width(status_label, 10) + 18.0
    draw_rounded_rect(pill_x, pill_y, p2_w, pill_h, pill_r, CTRL)
    status = str(overlay_state.status_text)
    if status == "ERROR":
        status_col = DANGER
    elif is_processing or status == "PENDING_APPROVAL":
        status_col = WARN
    else:
        status_col = OK
    draw_text(status_label, pill_x + 8.0, pill_y + 6.0, size=10, color=status_col)
    pill_x += p2_w + 8.0

    hint_w = text_width("Esc to close", 10) + 20.0
    if pill_x + hint_w <= send_left:
        draw_rounded_rect(pill_x, pill_y, hint_w, pill_h, pill_r, CTRL)
        draw_text("Esc to close", pill_x + 10.0, pill_y + 6.0, size=10, color=TEXT_FAINT)

    # -------------------------------------------------------------------------
    # 6. Conversation drawers: submitted user turn, then approval/response
    # -------------------------------------------------------------------------
    content_y = bar_y + bar_h + 10.0
    if overlay_state.panel in ("menu", "history", "settings"):
        # A drawer replaces the conversation cards; the approval card below still shows.
        if overlay_state.panel == "menu":
            panel_h = draw_menu_panel(bar_x, content_y, bar_w)
        elif overlay_state.panel == "settings":
            panel_h = draw_settings_panel(bar_x, content_y, bar_w)
        else:
            panel_h = draw_history_panel(bar_x, content_y, bar_w)
        content_y += panel_h + 8.0
        show_conversation = False
    else:
        show_conversation = True
    if show_conversation and overlay_state.last_prompt_text:
        user_lines = wrap_text(overlay_state.last_prompt_text, bar_w - 36.0, 11)
        user_lines = user_lines[:2]
        user_h = 42.0 + len(user_lines) * 16.0
        user_x = bar_x
        user_y = content_y
        overlay_state.buttons["card:prompt"] = (user_x, user_y, bar_w, user_h)  # click sink
        draw_rounded_shadow(user_x, user_y, bar_w, user_h, 14.0, shadow_size=10.0)
        draw_rounded_rect(user_x, user_y, bar_w, user_h, 14.0, SURFACE_2)
        draw_text("You", user_x + 16.0, user_y + user_h - 20.0, size=11, color=TEXT_DIM)
        user_text_y = user_y + user_h - 38.0
        for line in user_lines:
            draw_text(line, user_x + 16.0, user_text_y, size=11, color=TEXT)
            user_text_y -= 16.0
        content_y = user_y + user_h + 8.0

    # FIFO user prompts waiting behind the active turn. This is deliberately
    # separate from the active user card and the agent's task checklist.
    queued_prompts = list(getattr(overlay_state, "queued_prompts", []))
    if show_conversation and queued_prompts:
        shown = queued_prompts[:6]
        queue_h = 42.0 + len(shown) * 18.0
        queue_x = bar_x
        queue_y = content_y
        overlay_state.buttons["card:queue"] = (queue_x, queue_y, bar_w, queue_h)  # click sink
        draw_rounded_shadow(queue_x, queue_y, bar_w, queue_h, 14.0, shadow_size=10.0)
        draw_rounded_rect(queue_x, queue_y, bar_w, queue_h, 14.0, SURFACE_2)
        draw_text(
            f"Queued · {len(queued_prompts)} waiting",
            queue_x + 16.0,
            queue_y + queue_h - 22.0,
            size=11,
            color=TEXT,
        )
        queue_line_y = queue_y + queue_h - 40.0
        for item in shown:
            label = str(item.get("prompt", "Queued prompt")).replace("\n", " ")[:88]
            draw_text("○", queue_x + 16.0, queue_line_y, size=11, color=TEXT_FAINT)
            draw_text(label, queue_x + 34.0, queue_line_y, size=10, color=TEXT)
            queue_line_y -= 18.0
        if len(queued_prompts) > len(shown):
            draw_text(
                f"+ {len(queued_prompts) - len(shown)} more",
                queue_x + 34.0,
                queue_line_y,
                size=10,
                color=TEXT_DIM,
            )
        content_y = queue_y + queue_h + 8.0

    # OpenCode-style task checklist.  This is deliberately separate from the
    # approval card: approval answers "may I run it?", while this answers
    # "what happened to each step?".
    if show_conversation and overlay_state.task_plan and not overlay_state.pending_approval:
        task = overlay_state.task_plan
        steps = list(task.get("steps", []))[:7]
        completed = int(task.get("steps_completed", 0) or 0)
        total = int(task.get("steps_total", len(steps)) or len(steps))
        task_h = 54.0 + len(steps) * 18.0
        task_x = bar_x
        task_y = content_y
        overlay_state.buttons["card:tasks"] = (task_x, task_y, bar_w, task_h)  # click sink
        draw_rounded_shadow(task_x, task_y, bar_w, task_h, 14.0, shadow_size=10.0)
        draw_rounded_rect(task_x, task_y, bar_w, task_h, 14.0, SURFACE_2)
        draw_text(
            f"Tasks · {completed}/{total} completed",
            task_x + 16.0,
            task_y + task_h - 22.0,
            size=11,
            color=TEXT,
        )
        if overlay_state.plan_title:
            copy_plan_w = 78.0
            draw_button("plan:copy", task_x + bar_w - copy_plan_w - 14.0, task_y + task_h - 32.0, copy_plan_w, 22.0,
                        "Copy plan")
        task_line_y = task_y + task_h - 42.0
        for item in steps:
            step_status = str(item.get("status", "PENDING")).upper()
            if step_status == "COMPLETED":
                marker, marker_color = "✓", OK
            elif step_status == "FAILED":
                marker, marker_color = "✕", DANGER
            elif step_status == "RUNNING":
                marker, marker_color = "●", WARN
            else:
                marker, marker_color = "○", TEXT_FAINT
            label = item.get("description") or item.get("tool_name", "Task")
            draw_text(marker, task_x + 16.0, task_line_y, size=11, color=marker_color)
            draw_text(str(label)[:88], task_x + 34.0, task_line_y, size=10, color=TEXT)
            task_line_y -= 18.0
        content_y = task_y + task_h + 8.0

    # -------------------------------------------------------------------------
    # 7. Upper Drawer: Approval Card (High Priority) OR Response Drawer
    # -------------------------------------------------------------------------
    if overlay_state.pending_approval:
        # Approval Card takes visual precedence over regular response drawer
        appr = overlay_state.pending_approval
        card_w = bar_w
        is_plan = appr.get("kind") == "plan"
        shown_steps = appr.get("steps_shown", []) if is_plan else []
        card_h = 142.0 + min(len(shown_steps), 5) * 18.0 if is_plan else 106.0
        card_x = bar_x
        card_y = content_y
        corner_r = 16.0

        overlay_state.approval_card_rect = (card_x, card_y, card_w, card_h)

        # 1. Drop shadow & glowing warning border
        draw_rounded_shadow(card_x, card_y, card_w, card_h, corner_r, shadow_size=14.0)
        draw_rounded_rect(card_x - 1.5, card_y - 1.5, card_w + 3.0, card_h + 3.0, corner_r + 1.0, WARN)
        draw_rounded_rect(card_x, card_y, card_w, card_h, corner_r, SURFACE)

        # 2. Header row
        header = "Plan ready" if is_plan else "Confirm action"
        header_color = ACCENT if is_plan else WARN
        draw_text(header, card_x + 18.0, card_y + card_h - 24.0, size=12, color=header_color)
        appr_id = appr.get("approval_id", "")
        if appr_id:
            draw_text(appr_id, card_x + card_w - 110.0, card_y + card_h - 22.0, size=10, color=TEXT_FAINT)

        # 3. Middle row: Action Description & Risk Badge
        desc = appr.get("description", "Execute action")
        draw_text(desc, card_x + 18.0, card_y + card_h - 48.0, size=14, color=TEXT)

        if is_plan:
            step_y = card_y + card_h - 75.0
            for step in shown_steps[:5]:
                tool_name = step.get("tool_name", "tool")
                step_desc = step.get("description", "")
                label = f"✓ {tool_name}: {step_desc}" if step_desc else f"✓ {tool_name}"
                draw_text(label, card_x + 22.0, step_y, size=11, color=TEXT_DIM)
                step_y -= 18.0
            hidden_count = int(appr.get("hidden_count", 0) or 0)
            if hidden_count:
                draw_text(f"+ {hidden_count} more step(s)", card_x + 22.0, step_y, size=10, color=TEXT_DIM)

        risk = str(appr.get("risk_level", "MEDIUM")).upper()
        risk_text = f"Risk: {risk}"
        draw_rounded_rect(card_x + card_w - 120.0, card_y + card_h - 52.0, 102.0, 20.0, 5.0, SURFACE_2)
        draw_text(risk_text, card_x + card_w - 112.0, card_y + card_h - 46.0, size=10, color=WARN)

        # 4. Bottom row: Reject and Approve Buttons
        btn_h = 32.0
        btn_y = card_y + 12.0

        # Reject Button (Muted Dark Red)
        r_w = 115.0
        r_x = card_x + 18.0
        overlay_state.reject_btn_rect = (r_x, btn_y, r_w, btn_h)
        r_hover = overlay_state.hover_element == "reject"
        r_col = DANGER_FILL if r_hover else DANGER_FILL
        draw_rounded_rect(r_x - 1, btn_y - 1, r_w + 2, btn_h + 2, 8.0, DANGER)
        draw_rounded_rect(r_x, btn_y, r_w, btn_h, 7.0, r_col)
        draw_text("Reject  N", r_x + 16.0, btn_y + 10.0, size=11, color=DANGER)

        # Approve Button (Muted Dark Emerald Green with Crisp Border)
        a_w = 125.0
        a_x = card_x + card_w - a_w - 18.0
        overlay_state.approve_btn_rect = (a_x, btn_y, a_w, btn_h)
        a_hover = overlay_state.hover_element == "approve"
        a_col = OK_FILL if a_hover else OK_FILL
        draw_rounded_rect(a_x - 1, btn_y - 1, a_w + 2, btn_h + 2, 8.0, OK)
        draw_rounded_rect(a_x, btn_y, a_w, btn_h, 7.0, a_col)
        draw_text("Approve  Y", a_x + 16.0, btn_y + 10.0, size=11, color=OK)

    else:
        # Reset approval rects
        overlay_state.approval_card_rect = (0.0, 0.0, 0.0, 0.0)
        overlay_state.reject_btn_rect = (0.0, 0.0, 0.0, 0.0)
        overlay_state.approve_btn_rect = (0.0, 0.0, 0.0, 0.0)

        # Regular Response Drawer (If AI is thinking or has a response)
        overlay_state.response_copy_btn_rect = (0.0, 0.0, 0.0, 0.0)
        if show_conversation and (is_processing or overlay_state.last_response_text or overlay_state.streaming_response_text or overlay_state.active_tool_name):
            resp_text = overlay_state.streaming_response_text or overlay_state.last_response_text
            if is_processing and overlay_state.active_tool_name:
                resp_text = f"Running tool: {overlay_state.active_tool_name}..."
            elif is_processing and not resp_text:
                resp_text = "AI Thinking..."

            if resp_text:
                drawer_w = bar_w
                body_lines = wrap_text(resp_text, drawer_w - 36.0, 12)
                max_lines = max(1, min(len(body_lines), 10))
                drawer_h = 58.0 + max_lines * 18.0
                drawer_x = bar_x
                drawer_y = content_y
                overlay_state.buttons["card:response"] = (drawer_x, drawer_y, drawer_w, drawer_h)  # click sink
                # Long answers scroll with the wheel; while streaming the view follows the newest lines.
                max_scroll = max(0, len(body_lines) - max_lines)
                overlay_state.response_max_scroll = max_scroll
                first = max_scroll if is_processing and not overlay_state.response_scroll else min(overlay_state.response_scroll, max_scroll)

                # Drawer shadow & background
                draw_rounded_shadow(drawer_x, drawer_y, drawer_w, drawer_h, corner_r, shadow_size=12.0)
                draw_rounded_rect(drawer_x - 1, drawer_y - 1, drawer_w + 2, drawer_h + 2, corner_r + 1, BORDER)
                draw_rounded_rect(drawer_x, drawer_y, drawer_w, drawer_h, corner_r, SURFACE)

                # Header
                draw_text("Copilot", drawer_x + 16.0, drawer_y + drawer_h - 22.0, size=11, color=ACCENT)

                # Copy action for the complete response text.
                copy_w = 60.0
                copy_h = 22.0
                copy_x = drawer_x + drawer_w - copy_w - 14.0
                copy_y = drawer_y + drawer_h - copy_h - 10.0
                draw_button("copy_response", copy_x, copy_y, copy_w, copy_h, "Copy")
                if max_scroll:
                    pos = f"{first + 1}-{first + max_lines} / {len(body_lines)}"
                    draw_text(pos, drawer_x + 80.0, drawer_y + drawer_h - 22.0, size=10, color=TEXT_FAINT)

                # What the finished AI task changed, and one undo for all of it.
                steps = overlay_state.task_open_steps
                if steps > 0 and not is_processing:
                    undo_w, chg_w = 96.0, 94.0
                    undo_x = copy_x - undo_w - 8.0
                    draw_button("task:undo", undo_x, copy_y, undo_w, copy_h, f"Undo task ({steps})",
                                accent=WARN)
                    draw_button("task:changes", undo_x - chg_w - 8.0, copy_y, chg_w, copy_h, "What changed?")

                # Body text wraps into multiple lines instead of being truncated.
                body_y = drawer_y + drawer_h - 48.0
                for line in body_lines[first:first + max_lines]:
                    draw_text(line, drawer_x + 16.0, body_y, size=12, color=TEXT)
                    body_y -= 18.0

    # Restore default blend state
    gpu.state.blend_set("NONE")
