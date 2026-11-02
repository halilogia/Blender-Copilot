"""AssetSpec: Semantic Intermediate Representation (IR) and Constraint Solver.

Enables pure text LLMs to specify high-level 3D design intent without guessing
arbitrary 3D coordinates. The constraint solver computes mathematically coupled,
watertight, manifold geometric bounds, sockets, and features ready for the
Blender geometry compiler and Godot game engine export.

Pure Python — 100% testable without Blender dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AssetFamily(str, Enum):
    """Broad categories of game assets."""
    VEHICLE = "vehicle"
    PROP = "prop"
    STRUCTURE = "structure"
    CHARACTER = "character"
    WEAPON = "weapon"


class CollisionType(str, Enum):
    """Godot-compatible collision generation hints."""
    COMPOUND_CONVEX = "COMPOUND_CONVEX"  # -convcol per functional part
    CONVEX = "CONVEX"                    # -convcol for the whole joined mesh
    BOX = "BOX"                          # -col box hull
    TRIMESH = "TRIMESH"                  # -colonly static world collision
    NONE = "NONE"


class PivotPlacement(str, Enum):
    """Where to place the object's origin point."""
    BOTTOM_CENTER = "BOTTOM_CENTER"  # Recommended for game engines (feet/wheels on ground)
    CENTER = "CENTER"
    TOP_CENTER = "TOP_CENTER"


@dataclass
class AssetDimensions:
    """Real-world dimensions in meters."""
    length: float  # Along Y axis (front/back in Blender)
    width: float   # Along X axis (left/right in Blender)
    height: float  # Along Z axis (up/down in Blender)

    def to_dict(self) -> Dict[str, float]:
        return {"length": self.length, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetDimensions":
        return cls(
            length=float(data.get("length", 1.0)),
            width=float(data.get("width", 1.0)),
            height=float(data.get("height", 1.0)),
        )


@dataclass
class ExportSpec:
    """Packaging and engine delivery rules."""
    format: str = "GLB"
    collision: CollisionType = CollisionType.COMPOUND_CONVEX
    pivot: PivotPlacement = PivotPlacement.BOTTOM_CENTER
    triangle_budget: int = 5000
    generate_lod: bool = True
    recenter: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": self.format,
            "collision": self.collision.value,
            "pivot": self.pivot.value,
            "triangle_budget": self.triangle_budget,
            "generate_lod": self.generate_lod,
            "recenter": self.recenter,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportSpec":
        col_str = str(data.get("collision", "COMPOUND_CONVEX")).upper()
        piv_str = str(data.get("pivot", "BOTTOM_CENTER")).upper()
        col = CollisionType[col_str] if col_str in CollisionType.__members__ else CollisionType.COMPOUND_CONVEX
        piv = PivotPlacement[piv_str] if piv_str in PivotPlacement.__members__ else PivotPlacement.BOTTOM_CENTER
        return cls(
            format=str(data.get("format", "GLB")),
            collision=col,
            pivot=piv,
            triangle_budget=int(data.get("triangle_budget", 5000)),
            generate_lod=bool(data.get("generate_lod", True)),
            recenter=bool(data.get("recenter", True)),
        )


@dataclass
class AssetSpec:
    """Semantic model specification produced by LLMs."""
    asset_id: str
    family: AssetFamily
    recipe: str
    dimensions: AssetDimensions
    style: str = "stylized_lowpoly"
    parameters: Dict[str, float] = field(default_factory=dict)
    features: Dict[str, bool] = field(default_factory=dict)
    materials: Dict[str, str] = field(default_factory=dict)
    export: ExportSpec = field(default_factory=ExportSpec)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "family": self.family.value,
            "recipe": self.recipe,
            "style": self.style,
            "dimensions": self.dimensions.to_dict(),
            "parameters": dict(sorted(self.parameters.items())),
            "features": dict(sorted(self.features.items())),
            "materials": dict(sorted(self.materials.items())),
            "export": self.export.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetSpec":
        fam_str = str(data.get("family", "prop")).lower()
        family = AssetFamily(fam_str) if fam_str in [f.value for f in AssetFamily] else AssetFamily.PROP
        dims = AssetDimensions.from_dict(data.get("dimensions", {}))
        export = ExportSpec.from_dict(data.get("export", {}))

        raw_params = data.get("parameters", {})
        params = {k: float(v) for k, v in raw_params.items() if isinstance(v, (int, float))}

        raw_features = data.get("features", {})
        features = {k: bool(v) for k, v in raw_features.items()}

        raw_materials = data.get("materials", {})
        materials = {k: str(v) for k, v in raw_materials.items()}

        return cls(
            asset_id=str(data.get("asset_id", "asset_01")),
            family=family,
            recipe=str(data.get("recipe", "generic")),
            style=str(data.get("style", "stylized_lowpoly")),
            dimensions=dims,
            parameters=params,
            features=features,
            materials=materials,
            export=export,
        )


@dataclass
class SocketDefinition:
    """Calculated attachment point for secondary kitbash / functional parts."""
    name: str
    location: Tuple[float, float, float]
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    normal: Tuple[float, float, float] = (0.0, 0.0, 1.0)
    category: str = "generic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "location": list(self.location),
            "rotation": list(self.rotation),
            "normal": list(self.normal),
            "category": self.category,
        }


