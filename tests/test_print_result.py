"""Tests for Comicvine._print_result (Requirement 3.6)."""
import contextlib
import datetime
import io
import unittest

from calibre.ebooks.metadata.book.base import Metadata
from calibre_plugins.comicvine.source import Comicvine


def make_result(pubdate=datetime.datetime(2012, 3, 14)):
    meta = Metadata("Saga #1", ["Brian K. Vaughan"])
    meta.set_identifier("comicvine", "300001")
    meta.pubdate = pubdate
    return meta


class PrintResultTest(unittest.TestCase):
    def setUp(self):
        self.source = Comicvine(None)

    def capture(self, result, ranking, opf=False):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.source._print_result(result, ranking, opf=opf)
        return buf.getvalue()

    def test_plain_output_format(self):
        out = self.capture(make_result(), lambda r: 7)
        self.assertEqual(out, "(0007) - 300001: Saga #1 [2012-03-14]\n")

    def test_plain_output_without_pubdate_is_unknown(self):
        result = make_result()
        result.pubdate = None
        out = self.capture(result, lambda r: 12)
        self.assertEqual(out, "(0012) - 300001: Saga #1 [Unknown]\n")

    def test_plain_output_calls_ranking_with_result(self):
        seen = []
        result = make_result()
        self.capture(result, lambda r: seen.append(r) or 0)
        self.assertEqual(seen, [result])

    def test_opf_output(self):
        out = self.capture(make_result(), lambda r: 1 / 0, opf=True)
        self.assertIn("<package", out)
        self.assertIn("Saga #1", out)
        self.assertIn("300001", out)
        self.assertIn("Brian K. Vaughan", out)
        # OPF mode does not use the ranking or the plain format.
        self.assertNotIn("(0001)", out)


if __name__ == "__main__":
    unittest.main()
