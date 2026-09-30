import unittest

from core.model_qa import DEFAULT_TRIANGLE_BUDGET, group_issues, object_issues, verdict


def clean(name="Box", **over):
    stats = {"name": name, "tris": 12, "faces": 6, "nonmanifold_edges": 0, "closed": True, "signed_volume": 1.0,
             "degenerate_faces": 0, "duplicate_verts": 0, "loose_verts": 0, "scale": (1.0, 1.0, 1.0),
             "origin_outside": False, "has_material": True, "uses_image_texture": False, "uv_layers": 1,
             "z_min": 0.0, "z_max": 1.0, "bbox_min": (0, 0, 0), "bbox_max": (1, 1, 1)}
    stats.update(over)
    return stats


def codes(issues):
    return {i["code"] for i in issues}


class ModelQaTests(unittest.TestCase):
    def test_clean_model_is_clean(self):
        v = verdict([clean()])
        self.assertTrue(v["ok"] and v["clean"], v)
        self.assertEqual(v["issues"], [])

    def test_each_object_problem_is_found_with_a_fix(self):
        bad = clean(nonmanifold_edges=4, signed_volume=-2.0, degenerate_faces=1, duplicate_verts=3, loose_verts=2,
                    scale=(2.0, 1.0, 1.0), origin_outside=True, has_material=False, uses_image_texture=True, uv_layers=0,
                    z_min=-3.0, z_max=-2.0)
        found = object_issues(bad)
        self.assertEqual(codes(found), {"NON_MANIFOLD", "INVERTED_NORMALS", "DEGENERATE_FACES", "DUPLICATE_VERTICES",
                                        "LOOSE_VERTICES", "UNAPPLIED_SCALE", "ORIGIN_OUTSIDE", "NO_MATERIAL", "MISSING_UV",
                                        "BELOW_GROUND"})
        self.assertTrue(all(i["fix"] and i["objects"] == ["Box"] for i in found))

    def test_open_mesh_does_not_flip_normals_and_negative_scale_counts(self):
        self.assertNotIn("INVERTED_NORMALS", codes(object_issues(clean(closed=False, signed_volume=-1.0))))
        self.assertIn("UNAPPLIED_SCALE", codes(object_issues(clean(scale=(-1.0, 1.0, 1.0)))))

    def test_triangle_budget_warns_then_fails(self):
        self.assertEqual(group_issues([clean(tris=DEFAULT_TRIANGLE_BUDGET)]), [])
        warn = group_issues([clean(tris=DEFAULT_TRIANGLE_BUDGET + 1)])
        self.assertEqual((warn[0]["code"], warn[0]["severity"]), ("TOO_MANY_TRIANGLES", "WARN"))
        fail = group_issues([clean(tris=DEFAULT_TRIANGLE_BUDGET * 3 + 1)])
        self.assertEqual(fail[0]["severity"], "FAIL")
        self.assertEqual(group_issues([clean(tris=500)], max_triangles=400)[0]["severity"], "WARN")

    def test_sinking_and_duplicates(self):
        parts = [clean("A", z_min=-0.5, z_max=1.0), clean("B", z_min=0.0, z_max=1.0)]
        self.assertIn("SINKS_INTO_GROUND", codes(group_issues(parts)))
        twins = group_issues([clean("A"), clean("B")])
        self.assertEqual([i["code"] for i in twins], ["DUPLICATE_OBJECT"])
        moved = group_issues([clean("A"), clean("B", bbox_min=(0.5, 0, 0), bbox_max=(1.5, 1, 1))])
        self.assertNotIn("DUPLICATE_OBJECT", codes(moved))

    def test_verdict_merges_and_ranks_failures_first(self):
        stats = [clean("A", duplicate_verts=5), clean("B", duplicate_verts=2), clean("C", nonmanifold_edges=1)]
        v = verdict(stats)
        self.assertFalse(v["ok"])
        self.assertEqual(v["issues"][0]["code"], "NON_MANIFOLD")
        dup = [i for i in v["issues"] if i["code"] == "DUPLICATE_VERTICES"][0]
        self.assertEqual(dup["objects"], ["A", "B"])
        self.assertEqual(dup["count"], 2)
        self.assertEqual(v["objects_checked"], 3)

    def test_warnings_alone_keep_ok_true(self):
        v = verdict([clean(has_material=False)])
        self.assertTrue(v["ok"])
        self.assertFalse(v["clean"])


if __name__ == "__main__":
    unittest.main()
