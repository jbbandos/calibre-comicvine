# Defect Report

Suspected defects in the Comicvine plugin, found while building the test
suite. The plugin source was **not** modified. Each defect row is demonstrated
by an `unittest.expectedFailure` test in `tests/test_defects.py` that asserts
the *correct* behaviour. The one informational row is recorded by a normal
test.

Findings come from reading the source and from the calibre-runtime checks made
while writing `tests/test_defects.py`. Run the suite with
`calibre-debug -e tests/run_tests.py`.

Status values:

- `defect`: confirmed; the Expected_Failure test fails as expected.
- `defect (refined)`: confirmed, but the trigger differs from the original
  suspicion (see the notes below the table).
- `suspected, likely correct`: the test is expected to pass unexpectedly. The
  runner lists unexpected passes by name and the exit status is unchanged.
- `informational`: observed behaviour that is not asserted as a defect.
- `fixed in <version>`: a defect that has been fixed in the plugin. It is
  recorded by a normal passing regression test, not an Expected_Failure.

## Defects

| ID | Function | File | Observed behavior | Expected behavior | Test | Status |
|----|----------|------|-------------------|-------------------|------|--------|
| 1a | `Comicvine.cli_main` | `source.py` | `a:Brian K. Vaughan & Fiona Staples` splits on `&` without stripping, giving `["Brian K. Vaughan ", " Fiona Staples"]`. | One stripped name per author: `["Brian K. Vaughan", "Fiona Staples"]`. | `test_ampersand_separated_authors_are_stripped` | defect |
| 1b | `Comicvine.cli_main` | `source.py` | Each `a:` argument replaces the list with the split of element `[0]`, so every later `a:` argument is dropped (`a:Alice a:Bob` gives `["Alice"]`). | Every author from every `a:` argument is retained. | `test_multiple_author_arguments_are_all_retained` | defect |
| 2 | `Comicvine.cli_main` | `source.py` | Repeated `t:` or `i:` arguments overwrite the earlier value with no message. | Repeats are rejected with a message, or the same choice (first or last) is made for `t:` and `i:` and the user is told. | `test_repeated_title_and_id_arguments_handled_consistently` | defect |
| 3 | `Comicvine.cli_main` | `source.py` | `i:comicvine:abc` raises an uncaught `ValueError` from `int()`. | A usage or error message, with no exception. | `test_non_numeric_comicvine_id_reports_error` | defect |
| 4 | `normalised_title` | `utils.py` | Non-`str` input returns `(0, "")`: an `int` and a `str`. | `(Optional[str], list)` for every input type (`str`, `None`, `int`, `bytes`). | `test_return_shape_is_consistent_for_every_input_type` | defect |
| 5 | `find_title` | `utils.py` | With no issue number in the title, the volume query is built with `str(None)` and contains the literal `AND None`. | No `AND None` in the query passed to `find_volumes`. | `test_query_has_no_literal_and_none_without_issue_number` | defect |
| 6a | `score_title` | `utils.py` | `title=None` raises `TypeError` in `match_year.search(title)`. `keygen` guards against it, so only direct calls hit it. | Returns an integer score. | `test_title_none_returns_a_score` | defect |
| 6b | `score_title` | `utils.py` | `Levenshtein.ratio(volume, title)` does not depend on the token but is evaluated inside the token loop, so the similarity penalty scales with the token count. | The penalty is applied once. | `test_similarity_penalty_applied_once_not_per_token` | defect (see note 6b) |
| 6c | `score_title` | `utils.py` | With a numeric `series_index`, `series_index not in title` raises `TypeError`, and `series_index != issue_number` compares a float with a str. | An exact match scores 0. | `test_real_metadata_float_series_index_scores_exact_match_zero` | defect (refined, see note 6c) |
| 7 | `keygen` | `utils.py` | The identifier from `build_meta` is the str `"123"`; `cli_main` passes the int `123`. `"123" == 123` is `False`, so the fast path never matches. | A str and an int of equal value compare as equal. | `test_string_and_int_identifier_of_equal_value_match` | defect (see note 7) |
| 7b | `keygen` | `utils.py` | The fast path calls `metadata.get_identifier(...)`, which stock calibre `Metadata` does not have, so it never fires, even for equal str identifiers. | The identifier fast path works with stock `Metadata`. | `test_identifier_fast_path_works_with_stock_metadata` | defect (see note 7) |
| 8a | `retry_on_cv_error` | `utils.py` | `retries=0` gives `range(1, 1)`, so the target is never called and the wrapper returns `None`. | The target is called once and its result returned. | `test_zero_retries_still_calls_target_once` | defect |
| 8b | `retry_on_cv_error` | `utils.py` | The final-attempt check raises before `time.sleep`, so no sleep follows the last failure. The code already behaves correctly. | No back-off sleep after the final failed attempt. | `test_no_sleep_after_final_failed_attempt` | suspected, likely correct (see note 8b) |
| 9a | `build_meta` | `utils.py` | A non-numeric issue number such as `"Annual"` is stored verbatim as a `str` in `series_index`. No exception is raised. | `series_index` is not left as a non-numeric `str`. | `test_non_numeric_issue_number_gives_numeric_series_index` | defect (refined, see note 9a) |
| 9b | `build_meta` | `utils.py` | `person_credits=None` raises `TypeError` in `[p.name for p in issue.person_credits]`. | Metadata with no authors. | `test_person_credits_none_is_tolerated` | defect |
| 10a | `Comicvine.identify` | `source.py` | The `abort` event is never read; setting it does not stop work. | A set `abort` event means nothing is queued. | `test_abort_event_stops_work` | defect |
| 10b | `Comicvine.identify` | `source.py` | The `timeout` argument is accepted but never used to bound the wait. | `timeout` bounds how long `identify` waits for workers. | `test_timeout_bounds_identify` | defect |
| 10c | `Comicvine.identify` | `source.py` | The `ThreadPool` is never closed or joined; `finally` only sets `shutdown`. | The pool is closed or terminated after use. | `test_thread_pool_is_closed` | defect |
| 10d | `Comicvine.identify` | `source.py` | When the author search is disjoint from the title candidates, the intersection is empty and zero results are returned silently. | Fall back to the title candidates, or log the fact. | `test_empty_author_intersection_is_not_silent` | defect |
| 11 | `Comicvine.download_cover` | `source.py` | `utils.cover_urls(...)` is called outside the `try` block, so a failure there propagates unhandled. | The failure is caught and logged. | `test_cover_urls_failure_is_handled_and_logged` | defect |
| 12 | `Comicvine.cli_main` (unknown prefix) | `source.py` | An argument with an unknown prefix (for example `x:something`) is neither used nor reported. No usage message is printed and the search still runs. | A usage message. Recorded as informational only. | `test_unknown_prefix_is_silently_ignored` | informational |
| 13 | `Comicvine.touched_fields` | `source.py` | `touched_fields` listed `identifiers:comicvine` and `identifiers:comicvine-volume` (plural). calibre's `Source.test_fields` only recognises the `identifier:` prefix, so these were treated as plain field names that can never be satisfied. | Keys `identifier:comicvine` and `identifier:comicvine-volume`; `test_fields` returns `None` for metadata carrying both identifiers. | `test_touched_fields_are_plain_names_or_singular_identifiers` | fixed in 0.14.4 |

