"""Tests for ``Comicvine.cli_main`` (Requirement 5).

Argument parsing is checked by replacing ``identify`` with a recording mock;
output is checked end to end against Mock_Comicvine data.  Known defects of
``cli_main`` (stripping of ``&``-separated authors, dropped extra ``a:``
arguments, repeated ``t:``/``i:``, non-numeric ids) are asserted as
Expected_Failure tests in ``test_defects.py``; the tests here only assert
behavior that holds today.
"""
import contextlib
import io
import unittest
from unittest import mock

from calibre_plugins.comicvine.source import Comicvine

from .fixtures import add_isolation
from .mock_comicvine import MockComicvineMixin


class CliMainBase(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        add_isolation(self, worker_threads=2, max_volumes=5)
        self.source = Comicvine(None)

    def run_cli(self, *args):
        """Run cli_main with ``identify`` replaced; return (kwargs, stdout)."""
        buf = io.StringIO()
        with mock.patch.object(self.source, "identify") as identify:
            with contextlib.redirect_stdout(buf):
                self.source.cli_main(list(args))
        self.assertEqual(identify.call_count, 1)
        call = identify.call_args
        self.assertFalse(call.args[2])  # abort flag
        return call.kwargs, buf.getvalue()

    def run_cli_real(self, *args):
        """Run cli_main end to end against Mock_Comicvine; return stdout."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.source.cli_main(list(args))
        return buf.getvalue()


class CliArgumentParsingTest(CliMainBase):
    def test_readme_title_and_author_example(self):
        kwargs, out = self.run_cli("t:The Invisibles #15", "a:Grant Morrison")
        self.assertEqual(kwargs["title"], "The Invisibles #15")
        self.assertEqual(kwargs["authors"], ["Grant Morrison"])
        self.assertEqual(kwargs["identifiers"], {})
        self.assertEqual(out, "")

    def test_readme_comicvine_id_example(self):
        kwargs, _ = self.run_cli("i:comicvine:41736")
        self.assertIsNone(kwargs["title"])
        self.assertEqual(kwargs["authors"], [])
        self.assertEqual(kwargs["identifiers"], {"comicvine": 41736})
        self.assertIsInstance(kwargs["identifiers"]["comicvine"], int)

    def test_readme_title_and_volume_id_example(self):
        kwargs, _ = self.run_cli("t:Batman #12", "i:comicvine-volume:42721")
        self.assertEqual(kwargs["title"], "Batman #12")
        self.assertEqual(kwargs["identifiers"], {"comicvine-volume": 42721})

    def test_title_keeps_colons_after_the_prefix(self):
        kwargs, _ = self.run_cli("t:Batman: Year One #1")
        self.assertEqual(kwargs["title"], "Batman: Year One #1")

    def test_combined_comicvine_and_volume_ids(self):
        kwargs, _ = self.run_cli("i:comicvine:41736", "i:comicvine-volume:42721")
        self.assertEqual(
            kwargs["identifiers"], {"comicvine": 41736, "comicvine-volume": 42721}
        )

    def test_ampersand_separates_authors_in_one_argument(self):
        kwargs, _ = self.run_cli("a:Brian K. Vaughan & Fiona Staples")
        # Surrounding spaces are not stripped today (see test_defects.py), so
        # compare the stripped names.
        self.assertEqual(
            [name.strip() for name in kwargs["authors"]],
            ["Brian K. Vaughan", "Fiona Staples"],
        )

    def test_multiple_author_arguments_keep_the_first_author(self):
        # Later ``a:`` arguments are dropped today (see test_defects.py); the
        # first one must always be retained.
        kwargs, _ = self.run_cli("a:Grant Morrison", "a:Frank Quitely")
        self.assertEqual(kwargs["authors"][0], "Grant Morrison")

    def test_arguments_are_order_independent(self):
        first, _ = self.run_cli("t:Saga #1", "a:Brian K. Vaughan", "i:comicvine:1")
        self.source = Comicvine(None)
        second, _ = self.run_cli("i:comicvine:1", "a:Brian K. Vaughan", "t:Saga #1")
        self.assertEqual(first, second)

    def test_unknown_prefix_is_silently_ignored(self):
        # Informational (DEFECTS.md): an argument with an unknown prefix is
        # neither used nor reported; no usage message is printed.
        kwargs, out = self.run_cli("x:something", "t:Saga #1")
        self.assertEqual(kwargs["title"], "Saga #1")
        self.assertEqual(kwargs["authors"], [])
        self.assertEqual(kwargs["identifiers"], {})
        self.assertNotIn("usage", out.lower())

    def test_only_unknown_prefix_runs_empty_search_without_usage(self):
        kwargs, out = self.run_cli("bogus")
        self.assertIsNone(kwargs["title"])
        self.assertEqual(kwargs["authors"], [])
        self.assertEqual(kwargs["identifiers"], {})
        self.assertNotIn("usage", out.lower())


class CliOutputTest(CliMainBase):
    def test_plain_output_for_comicvine_id(self):
        out = self.run_cli_real("i:comicvine:300001")
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertRegex(
            lines[0], r"^\(\d{4}\) - 300001: Saga #1: Chapter One \[\d{4}-\d{2}-\d{2}\]$"
        )

    def test_plain_output_for_title_and_author(self):
        out = self.run_cli_real("t:Saga #1", "a:Vaughan")
        self.assertIn("300001: Saga #1: Chapter One", out)
        self.assertNotIn("<package", out)

    def test_plain_output_for_title_and_volume_id(self):
        out = self.run_cli_real("t:Saga #1", "i:comicvine-volume:49104")
        self.assertIn("300001: Saga #1: Chapter One", out)

    def test_no_match_prints_nothing(self):
        self.cv.volumes = []
        self.assertEqual(self.run_cli_real("t:Nothing #1"), "")

    def test_opf_option_prints_opf_for_single_result(self):
        out = self.run_cli_real("-o", "i:comicvine:300001")
        self.assertIn("<package", out)
        self.assertIn("Saga #1: Chapter One", out)
        self.assertIn("300001", out)
        self.assertIn("Brian K. Vaughan", out)
        self.assertNotRegex(out, r"^\(\d{4}\)")

    def test_long_opf_option_prints_opf(self):
        out = self.run_cli_real("--opf", "i:comicvine:300001")
        self.assertIn("<package", out)

    def test_opf_prints_only_the_first_of_several_results(self):
        out = self.run_cli_real("-o", "t:Saga")
        self.assertEqual(out.count("<package"), 1)


if __name__ == "__main__":
    unittest.main()
