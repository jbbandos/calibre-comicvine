"""Tests for Comicvine.identify_results_keygen (Requirement 3.5)."""
import types
import unittest
from functools import partial

from calibre.ebooks.metadata.book.base import Metadata
from calibre_plugins.comicvine import utils
from calibre_plugins.comicvine.source import Comicvine


def make_meta(title="Saga #1", authors=("Brian K. Vaughan",), cv_id="100"):
    meta = Metadata(title, list(authors))
    meta.set_identifier("comicvine", cv_id)
    return meta


def stub_meta(title, series_index, authors=(), cv_id=None):
    """Metadata stand-in with a str series_index.

    Calibre's Metadata coerces series_index to float, which makes
    ``score_title`` raise TypeError (suspected defect 6c); the stub lets
    the title-ordering behaviour be tested independently of that.
    """
    return types.SimpleNamespace(
        series=title.lower(),
        series_index=series_index,
        pubdate=None,
        comments=None,
        authors=list(authors),
        get_identifier=lambda name: cv_id,
    )


class IdentifyResultsKeygenTest(unittest.TestCase):
    def setUp(self):
        self.source = Comicvine(None)

    def test_returns_partial_over_utils_keygen(self):
        key = self.source.identify_results_keygen("Saga #1", ["A"], {"comicvine": "5"})
        self.assertIsInstance(key, partial)
        self.assertIs(key.func, utils.keygen)
        self.assertEqual(key.keywords["title"], "Saga #1")
        self.assertEqual(key.keywords["authors"], ["A"])
        self.assertEqual(key.keywords["identifiers"], {"comicvine": "5"})
        self.assertEqual(key.keywords["issue_number"], "1")
        self.assertEqual(key.keywords["title_tokens"], ["saga"])

    def test_non_string_title_gives_empty_title_state(self):
        key = self.source.identify_results_keygen(None, None, None)
        self.assertEqual(key.keywords["title"], "")
        self.assertEqual(key.keywords["issue_number"], 0)
        self.assertEqual(key.keywords["title_tokens"], "")

    def test_no_criteria_scores_zero(self):
        key = self.source.identify_results_keygen()
        self.assertEqual(key(make_meta()), 0)

    def test_matching_identifier_ranks_first(self):
        key = self.source.identify_results_keygen(
            None, ["Nobody"], {"comicvine": "100"}
        )
        # Stub with get_identifier: the installed calibre's Metadata has no
        # get_identifier(), so keygen's AttributeError guard swallows it and
        # the fast path never fires for real Metadata objects (see report).
        match = stub_meta("Saga", "1", ["Brian K. Vaughan"], cv_id="100")
        other = stub_meta("Saga", "1", ["Brian K. Vaughan"], cv_id="200")
        self.assertEqual(key(match), 0)
        self.assertGreater(key(other), key(match))
        self.assertEqual(sorted([other, match], key=key)[0], match)

    def test_authors_each_missing_author_adds_penalty(self):
        key = self.source.identify_results_keygen(None, ["A", "B"], None)
        both = make_meta(authors=("A", "B"))
        one = make_meta(authors=("A",))
        none = make_meta(authors=("Z",))
        self.assertEqual(key(both), 0)
        self.assertEqual(key(one), 10)
        self.assertEqual(key(none), 20)
        self.assertEqual(sorted([none, one, both], key=key), [both, one, none])

    def test_closer_title_ranks_first(self):
        key = self.source.identify_results_keygen("Saga #1", None, None)
        close = stub_meta("Saga", "1")
        far = stub_meta("Completely Different Series Name", "1")
        self.assertLess(key(close), key(far))
        self.assertEqual(sorted([far, close], key=key)[0], close)


if __name__ == "__main__":
    unittest.main()
