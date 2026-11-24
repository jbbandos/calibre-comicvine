"""Property 10: Defect_Report rows are structurally complete.

**Validates: Requirements 9.2**

Parses ``tests/DEFECTS.md`` and checks every table row. Needs no calibre
import: the test suite is inspected statically with ``ast``.
"""
import ast
import glob
import os
import random
import re
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFECTS_MD = os.path.join(TESTS_DIR, "DEFECTS.md")
HEADER = ["id", "function", "file", "observed behavior",
          "expected behavior", "test", "status"]
ITERATIONS = 100


def parse_rows(text):
    """Return a list of dicts for the rows of the defects table."""
    rows = []
    header = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            header = None if rows else header
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def strip_ticks(value):
    return value.strip().strip("`").strip()


def collect_tests():
    """Map test name -> list of is_expected_failure flags, from test_*.py."""
    found = {}
    for path in glob.glob(os.path.join(TESTS_DIR, "test_*.py")):
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name.startswith("test"):
                expected = any(
                    "expectedFailure" in ast.dump(dec)
                    for dec in node.decorator_list)
                found.setdefault(node.name, []).append(expected)
    return found


def is_normal_test_row(row):
    """Informational and fixed rows are recorded by a normal passing test."""
    status = row.get("status", "").lower()
    return status.startswith(("informational", "fixed"))


def row_problems(row, tests):
    """Return a list of problems with one row (empty list means complete)."""
    problems = []
    for key in ("function", "file", "observed behavior", "expected behavior"):
        if not row.get(key, "").strip():
            problems.append("empty %s" % key)
    name = strip_ticks(row.get("test", ""))
    if not name:
        problems.append("no test name")
        return problems
    flags = tests.get(name)
    if not flags:
        problems.append("test %s not found" % name)
    elif is_normal_test_row(row):
        if not any(not f for f in flags):
            problems.append("normal-test row %s is expectedFailure" % name)
    elif not any(flags):
        problems.append("test %s is not an expectedFailure" % name)
    return problems


class DefectReportStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DEFECTS_MD, encoding="utf-8") as handle:
            cls.rows = parse_rows(handle.read())
        cls.tests = collect_tests()

    def test_report_has_rows_and_expected_columns(self):
        self.assertTrue(self.rows, "no table rows parsed from DEFECTS.md")
        for column in HEADER:
            self.assertIn(column, self.rows[0])

    def test_every_row_is_structurally_complete(self):
        for row in self.rows:
            self.assertEqual(row_problems(row, self.tests), [],
                             "row %s" % row.get("id"))

    def test_at_least_one_informational_row(self):
        self.assertTrue(any(
            r.get("status", "").lower().startswith("informational")
            for r in self.rows))

    def test_row_ids_are_unique(self):
        ids = [r["id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_random_corruption_is_detected(self):
        """Validator property: blanking a required cell or renaming the test
        to a nonexistent one is always reported."""
        rng = random.Random(10)
        keys = ("function", "file", "observed behavior", "expected behavior")
        for _ in range(ITERATIONS):
            row = dict(rng.choice(self.rows))
            if rng.random() < 0.5:
                row[rng.choice(keys)] = rng.choice(["", "  "])
            else:
                row["test"] = "`test_missing_%d`" % rng.randrange(10**6)
            self.assertTrue(row_problems(row, self.tests))

    def test_random_row_kind_mismatch_is_detected(self):
        """Pointing a defect row at a normal test (or an informational row at
        an expectedFailure test) is always reported."""
        normal = [n for n, f in self.tests.items() if not any(f)]
        failing = [n for n, f in self.tests.items() if all(f)]
        self.assertTrue(normal and failing)
        rng = random.Random(11)
        for _ in range(ITERATIONS):
            row = dict(rng.choice(self.rows))
            informational = is_normal_test_row(row)
            row["test"] = "`%s`" % rng.choice(failing if informational
                                              else normal)
            self.assertTrue(row_problems(row, self.tests))


if __name__ == "__main__":
    unittest.main()
