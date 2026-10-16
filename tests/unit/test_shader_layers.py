import unittest

from core.shader_layers import AXES, axis_vector, even_stops, normalize_layers
from tools.mutations.set_material import SetMaterialTool


class ShaderLayerTests(unittest.TestCase):
    def test_nothing_given_is_empty(self):
        self.assertEqual(normalize_layers(), {})
        self.assertEqual(normalize_layers(coat=None, rim_colors=None), {})

    def test_valid_layers_and_defaults(self):
        out = normalize_layers(subsurface=0.2, coat=1, coat_roughness=0.05, thin_film=400,
                               gradient_colors=[[0, 0, 1], [1, 0, 1, 1]], rim_colors=[[0, 1, 1], [0, 0, 1]])
        self.assertEqual(out["coat"], 1.0)
        self.assertEqual(out["thin_film"], 400.0)
        self.assertEqual(out["gradient_axis"], "z")
        self.assertEqual(out["gradient_colors"][1], (1.0, 0.0, 1.0))   # alpha dropped
        self.assertEqual(out["rim_strength"], 2.0)
        self.assertEqual(normalize_layers(gradient_colors=[[0, 0, 0], [1, 1, 1]], gradient_axis="Diagonal")["gradient_axis"], "diagonal")

    def test_errors_state_the_range(self):
        bad = [dict(coat=1.5), dict(subsurface="x"), dict(thin_film=5000), dict(gradient_colors=[[0, 0, 0]]),
               dict(gradient_colors=[[0, 0, 0]] * 5), dict(gradient_colors=[[0, 0], [1, 1]]),
               dict(gradient_colors=[[0, 0, 0], [2, 0, 0]]), dict(gradient_axis="z"),
               dict(gradient_colors=[[0, 0, 0], [1, 1, 1]], gradient_axis="w"), dict(rim_strength=1.0),
               dict(rim_colors=[[0, 0, 0], [1, 1, 1]], rim_strength=99)]
        for kwargs in bad:
            with self.assertRaises(ValueError, msg=kwargs):
                normalize_layers(**kwargs)

    def test_stops_and_axes(self):
        stops = even_stops([(0, 0, 0), (0.5, 0.5, 0.5), (1, 1, 1)], 0.35, 1.0)
        self.assertEqual([round(p, 3) for p, _ in stops], [0.35, 0.675, 1.0])
        for name in AXES:
            vec = axis_vector(name)
            self.assertAlmostEqual(sum(v * v for v in vec) ** 0.5, 1.0, places=2)

    def test_tool_schema_lists_the_layers(self):
        props = SetMaterialTool().input_schema["properties"]
        for key in ("subsurface", "coat", "coat_roughness", "thin_film", "gradient_colors", "gradient_axis",
                    "rim_colors", "rim_strength"):
            self.assertIn(key, props)


if __name__ == "__main__":
    unittest.main()
