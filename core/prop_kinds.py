"""What create_prop can build (plain data, no bpy): kind -> (default height in meters, one line, ready for rig_character)."""

from typing import Dict, Tuple

KIND_INFO: Dict[str, Tuple[float, str, bool]] = {
    "crate": (1.0, "wooden crate with corner posts and a lid", False),
    "barrel": (1.0, "wooden barrel with metal bands", False),
    "tree_pine": (4.0, "pine tree, four cone tiers", False),
    "tree_round": (4.0, "round leafy tree", False),
    "rock": (1.0, "cluster of three boulders", False),
    "house": (3.0, "village house: walls, tiled roof, door, windows, chimney", False),
    "tower": (6.0, "wooden watchtower with railing, roof and ladder", False),
    "fence": (1.0, "wooden fence section, three heights long", False),
    "lamp": (3.5, "street lamp with a glowing bulb", False),
    "tent": (2.0, "camping tent with a door and pegs", False),
    "well": (2.0, "stone well with roof, water and bucket", False),
    "car": (1.4, "simple car, four wheels, glass cabin, lights", False),
    "chest": (0.6, "treasure chest with round lid, bands and lock", False),
    "table": (0.8, "wooden table", False),
    "chair": (1.0, "wooden chair", False),
    "campfire": (1.0, "stone ring, logs and flames", False),
    "humanoid": (1.8, "person made of parts (head, torso, arms with forearms, legs with shins, boots, eyes, mouth, hair), ready for rig_character", True),
    "robot": (1.8, "robot made of the same parts with antenna and chest panel, ready for rig_character", True),
}