@dataclass
class ResolvedPart:
    """A mathematically solved geometric block ready for creation."""
    name: str
    primitive: str  # "CUBE", "CYLINDER", "LOFT", etc.
    location: Tuple[float, float, float]
    dimensions: Tuple[float, float, float]  # scale / dimensions (X, Y, Z)
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    material_slot: str = "body"
    bevel_width: float = 0.0
    cutter: bool = False
    parent_part: Optional[str] = None
    socket_name: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "name": self.name,
            "primitive": self.primitive,
            "location": list(self.location),
            "dimensions": list(self.dimensions),
            "rotation": list(self.rotation),
            "material_slot": self.material_slot,
            "bevel_width": self.bevel_width,
            "cutter": self.cutter,
        }
        if self.parent_part:
            res["parent_part"] = self.parent_part
        if self.socket_name:
            res["socket_name"] = self.socket_name
        if self.meta:
            res["meta"] = self.meta
        return res


@dataclass
class ResolvedAssetPlan:
    """The complete mathematical compilation result ready for Blender."""
    asset_id: str
    parts: List[ResolvedPart]
    sockets: Dict[str, SocketDefinition]
    materials: Dict[str, str]
    export: ExportSpec

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "parts": [p.to_dict() for p in self.parts],
            "sockets": {k: v.to_dict() for k, v in sorted(self.sockets.items())},
            "materials": dict(sorted(self.materials.items())),
            "export": self.export.to_dict(),
        }