Test names in the Test column are in `tests/test_defects.py`, except row 12,
which is in `tests/test_cli_main.py` (`test_unknown_prefix_is_silently_ignored`).
Row 12 is a normal test, not an Expected_Failure, and it asserts the current
behaviour. Row 13 (`TouchedFieldsTests` in `tests/test_defects.py`) is also a
normal passing test.

## Notes

**6b (Levenshtein).** The test skips itself when the `Levenshtein` module is
not importable (`hasattr(utils, "Levenshtein")` is false). A skipped
Expected_Failure shows up as skipped rather than as an expected failure, so a
run without that module does not exercise this defect.

**6c (float `series_index`).** The original suspicion was that calibre coerces
`series_index` to a float whenever `build_meta` assigns it. Under this calibre
runtime that is not the case: `Metadata` keeps the assigned `str`, so
`score_title` does not fail on metadata produced by `build_meta`. The
`TypeError` is reachable only when `series_index` is numeric, for example a
value loaded from a calibre library. The test therefore assigns `1.0`
directly.

**7 and 7b (keygen identifier).** Two independent problems stop the identifier
fast path from ever matching:

- 7b: stock `Metadata` has no `get_identifier`, so the call never gets as far
  as a comparison. Test 7 uses an `IdMetadata` shim (from `test_keygen.py`)
  that adds `get_identifier`, to isolate the str-versus-int mismatch.
- 7: even with `get_identifier` available, `"123"` (from `build_meta`) never
  equals `123` (from `cli_main`).

Both must be fixed for the fast path to work.

**8b (sleep after final failure).** An unexpected pass is the expected outcome.
`retry_on_cv_error` already raises before sleeping on the last attempt. The
test is kept because Requirement 8.9 asks for it. The runner reports it by
name as an unexpected pass and the exit status does not change.

**9a (non-numeric issue number).** The original suspicion was that
`build_meta` would raise or fail on coercion. It does not: `Metadata` stores
the string `"Annual"` verbatim, with no exception (even `"1"` stays a `str`).
The defect is that a non-numeric `str` ends up in a field calibre documents as
a float.
