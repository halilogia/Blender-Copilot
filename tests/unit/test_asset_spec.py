"""Unit tests for core/asset_spec.py — Semantic AssetSpec & Constraint Solver.

Pure Python, zero Blender dependency.
"""

import unittest
from core.asset_spec import (
    AssetDimensions,
    AssetFamily,
    AssetSpec,
    CollisionType,
    ExportSpec,
    PivotPlacement,
    SpecValidationError,
    solve_asset_constraints,
    validate_asset_spec,
)


class TestAssetSpec(unittest.TestCase):
    """Test AssetSpec models, serialization, and schema validation."""

    def test_serialization_round_trip(self):
        spec = AssetSpec(
            asset_id="test_scout",
            family=AssetFamily.VEHICLE,
            recipe="offroad_vehicle",
            dimensions=AssetDimensions(length=4.2, width=1.9, height=1.6),
            parameters={"wheelbase_ratio": 0.65, "bevel_width": 0.03},
            features={"roof_rack": True, "bumpers": True},
            materials={"body": "olive_drab"},
            export=ExportSpec(triangle_budget=4500, collision=CollisionType.COMPOUND_CONVEX),
        )

        data = spec.to_dict()
        self.assertEqual(data["asset_id"], "test_scout")
        self.assertEqual(data["family"], "vehicle")
        self.assertEqual(data["dimensions"]["length"], 4.2)
        self.assertTrue(data["features"]["roof_rack"])

        restored = AssetSpec.from_dict(data)
        self.assertEqual(restored.asset_id, spec.asset_id)
        self.assertEqual(restored.family, AssetFamily.VEHICLE)
        self.assertEqual(restored.dimensions.width, 1.9)
        self.assertEqual(restored.export.triangle_budget, 4500)

    def test_validation_rejects_negative_dimensions(self):
        spec = AssetSpec(
            asset_id="bad_dims",
            family=AssetFamily.PROP,
            recipe="crate",
            dimensions=AssetDimensions(length=-1.0, width=1.0, height=1.0),
        )
        errors = validate_asset_spec(spec)
        self.assertTrue(any("length must be positive" in e for e in errors))

    def test_validation_rejects_excessive_bevel(self):
        # Bevel 0.5m on a 0.2m box will collapse geometry
        spec = AssetSpec(
            asset_id="bad_bevel",
            family=AssetFamily.PROP,
            recipe="crate",
            dimensions=AssetDimensions(length=1.0, width=1.0, height=0.2),
            parameters={"bevel_width": 0.15},
        )
        errors = validate_asset_spec(spec)
        self.assertTrue(any("bevel_width" in e and "exceeds" in e for e in errors))

    def test_validation_rejects_invalid_wheelbase_ratio(self):
        spec = AssetSpec(
            asset_id="bad_wb",
            family=AssetFamily.VEHICLE,
            recipe="offroad_vehicle",
            dimensions=AssetDimensions(length=4.0, width=1.8, height=1.5),
            parameters={"wheelbase_ratio": 0.98},  # Wheels beyond vehicle bumper!
        )
        errors = validate_asset_spec(spec)
        self.assertTrue(any("wheelbase_ratio" in e for e in errors))


class TestConstraintSolver(unittest.TestCase):
    """Test mathematical coupling of geometry and socket placement."""

    def test_vehicle_wheels_touch_ground_and_symmetry(self):
        spec = AssetSpec(
            asset_id="scout_vehicle",
            family=AssetFamily.VEHICLE,
            recipe="offroad_vehicle",
            dimensions=AssetDimensions(length=4.0, width=2.0, height=1.6),
            parameters={
                "wheel_radius": 0.40,
                "wheel_width": 0.25,
                "wheelbase_ratio": 0.60,
                "track_width_ratio": 0.80,
            },
            features={"roof_rack": True, "headlights": True, "bumpers": True},
        )

        plan = solve_asset_constraints(spec)
        self.assertEqual(plan.asset_id, "scout_vehicle")

        # 1. Wheels touch Z=0: center Z must be exactly wheel_radius (0.40)
        wheel_parts = [p for p in plan.parts if p.name.startswith("Wheel_")]
        self.assertEqual(len(wheel_parts), 4)
        for w in wheel_parts:
            self.assertAlmostEqual(w.location[2], 0.40, places=4)

        # 2. Track width symmetry: FL (X > 0) vs FR (X < 0)
        w_fl = next(p for p in wheel_parts if p.name == "Wheel_FL")
        w_fr = next(p for p in wheel_parts if p.name == "Wheel_FR")
        expected_half_tw = (2.0 * 0.80) / 2.0  # 0.80m
        self.assertAlmostEqual(w_fl.location[0], expected_half_tw, places=4)
        self.assertAlmostEqual(w_fr.location[0], -expected_half_tw, places=4)

        # 3. Wheelbase symmetry: FL (Y > 0) vs RL (Y < 0)
        w_rl = next(p for p in wheel_parts if p.name == "Wheel_RL")
        expected_half_wb = (4.0 * 0.60) / 2.0  # 1.20m
        self.assertAlmostEqual(w_fl.location[1], expected_half_wb, places=4)
        self.assertAlmostEqual(w_rl.location[1], -expected_half_wb, places=4)

        # 4. Sockets verified
        self.assertIn("socket_wheel_fl", plan.sockets)
        self.assertIn("socket_bumper_front", plan.sockets)
        self.assertIn("socket_roof", plan.sockets)
        self.assertIn("socket_headlight_l", plan.sockets)

        # 5. Roof rack attached to roof socket
        roof_part = next(p for p in plan.parts if p.name == "Roof_Rack")
        self.assertEqual(roof_part.socket_name, "socket_roof")

    def test_crate_solver_and_lid_socket(self):
        spec = AssetSpec(
            asset_id="wood_crate",
            family=AssetFamily.PROP,
            recipe="crate",
            dimensions=AssetDimensions(length=1.2, width=0.8, height=0.9),
            parameters={"bevel_width": 0.02},
        )
        plan = solve_asset_constraints(spec)
        self.assertIn("socket_lid", plan.sockets)
        self.assertAlmostEqual(plan.sockets["socket_lid"].location[2], 0.9, places=4)
        body = next(p for p in plan.parts if p.name == "Crate_Body")
        self.assertAlmostEqual(body.location[2], 0.45, places=4)

    def test_barrel_solver_bands(self):
        spec = AssetSpec(
            asset_id="metal_barrel",
            family=AssetFamily.PROP,
            recipe="barrel",
            dimensions=AssetDimensions(length=0.6, width=0.6, height=1.0),
        )
        plan = solve_asset_constraints(spec)
        self.assertIn("socket_cap", plan.sockets)
        hoops = [p for p in plan.parts if "Hoop" in p.name]
        self.assertEqual(len(hoops), 2)


if __name__ == "__main__":
    unittest.main()