class SpecValidationError(Exception):
    """Raised when an AssetSpec fails geometric consistency or bounds rules."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


def validate_asset_spec(spec: AssetSpec) -> List[str]:
    """Validate AssetSpec for physical sense, manifold safety, and constraint bounds.
    
    Returns a list of human-readable error messages (empty if valid).
    """
    errors: List[str] = []

    # 1. Dimensional sanity (must be positive, non-zero, within plausible game scale)
    if spec.dimensions.length <= 0:
        errors.append(f"dimensions.length must be positive (got {spec.dimensions.length})")
    if spec.dimensions.width <= 0:
        errors.append(f"dimensions.width must be positive (got {spec.dimensions.width})")
    if spec.dimensions.height <= 0:
        errors.append(f"dimensions.height must be positive (got {spec.dimensions.height})")

    # 2. Bevel width safety (prevent self-intersecting / inverted geometry)
    bevel_w = spec.parameters.get("bevel_width", 0.03)
    if bevel_w < 0:
        errors.append(f"parameters.bevel_width cannot be negative (got {bevel_w})")
    min_dim = min(spec.dimensions.length, spec.dimensions.width, spec.dimensions.height)
    if bevel_w > min_dim * 0.25:
        errors.append(
            f"parameters.bevel_width ({bevel_w:.3f}m) exceeds 25% of smallest dimension ({min_dim:.3f}m); "
            "will cause inverted normals or mesh collapse"
        )

    # 3. Vehicle recipe constraints
    if spec.family == AssetFamily.VEHICLE:
        wb_ratio = spec.parameters.get("wheelbase_ratio", 0.65)
        if not (0.35 <= wb_ratio <= 0.88):
            errors.append(f"vehicle wheelbase_ratio must be between 0.35 and 0.88 (got {wb_ratio})")

        track_ratio = spec.parameters.get("track_width_ratio", 0.82)
        if not (0.45 <= track_ratio <= 1.05):
            errors.append(f"vehicle track_width_ratio must be between 0.45 and 1.05 (got {track_ratio})")

        wheel_r = spec.parameters.get("wheel_radius", 0.35)
        if wheel_r <= 0 or wheel_r > spec.dimensions.height * 0.45:
            errors.append(f"vehicle wheel_radius ({wheel_r}m) is invalid for height ({spec.dimensions.height}m)")

        cabin_h_ratio = spec.parameters.get("cabin_height_ratio", 0.45)
        if not (0.2 <= cabin_h_ratio <= 0.75):
            errors.append(f"vehicle cabin_height_ratio must be between 0.2 and 0.75 (got {cabin_h_ratio})")

    # 4. Triangle budget check
    if spec.export.triangle_budget < 100:
        errors.append(f"export.triangle_budget must be >= 100 (got {spec.export.triangle_budget})")

    return errors


def solve_asset_constraints(spec: AssetSpec) -> ResolvedAssetPlan:
    """Compile high-level AssetSpec into exact mathematical part definitions and sockets.
    
    Couples relative parameters to ground Z=0 and proper coordinate axes:
    - X: Width (Left/Right)
    - Y: Length (Front +Y / Back -Y in Blender coordinate space)
    - Z: Height (Up +Z)
    """
    errors = validate_asset_spec(spec)
    if errors:
        raise SpecValidationError(
            f"AssetSpec validation failed with {len(errors)} error(s): " + "; ".join(errors),
            details={"errors": errors, "asset_id": spec.asset_id}
        )

    if spec.family == AssetFamily.VEHICLE:
        return _solve_vehicle_spec(spec)
    elif spec.family == AssetFamily.PROP and spec.recipe in ("crate", "sci_fi_crate"):
        return _solve_crate_spec(spec)
    elif spec.family == AssetFamily.PROP and spec.recipe in ("barrel", "fuel_barrel"):
        return _solve_barrel_spec(spec)
    else:
        return _solve_generic_box_spec(spec)


def _solve_vehicle_spec(spec: AssetSpec) -> ResolvedAssetPlan:
    """Mathematically compiles vehicle design intent into coupled parts and sockets."""
    L = spec.dimensions.length
    W = spec.dimensions.width
    H = spec.dimensions.height

    # Parameters with robust defaults
    wheel_r = spec.parameters.get("wheel_radius", min(0.38, H * 0.25))
    wheel_w = spec.parameters.get("wheel_width", min(0.28, W * 0.18))
    wb_ratio = spec.parameters.get("wheelbase_ratio", 0.65)
    tw_ratio = spec.parameters.get("track_width_ratio", 0.85)
    cabin_h_ratio = spec.parameters.get("cabin_height_ratio", 0.42)
    hood_l_ratio = spec.parameters.get("hood_length_ratio", 0.28)
    ground_clearance = spec.parameters.get("ground_clearance", wheel_r * 0.75)
    bevel_w = spec.parameters.get("bevel_width", min(0.035, H * 0.025))

    parts: List[ResolvedPart] = []
    sockets: Dict[str, SocketDefinition] = {}

    # 1. Wheels Calculation (Grounding at Z = 0)
    # Contact with ground means center of wheel is exactly at Z = wheel_r
    half_wb = (L * wb_ratio) / 2.0
    half_tw = (W * tw_ratio) / 2.0

    wheel_configs = [
        ("Wheel_FL", (half_tw, half_wb, wheel_r), "socket_wheel_fl"),
        ("Wheel_FR", (-half_tw, half_wb, wheel_r), "socket_wheel_fr"),
        ("Wheel_RL", (half_tw, -half_wb, wheel_r), "socket_wheel_rl"),
        ("Wheel_RR", (-half_tw, -half_wb, wheel_r), "socket_wheel_rr"),
    ]

    for w_name, loc, sock_name in wheel_configs:
        sockets[sock_name] = SocketDefinition(
            name=sock_name,
            location=loc,
            rotation=(0.0, 90.0, 0.0),  # Oriented along X-axis
            normal=(1.0 if loc[0] > 0 else -1.0, 0.0, 0.0),
            category="wheel",
        )
        parts.append(ResolvedPart(
            name=w_name,
            primitive="CYLINDER",
            location=loc,
            dimensions=(wheel_r * 2, wheel_w, wheel_r * 2),
            rotation=(0.0, 90.0, 0.0),
            material_slot="tires",
            bevel_width=bevel_w * 0.5,
            socket_name=sock_name,
        ))

    # 2. Main Chassis & Lower Body
    # Starts above ground clearance, reaches up to cabin base
    chassis_z_start = ground_clearance
    cabin_h = H * cabin_h_ratio
    chassis_h = max(0.25, H - cabin_h - ground_clearance)
    chassis_center_z = chassis_z_start + (chassis_h / 2.0)
    chassis_w = W * 0.92
    chassis_l = L * 0.96

    parts.append(ResolvedPart(
        name="Chassis_Main",
        primitive="CUBE",
        location=(0.0, 0.0, chassis_center_z),
        dimensions=(chassis_w, chassis_l, chassis_h),
        material_slot="body",
        bevel_width=bevel_w,
    ))

    # 3. Cabin (Upper Body)
    cabin_w = W * 0.82
    cabin_l = L * (1.0 - hood_l_ratio - 0.15)
    # Offset cabin backward to leave room for the hood/engine bay in front (+Y)
    cabin_offset_y = - (L * 0.5) + (cabin_l * 0.5) + 0.1
    cabin_center_z = chassis_z_start + chassis_h + (cabin_h / 2.0)

    parts.append(ResolvedPart(
        name="Cabin_Upper",
        primitive="CUBE",
        location=(0.0, cabin_offset_y, cabin_center_z),
        dimensions=(cabin_w, cabin_l, cabin_h),
        material_slot="body",
        bevel_width=bevel_w,
        parent_part="Chassis_Main",
    ))

    # Cabin roof socket
    sockets["socket_roof"] = SocketDefinition(
        name="socket_roof",
        location=(0.0, cabin_offset_y, cabin_center_z + (cabin_h / 2.0)),
        normal=(0.0, 0.0, 1.0),
        category="roof_mount",
    )

    # 4. Windshield & Glass (Features)
    if spec.features.get("windshield", True):
        glass_h = cabin_h * 0.6
        glass_w = cabin_w * 0.85
        glass_front_y = cabin_offset_y + (cabin_l / 2.0) + 0.01
        parts.append(ResolvedPart(
            name="Windshield_Front",
            primitive="CUBE",
            location=(0.0, glass_front_y, cabin_center_z + 0.05),
            dimensions=(glass_w, 0.05, glass_h),
            material_slot="windows",
            parent_part="Cabin_Upper",
        ))

    # 5. Bumpers & Lights Sockets
    front_bumper_y = (chassis_l * 0.5)
    rear_bumper_y = -(chassis_l * 0.5)
    bumper_z = ground_clearance + (chassis_h * 0.4)

    sockets["socket_bumper_front"] = SocketDefinition(
        name="socket_bumper_front",
        location=(0.0, front_bumper_y, bumper_z),
        normal=(0.0, 1.0, 0.0),
        category="bumper",
    )
    sockets["socket_bumper_rear"] = SocketDefinition(
        name="socket_bumper_rear",
        location=(0.0, rear_bumper_y, bumper_z),
        normal=(0.0, -1.0, 0.0),
        category="bumper",
    )

    if spec.features.get("bumpers", True):
        parts.append(ResolvedPart(
            name="Bumper_Front",
            primitive="CUBE",
            location=(0.0, front_bumper_y, bumper_z),
            dimensions=(W * 0.98, 0.12, chassis_h * 0.45),
            material_slot="trim",
            bevel_width=bevel_w * 0.5,
            socket_name="socket_bumper_front",
        ))
        parts.append(ResolvedPart(
            name="Bumper_Rear",
            primitive="CUBE",
            location=(0.0, rear_bumper_y, bumper_z),
            dimensions=(W * 0.98, 0.12, chassis_h * 0.45),
            material_slot="trim",
            bevel_width=bevel_w * 0.5,
            socket_name="socket_bumper_rear",
        ))

    # 6. Headlights
    hl_offset_x = W * 0.32
    sockets["socket_headlight_l"] = SocketDefinition(
        name="socket_headlight_l",
        location=(hl_offset_x, front_bumper_y - 0.02, bumper_z + 0.15),
        normal=(0.0, 1.0, 0.0),
        category="light",
    )
    sockets["socket_headlight_r"] = SocketDefinition(
        name="socket_headlight_r",
        location=(-hl_offset_x, front_bumper_y - 0.02, bumper_z + 0.15),
        normal=(0.0, 1.0, 0.0),
        category="light",
    )

    if spec.features.get("headlights", True):
        for hl_name, sock_name in [("Headlight_L", "socket_headlight_l"), ("Headlight_R", "socket_headlight_r")]:
            sock = sockets[sock_name]
            parts.append(ResolvedPart(
                name=hl_name,
                primitive="CYLINDER",
                location=sock.location,
                dimensions=(0.14, 0.05, 0.14),
                rotation=(90.0, 0.0, 0.0),
                material_slot="lights",
                socket_name=sock_name,
            ))

    # 7. Roof Rack (Optional Feature)
    if spec.features.get("roof_rack", False):
        sock = sockets["socket_roof"]
        parts.append(ResolvedPart(
            name="Roof_Rack",
            primitive="CUBE",
            location=(sock.location[0], sock.location[1], sock.location[2] + 0.05),
            dimensions=(cabin_w * 0.9, cabin_l * 0.8, 0.12),
            material_slot="trim",
            bevel_width=bevel_w * 0.5,
            parent_part="Cabin_Upper",
            socket_name="socket_roof",
        ))

    return ResolvedAssetPlan(
        asset_id=spec.asset_id,
        parts=parts,
        sockets=sockets,
        materials=spec.materials or {
            "body": "olive_paint",
            "tires": "dark_rubber",
            "windows": "dark_glass",
            "trim": "brushed_metal",
            "lights": "headlight_emissive",
        },
        export=spec.export,
    )


def _solve_crate_spec(spec: AssetSpec) -> ResolvedAssetPlan:
    """Solves modular supply crate / sci-fi container geometry."""
    L = spec.dimensions.length
    W = spec.dimensions.width
    H = spec.dimensions.height
    bevel_w = spec.parameters.get("bevel_width", min(0.025, min(L, W, H) * 0.04))
    wall_t = spec.parameters.get("wall_thickness", 0.04)

    parts: List[ResolvedPart] = []
    sockets: Dict[str, SocketDefinition] = {}

    # Main box resting on ground Z=0
    parts.append(ResolvedPart(
        name="Crate_Body",
        primitive="CUBE",
        location=(0.0, 0.0, H / 2.0),
        dimensions=(W, L, H),
        material_slot="body",
        bevel_width=bevel_w,
    ))

    # Lid Socket at top
    sockets["socket_lid"] = SocketDefinition(
        name="socket_lid",
        location=(0.0, 0.0, H),
        normal=(0.0, 0.0, 1.0),
        category="lid",
    )

    # 4 Corner reinforcements
    corner_w = wall_t * 1.5
    half_x = (W - corner_w) / 2.0
    half_y = (L - corner_w) / 2.0

    corner_locs = [
        ("Corner_FL", (half_x, half_y, H / 2.0)),
        ("Corner_FR", (-half_x, half_y, H / 2.0)),
        ("Corner_BL", (half_x, -half_y, H / 2.0)),
        ("Corner_BR", (-half_x, -half_y, H / 2.0)),
    ]
    for c_name, c_loc in corner_locs:
        parts.append(ResolvedPart(
            name=c_name,
            primitive="CUBE",
            location=c_loc,
            dimensions=(corner_w, corner_w, H * 1.01),
            material_slot="trim",
            bevel_width=bevel_w * 0.5,
        ))

    return ResolvedAssetPlan(
        asset_id=spec.asset_id,
        parts=parts,
        sockets=sockets,
        materials=spec.materials or {"body": "wood_or_metal", "trim": "steel_edge"},
        export=spec.export,
    )


def _solve_barrel_spec(spec: AssetSpec) -> ResolvedAssetPlan:
    """Solves radial container / barrel geometry."""
    diameter = max(spec.dimensions.width, spec.dimensions.length)
    H = spec.dimensions.height
    radius = diameter / 2.0
    bevel_w = spec.parameters.get("bevel_width", 0.02)

    parts: List[ResolvedPart] = []
    sockets: Dict[str, SocketDefinition] = {}

    # Main cylinder resting on Z=0
    parts.append(ResolvedPart(
        name="Barrel_Body",
        primitive="CYLINDER",
        location=(0.0, 0.0, H / 2.0),
        dimensions=(diameter, diameter, H),
        material_slot="body",
        bevel_width=bevel_w,
    ))

    # Top socket
    sockets["socket_cap"] = SocketDefinition(
        name="socket_cap",
        location=(0.0, 0.0, H),
        normal=(0.0, 0.0, 1.0),
        category="plug",
    )

    # Metal hoops/bands (2 bands)
    band_h = H * 0.06
    band_locs = [
        ("Hoop_Upper", (0.0, 0.0, H * 0.75)),
        ("Hoop_Lower", (0.0, 0.0, H * 0.25)),
    ]
    for b_name, b_loc in band_locs:
        parts.append(ResolvedPart(
            name=b_name,
            primitive="CYLINDER",
            location=b_loc,
            dimensions=(diameter * 1.03, diameter * 1.03, band_h),
            material_slot="trim",
        ))

    return ResolvedAssetPlan(
        asset_id=spec.asset_id,
        parts=parts,
        sockets=sockets,
        materials=spec.materials or {"body": "barrel_wood", "trim": "metal_band"},
        export=spec.export,
    )


def _solve_generic_box_spec(spec: AssetSpec) -> ResolvedAssetPlan:
    """Fallback solver for generic graybox structures."""
    L = spec.dimensions.length
    W = spec.dimensions.width
    H = spec.dimensions.height
    bevel_w = spec.parameters.get("bevel_width", 0.02)

    parts = [
        ResolvedPart(
            name=f"{spec.asset_id}_Body",
            primitive="CUBE",
            location=(0.0, 0.0, H / 2.0),
            dimensions=(W, L, H),
            material_slot="body",
            bevel_width=bevel_w,
        )
    ]
    sockets = {
        "socket_top": SocketDefinition(
            name="socket_top",
            location=(0.0, 0.0, H),
            normal=(0.0, 0.0, 1.0),
        )
    }
    return ResolvedAssetPlan(
        asset_id=spec.asset_id,
        parts=parts,
        sockets=sockets,
        materials=spec.materials or {"body": "default_material"},
        export=spec.export,
    )
