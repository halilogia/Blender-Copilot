"""Unit tests for stdlib local embedding (v1.1 A3). Pure Python."""

import math
import unittest

from agent.local_embed import (
    LocalIndex,
    cosine_sim,
    embed_text,
    featurize,
    tokenize,
    top_k,
)


class TestLocalEmbed(unittest.TestCase):
    def test_tokenize_turkish(self):
        toks = tokenize("Küp Sahne 123!")
        self.assertIn("küp", toks)
        self.assertIn("sahne", toks)
        self.assertIn("123", toks)

    def test_embed_deterministic_and_normalized(self):
        a = embed_text("küp sahne")
        b = embed_text("küp sahne")
        self.assertEqual(a, b)
        norm = math.sqrt(sum(v * v for v in a))
        self.assertAlmostEqual(norm, 1.0, places=6)

    def test_embed_empty_zero_vector(self):
        v = embed_text("")
        self.assertTrue(all(x == 0.0 for x in v))
        self.assertEqual(cosine_sim(v, v), 0.0)

    def test_cosine_self_similarity(self):
        v = embed_text("camera light")
        self.assertAlmostEqual(cosine_sim(v, v), 1.0, places=6)

    def test_top_k_ranking(self):
        docs = ["kırmızı küp", "mavi küre", "kırmızı küp büyük"]
        ranked = top_k("kırmızı küp", docs, k=2)
        self.assertEqual(ranked[0][0], 0)
        self.assertGreaterEqual(ranked[0][1], ranked[1][1])

    def test_top_k_invalid_k(self):
        with self.assertRaises(ValueError):
            top_k("q", ["a"], k=0)

    def test_cosine_length_mismatch(self):
        with self.assertRaises(ValueError):
            cosine_sim((1.0,), (1.0, 2.0))

    def test_local_index_query(self):
        idx = LocalIndex()
        idx.add("a", "tahta sandalye")
        idx.add("b", "metal küp")
        res = idx.query("metal küp", k=1)
        self.assertEqual(res[0][0], "b")
        idx.remove("b")
        res2 = idx.query("metal küp", k=2)
        self.assertTrue(all(d != "b" for d, _ in res2))

    def test_local_index_invalid(self):
        idx = LocalIndex()
        with self.assertRaises(ValueError):
            idx.add("  ", "x")
        with self.assertRaises(ValueError):
            idx.query("q", k=0)

    def test_featurize_includes_trigrams(self):
        feats = featurize("kup")
        self.assertTrue(any(f.startswith("g:") for f in feats))
        self.assertIn("t:kup", feats)

    def test_serialization_roundtrip(self):
        idx = LocalIndex()
        idx.add("cube", "küp obje")
        d = idx.to_dict()
        idx2 = LocalIndex.from_dict(d)
        self.assertEqual(idx2.query("küp", k=1)[0][0], "cube")


if __name__ == "__main__":
    unittest.main()
