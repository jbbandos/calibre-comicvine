"""Tests for ``utils.build_term`` (Requirement 3.4)."""
import unittest

from calibre_plugins.comicvine import utils


class BuildTermTests(unittest.TestCase):
    def test_single_part(self):
        self.assertEqual(utils.build_term("title", ["saga"]), "saga")
        self.assertEqual(utils.build_term("author", ["vaughan"]), "vaughan")

    def test_multi_part_joined_with_spaces(self):
        self.assertEqual(
            utils.build_term("author", ["brian", "k.", "vaughan"]),
            "brian k. vaughan",
        )
        self.assertEqual(utils.build_term("title", ["a", "b", "c"]), "a b c")

    def test_empty_parts_list(self):
        self.assertEqual(utils.build_term("author", []), "")
        self.assertEqual(utils.build_term("title", []), "")

    def test_empty_string_part(self):
        self.assertEqual(utils.build_term("title", [""]), "")
        self.assertEqual(utils.build_term("title", ["a", "", "b"]), "a  b")

    def test_accepts_any_iterable(self):
        self.assertEqual(utils.build_term("author", iter(["x", "y"])), "x y")

    def test_unknown_build_type_behaves_like_default(self):
        self.assertEqual(
            utils.build_term("other", ["x", "y"]),
            utils.build_term("author", ["x", "y"]),
        )


if __name__ == "__main__":
    unittest.main()
