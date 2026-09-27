"""Unit tests for check-only auto-update (v1.1 B). Pure Python."""

import unittest

from core.update_check import UpdateStatus, check_for_updates, is_newer, parse_version


class TestUpdateCheck(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("release 2.0.10"), (2, 0, 10))
        with self.assertRaises(ValueError):
            parse_version("no-version")

    def test_is_newer(self):
        self.assertTrue(is_newer("1.0.0", "1.1.0"))
        self.assertFalse(is_newer("1.1.0", "1.1.0"))
        self.assertFalse(is_newer("2.0.0", "1.9.9"))

    def test_available(self):
        st = check_for_updates("1.0.0", fetcher=lambda url: {"tag_name": "v1.1.0", "body": "notes"})
        self.assertTrue(st.update_available)
        self.assertEqual(st.latest, "1.1.0")

    def test_up_to_date(self):
        st = check_for_updates("1.1.0", fetcher=lambda url: {"tag_name": "v1.1.0"})
        self.assertFalse(st.update_available)

    def test_error_folds(self):
        def boom(url):
            raise OSError("offline")
        st = check_for_updates("1.0.0", fetcher=boom)
        self.assertFalse(st.update_available)
        self.assertIsNotNone(st.error)

    def test_malformed_tag(self):
        st = check_for_updates("1.0.0", fetcher=lambda url: {"tag_name": "??? "})
        self.assertFalse(st.update_available)
        self.assertIsNotNone(st.error)


if __name__ == "__main__":
    unittest.main()
