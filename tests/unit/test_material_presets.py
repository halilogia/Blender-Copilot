import unittest

from core.material_presets import PRESETS, preset_names, recipe


class MaterialPresetTests(unittest.TestCase):
    def test_every_preset_is_well_formed(self):
        for name in preset_names():
            rec = recipe(name)
            self.assertIn(rec["texture"], ("noise", "wave", "brick"), name)
            self.assertGreaterEqual(len(rec["ramp"]), 2, name)
            last = -1.0
            for pos, rgb in rec["ramp"]:
                self.assertTrue(0.0 <= pos <= 1.0 and pos > last, name)
                last = pos
                self.assertEqual(len(rgb), 3)
                self.assertTrue(all(0.0 <= c <= 1.0 for c in rgb), name)
            self.assertTrue(0.0 <= rec["roughness"] <= 1.0 and 0.0 <= rec["metallic"] <= 1.0, name)
        self.assertGreaterEqual(len(PRESETS), 8)

    def test_scale_and_name_handling(self):
        self.assertEqual(recipe("Wood ", 2.0)["scale"], tuple(v * 2 for v in PRESETS["wood"]["scale"]))
        self.assertEqual(recipe("wood", None)["scale"], PRESETS["wood"]["scale"])
        self.assertEqual(recipe("wood")["name"], "wood")

    def test_errors_name_the_options(self):
        with self.assertRaises(ValueError) as ctx:
            recipe("velvet")
        self.assertIn("wood", str(ctx.exception))
        for bad in ("x", 0, 500):
            with self.assertRaises(ValueError):
                recipe("wood", bad)


if __name__ == "__main__":
    unittest.main()
