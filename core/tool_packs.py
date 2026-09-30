"""Tool packs: send a model only the tools its request needs (pure Python, no bpy).

The full toolset is about 10,000 tokens of descriptions. A small or free model with a short context pays for that on every
message and gets slower and more error-prone. Tools are therefore grouped into packs; the modeling core is always sent,
the film and character packs load when the request talks about them (keywords, both languages) or when the model calls
``enable_tools``. Over MCP every tool stays visible: those clients handle long tool lists themselves.
"""

from typing import Iterable, List, Sequence, Set

PACKS = {
    "film": (
        "set_environment", "camera_move", "camera_settings", "set_look", "render_image", "render_contact_sheet",
        "render_animation", "render_shots", "edit_video", "make_soundtrack", "check_shot",
    ),
    "characters": ("rig_character", "animate_character", "animate_sequence", "character_library"),
    "textures": ("unwrap_uv", "bake_material"),
}

ABOUT = {
    "film": "light, camera moves, render, colour looks, video editing, music",
    "characters": "rig a character made of parts and animate it: walk, talk, expressions, scenes",
    "textures": "UV unwrap and bake procedural materials into image textures (so a .glb keeps the look)",
}

KEYWORDS = {
    "film": ("video", "film", "movie", "mp4", "render", "camera", "kamera", "çekim", "cekim", "sahne çek", "shot", "orbit",
             "dolly", "crane", "zoom", "ışık", "isik", "light", "lighting", "sunset", "gün batımı", "gun batimi", "müzik",
             "muzik", "music", "soundtrack", "slow motion", "yavaş çekim", "yavas cekim", "trailer", "animasyon", "animation",
             "clip", "klip"),
    "characters": ("character", "karakter", "walk", "yürü", "yuru", "run", "koş", "kos", "talk", "konuş", "konus", "rig",
                   "animate", "animasyon", "animation", "asker", "soldier", "robot", "zombi", "zombie", "insan", "human",
                   "person", "wave", "el salla", "jump", "zıpla", "zipla", "expression", "yüz", "yuz", "face", "dans", "dance"),
    "textures": ("uv map", "uv harita", "uv unwrap", "unwrap", "texture", "doku", "bake", "pişir", "pisir", "pbr", "kaplama", "glb", "gltf", "godot", "unity", "game asset", "oyun için"),
}
# a character request is nearly always filmed as well
IMPLIES = {"characters": ("film",)}


def packs_for_text(text: str) -> Set[str]:
    """Packs a user request calls for, judged from its words."""
    low = str(text or "").lower()
    found = {pack for pack, words in KEYWORDS.items() if any(w in low for w in words)}
    for pack in list(found):
        found.update(IMPLIES.get(pack, ()))
    return found


def pack_of(tool_name: str) -> str:
    for pack, names in PACKS.items():
        if tool_name in names:
            return pack
    return ""


def filter_tools(tools: Sequence, active: Iterable[str]) -> List:
    """Tools to send now: everything outside a pack, plus the packs that are active."""
    on = set(active)
    return [t for t in tools if not pack_of(t.name) or pack_of(t.name) in on]


def valid_packs(names: Iterable[str]) -> List[str]:
    return [n for n in names if n in PACKS]
