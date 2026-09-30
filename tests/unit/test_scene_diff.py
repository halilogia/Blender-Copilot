import unittest

from core.scene_diff import MAX_LINES, diff, headline


def obj(**over):
    base = {"type": "MESH", "location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0], "parent": None,
            "hidden": False, "materials": ["M"], "modifiers": [], "collections": ["Collection"], "data": {"vertices": 8, "faces": 6}}
    base.update(over)
    return base


def snap(objects, materials=("M",), collections=("Collection",), scene=None):
    return {"objects": objects, "materials": list(materials), "collections": list(collections), "scene": scene or {"camera": None}}


class SceneDiffTests(unittest.TestCase):
    def test_identical_snapshots_are_empty(self):
        a = snap({"Cube": obj()})
        d = diff(a, snap({"Cube": obj()}))
        self.assertTrue(d["empty"])
        self.assertEqual((d["summary"], headline(d)), ([], "no changes"))

    def test_added_removed_and_changed(self):
        before = snap({"Table": obj(), "Old": obj()})
        after = snap({"Table": obj(location=[1.0, 0.0, 0.0], materials=["Wood"], modifiers=["Bevel"]), "Chair": obj()},
                     materials=("M", "Wood"))
        d = diff(before, after)
        self.assertEqual([i["name"] for i in d["added"]], ["Chair"])
        self.assertEqual([i["name"] for i in d["removed"]], ["Old"])
        fields = d["changed"][0]["fields"]
        self.assertEqual(set(fields), {"location", "materials", "modifiers"})
        self.assertEqual(d["materials_added"], ["Wood"])
        text = "\n".join(d["summary"])
        self.assertIn("+ Chair (MESH)", text)
        self.assertIn("- Old (MESH)", text)
        self.assertIn("~ Table: location [0, 0, 0] -> [1, 0, 0]", text)
        self.assertIn("+ material Wood", text)
        self.assertEqual(headline(d), "1 added, 1 removed, 1 changed, 1 new materials")

    def test_tiny_float_noise_is_not_a_change(self):
        d = diff(snap({"A": obj()}), snap({"A": obj(location=[0.00001, 0.0, 0.0], scale=[1.00002, 1.0, 1.0])}))
        self.assertTrue(d["empty"])

    def test_mesh_size_parent_and_visibility(self):
        d = diff(snap({"A": obj()}), snap({"A": obj(data={"vertices": 16, "faces": 12}, parent="B", hidden=True)}))
        self.assertEqual(set(d["changed"][0]["fields"]), {"data", "parent", "hidden"})

    def test_scene_and_collections(self):
        d = diff(snap({}, scene={"camera": None, "fps": 24}), snap({}, collections=("Collection", "Forest"), scene={"camera": "Cam", "fps": 24}))
        self.assertEqual(d["collections_added"], ["Forest"])
        self.assertEqual(list(d["scene"]), ["camera"])
        self.assertFalse(d["empty"])
        self.assertEqual(headline(d), "scene settings changed")

    def test_long_reports_are_cut(self):
        after = snap({f"T{i}": obj() for i in range(MAX_LINES + 15)})
        d = diff(snap({}), after)
        self.assertEqual(len(d["summary"]), MAX_LINES + 1)
        self.assertTrue(d["summary"][-1].endswith("15 more"))
        self.assertEqual(d["counts"]["objects_added"], MAX_LINES + 15)


if __name__ == "__main__":
    unittest.main()
