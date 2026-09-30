"""Unit tests for tool packs (pure Python)."""

import unittest

from core.tool_packs import ABOUT, IMPLIES, PACKS, filter_tools, pack_of, packs_for_text, valid_packs


class Tool:
    def __init__(self, name):
        self.name = name


class TestToolPacks(unittest.TestCase):
    def test_packs_are_disjoint_and_described(self):
        seen = set()
        for pack, names in PACKS.items():
            self.assertFalse(seen & set(names), pack)
            seen |= set(names)
            self.assertIn(pack, ABOUT)
        self.assertTrue(set(IMPLIES) <= set(PACKS))

    def test_pack_of(self):
        self.assertEqual(pack_of("camera_move"), "film")
        self.assertEqual(pack_of("rig_character"), "characters")
        self.assertEqual(pack_of("create_primitive"), "")

    def test_requests_pick_their_packs_in_both_languages(self):
        self.assertEqual(packs_for_text("bir sandık modelle"), set())
        self.assertEqual(packs_for_text("Make a low poly crate and export it"), set())
        self.assertIn("film", packs_for_text("gün batımında 5 saniyelik bir MP4 çek"))
        self.assertIn("film", packs_for_text("orbit around the castle and render a video"))
        self.assertIn("textures", packs_for_text("unwrap the crate and bake the wood for Godot"))
        self.assertIn("textures", packs_for_text("bu sandığı Godot'ya götüreceğim, doku pişir"))
        self.assertNotIn("textures", packs_for_text("evin duvarını kırmızı yap"))
        self.assertEqual(pack_of("bake_material"), "textures")
        self.assertEqual(packs_for_text("bir asker modelle ve yürüt"), {"characters", "film"})
        self.assertEqual(packs_for_text("make a zombie walk"), {"characters", "film"})

    def test_filter_keeps_the_core_and_only_active_packs(self):
        tools = [Tool(n) for n in ("create_primitive", "camera_move", "rig_character", "export_gltf", "render_image")]
        self.assertEqual([t.name for t in filter_tools(tools, [])], ["create_primitive", "export_gltf"])
        self.assertEqual([t.name for t in filter_tools(tools, ["film"])],
                         ["create_primitive", "camera_move", "export_gltf", "render_image"])
        self.assertEqual(len(filter_tools(tools, ["film", "characters"])), 5)

    def test_valid_packs_drops_unknown_names(self):
        self.assertEqual(valid_packs(["film", "nope", "characters"]), ["film", "characters"])

    def test_every_pack_tool_exists_in_the_real_toolset(self):
        import inspect

        import tools.mutations as mutations
        from tools.base import BaseTool

        real = set()
        for n in dir(mutations):
            c = getattr(mutations, n)
            if inspect.isclass(c) and issubclass(c, BaseTool) and c is not BaseTool:
                real.add(c().name)
        for pack, names in PACKS.items():
            self.assertTrue(set(names) <= real, (pack, set(names) - real))


if __name__ == "__main__":
    unittest.main()
