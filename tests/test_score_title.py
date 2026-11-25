"""Tests for ``utils.score_title`` (Requirement 3.2).

``score_title`` only reads ``series``, ``series_index``, ``pubdate`` and
``comments`` from the metadata, so a light stand-in with a string
``series_index`` is used.  (Under calibre's real ``Metadata`` the index is a
float, which trips suspected defect 6c; that is covered in test_defects.py.)
"""
import datetime
import unittest
from types import SimpleNamespace

from calibre_plugins.comicvine import utils


def meta(series="Saga", index="1", pubdate=None, comments=None):
    return SimpleNamespace(
        series=series, series_index=index, pubdate=pubdate, comments=comments
    )


class ScoreTitleTests(unittest.TestCase):
    def test_exact_match_with_issue_number_scores_zero(self):
        score = utils.score_title(
            meta(), title="saga #1", issue_number="1", title_tokens=["saga"]
        )
        self.assertEqual(score, 0)

    def test_exact_match_without_issue_number_scores_zero(self):
        score = utils.score_title(
            meta(), title="saga #1", issue_number=None, title_tokens=["saga"]
        )
        self.assertEqual(score, 0)

    def test_partial_match_scores_worse_than_exact(self):
        exact = utils.score_title(
            meta(), title="saga #1", issue_number="1", title_tokens=["saga"]
        )
        partial = utils.score_title(
            meta(), title="saga deluxe #1", issue_number="1", title_tokens=["saga", "deluxe"]
        )
        self.assertGreater(partial, exact)

    def test_non_matching_title_scores_worse_than_exact(self):
        exact = utils.score_title(
            meta(), title="saga #1", issue_number="1", title_tokens=["saga"]
        )
        other = utils.score_title(
            meta(), title="xxxx #1", issue_number="1", title_tokens=["xxxx"]
        )
        self.assertGreater(other, exact)

    def test_missing_token_adds_ten_per_token(self):
        base = utils.score_title(
            meta(), title="saga #1", issue_number="1", title_tokens=[]
        )
        missing = utils.score_title(
            meta(), title="saga #1", issue_number="1", title_tokens=["zzz"]
        )
        self.assertGreaterEqual(missing - base, 10)

    def test_wrong_issue_number_adds_fifty(self):
        right = utils.score_title(
            meta(), title="saga #1", issue_number="1", title_tokens=["saga"]
        )
        wrong = utils.score_title(
            meta(), title="saga #1", issue_number="2", title_tokens=["saga"]
        )
        self.assertEqual(wrong - right, 50)

    def test_issue_number_absent_from_title_adds_ten(self):
        present = utils.score_title(
            meta(index="1"), title="saga #1", issue_number=None, title_tokens=["saga"]
        )
        # Same-length title so only the "index in title" penalty differs.
        absent = utils.score_title(
            meta(index="1"), title="saga #2", issue_number=None, title_tokens=["saga"]
        )
        self.assertGreaterEqual(absent - present, 10)

    def test_year_in_title_penalises_year_difference(self):
        pubdate = datetime.datetime(2012, 3, 1)
        same = utils.score_title(
            meta(pubdate=pubdate), title="saga #1 (2012)", issue_number="1",
            title_tokens=["saga"],
        )
        off = utils.score_title(
            meta(pubdate=pubdate), title="saga #1 (2015)", issue_number="1",
            title_tokens=["saga"],
        )
        self.assertEqual(off - same, 3)

    def test_year_in_title_without_pubdate_adds_ten(self):
        dated = utils.score_title(
            meta(pubdate=datetime.datetime(2012, 1, 1)), title="saga #1 (2012)",
            issue_number="1", title_tokens=["saga"],
        )
        undated = utils.score_title(
            meta(pubdate=None), title="saga #1 (2012)", issue_number="1",
            title_tokens=["saga"],
        )
        self.assertEqual(undated - dated, 10)

    def test_collection_comments_add_fifty(self):
        plain = utils.score_title(
            meta(), title="saga #1", issue_number="1", title_tokens=["saga"]
        )
        collected = utils.score_title(
            meta(comments="Collecting issues #1-6"), title="saga #1",
            issue_number="1", title_tokens=["saga"],
        )
        self.assertEqual(collected - plain, 50)


class FoldTests(unittest.TestCase):
    def test_fold_ignores_accents_and_case(self):
        self.assertEqual(utils.fold("Café Noir"), utils.fold("cafe noir"))

    def test_fold_ignores_leading_article(self):
        self.assertEqual(utils.fold("The Example"), utils.fold("example"))

    def test_score_title_equal_for_accent_and_case_variants(self):
        def score(series, title, token):
            return utils.score_title(
                meta(series=series), title=title, issue_number="1",
                title_tokens=[token],
            )
        plain = score("Cafe Noir", "cafe noir #1", "cafe")
        self.assertEqual(plain, 0)
        self.assertEqual(score("Café Noir", "Cafe Noir #1", "CAFÉ"), plain)
        self.assertEqual(score("The Example", "example #1", "example"), plain)

    def test_yyyymm_series_index_not_penalised(self):
        score = utils.score_title(
            meta(series="Example", index="202008"), title="example",
            issue_number="202008", title_tokens=["example"],
        )
        # Only the length difference (" #202008") contributes; no +10 penalty.
        self.assertEqual(score, len(" #202008"))


if __name__ == "__main__":
    unittest.main()
