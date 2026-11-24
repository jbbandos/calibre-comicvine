"""Tests for ``utils.keygen`` (Requirement 3.3)."""
import unittest

from calibre.ebooks.metadata.book.base import Metadata

from calibre_plugins.comicvine import utils


class IdMetadata(Metadata):
    """Metadata exposing ``get_identifier``, which ``keygen`` calls.

    The real calibre ``Metadata`` only has ``get_identifiers``; without this
    shim ``keygen`` always hits its ``AttributeError`` guard and the
    identifier fast path cannot be exercised.
    """

    def get_identifier(self, typ):
        return self.get_identifiers().get(typ)


def make_meta(series="Saga", index="1", authors=None, cv_id="100", cls=IdMetadata):
    meta = cls("Title", authors or ["Brian K. Vaughan"])
    meta.series = series
    meta.series_index = index
    if cv_id is not None:
        meta.set_identifier("comicvine", cv_id)
    return meta


def score(meta, title, **kwargs):
    kwargs.setdefault("title_tokens", [t.lower() for t in title.split() if t[0] != "#"])
    kwargs.setdefault("issue_number", "1")
    return utils.keygen(meta, title=title, **kwargs)


class KeygenTitleOrderingTest(unittest.TestCase):
    def test_no_title_no_authors_scores_zero(self):
        self.assertEqual(utils.keygen(make_meta()), 0)

    def test_matching_title_scores_better_than_non_matching(self):
        meta = make_meta()
        self.assertLess(score(meta, "Saga #1"), score(meta, "Completely Different #1"))

    def test_matching_title_beats_partial_title(self):
        meta = make_meta()
        self.assertLess(score(meta, "Saga #1"), score(meta, "Saga Special Edition #1"))

    def test_wrong_issue_number_is_penalised(self):
        meta = make_meta()
        self.assertLess(
            score(meta, "Saga #1", issue_number="1"),
            score(meta, "Saga #1", issue_number="2"),
        )

    def test_results_sort_by_score(self):
        good = make_meta(series="Saga", cv_id="1")
        bad = make_meta(series="Paper Girls", cv_id="2")
        ranked = sorted(
            [bad, good], key=lambda m: score(m, "Saga #1")
        )
        self.assertEqual(ranked, [good, bad])


class KeygenAuthorTest(unittest.TestCase):
    def test_missing_author_adds_penalty(self):
        meta = make_meta(authors=["Brian K. Vaughan"])
        self.assertEqual(utils.keygen(meta, authors=["Brian K. Vaughan"]), 0)
        self.assertEqual(utils.keygen(meta, authors=["Fiona Staples"]), 10)
        self.assertEqual(
            utils.keygen(meta, authors=["Fiona Staples", "Someone Else"]), 20
        )


class KeygenIdentifierTest(unittest.TestCase):
    def test_matching_identifier_returns_zero_regardless_of_title(self):
        meta = make_meta(series="Paper Girls", cv_id="100")
        result = utils.keygen(
            meta,
            title="Saga #1",
            identifiers={"comicvine": "100"},
            title_tokens=["saga"],
            issue_number="1",
        )
        self.assertEqual(result, 0)

    def test_matching_identifier_sorts_first(self):
        match = make_meta(series="Paper Girls", cv_id="100")
        # "other" has the better title but a different identifier; the
        # identifier match must still win (score 0 vs. >0 for "other").
        other = make_meta(series="Saga", index="2", cv_id="200")
        ids = {"comicvine": "100"}
        ranked = sorted(
            [other, match],
            key=lambda m: utils.keygen(
                m,
                title="Saga #1",
                identifiers=ids,
                title_tokens=["saga"],
                issue_number="1",
            ),
        )
        self.assertIs(ranked[0], match)

    def test_non_matching_identifier_falls_through_to_title_score(self):
        meta = make_meta(series="Paper Girls", cv_id="200")
        with_ids = utils.keygen(
            meta,
            title="Saga #1",
            identifiers={"comicvine": "100"},
            title_tokens=["saga"],
            issue_number="1",
        )
        without_ids = score(meta, "Saga #1")
        self.assertEqual(with_ids, without_ids)
        self.assertGreater(with_ids, 0)

    def test_missing_comicvine_key_falls_through(self):
        meta = make_meta()
        self.assertEqual(
            utils.keygen(meta, identifiers={"isbn": "1"}), 0
        )  # no title/authors, so base score

    def test_plain_metadata_without_get_identifier_falls_through(self):
        """Documents current runtime: stock Metadata lacks ``get_identifier``,
        so the AttributeError guard swallows it and the id fast path is skipped."""
        meta = make_meta(cls=Metadata, cv_id="100")
        if hasattr(meta, "get_identifier"):
            self.skipTest("this calibre's Metadata provides get_identifier")
        paper = make_meta(series="Paper Girls", cls=Metadata, cv_id="100")
        self.assertGreater(
            utils.keygen(
                paper,
                title="Saga #1",
                identifiers={"comicvine": "100"},
                title_tokens=["saga"],
                issue_number="1",
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
