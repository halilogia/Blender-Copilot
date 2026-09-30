"""RigCharacter: character tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class RigCharacterTool(BaseTool):
    """Character tool `rig_character`."""

    name = "rig_character"
    description = (
        "Prepare a character for animation. The character must be made of SEPARATE parts (do not join them): head, torso (or body), arm_l and arm_r (or a left and a right arm), leg_l and leg_r (or a left and a right leg), optionally forearm_l, forearm_r (lower arms, name them forearm or lowerarm) and shin_l, shin_r (lower legs, name them shin or calf) so elbows and knees bend, plus optional accessories (helmet, boots, backpack, gun ...). Name the parts with those words, or pass parts={role: object}. The tool puts each limb's pivot at its joint (shoulder, hip, neck), attaches accessories to the nearest part and parents everything under an empty called <name>_Rig, which is what animate_character and camera_move (follow) take. The character faces +Y; its right side is +X. Roles: head, torso, arm_l, arm_r, leg_l, leg_r, forearm_l, forearm_r, shin_l, shin_r."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Character name, for example Soldier (the rig is called Soldier_Rig)."},
            "object_names": {"type": "array", "items": {"type": "string"}, "description": "Every mesh object of the character, accessories included."},
            "parts": {"type": "object", "description": "Optional explicit mapping such as {\"torso\": \"Body\", \"arm_l\": \"LeftArm\"}; roles head, torso, arm_l, arm_r, leg_l, leg_r, forearm_l, forearm_r, shin_l, shin_r."},
        },
        "required": ["name", "object_names"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.rig_character(**kwargs)
