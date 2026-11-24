# Implementation Plan: Plugin Test Suite

## Overview

Build a `unittest`-based test suite under `tests/`, written in Python and run inside calibre with `calibre-debug -e tests/run_tests.py`. Work proceeds from shared infrastructure (Mock_Comicvine, fixtures, runner) to offline unit tests, then CLI, packaging, defect (Expected_Failure), and live smoke tests, and ends with documentation. No plugin source file is modified. All new files live under `tests/`, plus a "Testing" section in `README.md`.

## Tasks

- [x] 1. Set up test infrastructure
  - [x] 1.1 Create Mock_Comicvine and shared fixtures
    - Create `tests/mock_comicvine.py` with `Issue`, `Issues`, `Volume`, `Volumes`, `Person`, `People`, `hook_register`, `hook_run`, and a re-export of the real `pycomicvine.error` classes, backed by `MockVolume`/`MockIssue` dataclass fixture records
    - Add a `with_mock_comicvine()` mixin that swaps `pycomicvine` in `source.py`, `utils.py`, and `config.py` and restores it via `addCleanup`
    - Add a `socket.socket` guard that raises `AssertionError` naming the attempted host/port
    - Create `tests/fixtures.py` with `FakeClock` (`now()`, `advance()`), `isolated_jsonconfig(name)`, and `isolated_prefs()`
    - Add `tests/__init__.py` if needed for discovery
    - _Requirements: 1.2, 2.1, 2.2, 2.3, 2.4, 4.6_

  - [x] 1.2 Implement the Test_Runner
    - Create `tests/run_tests.py`: verify `calibre_plugins.comicvine` imports (print error naming the plugin and `sys.exit(1)` on failure)
    - Discover `test_*.py` with `unittest.TestLoader` and run with a custom `TestResult` that tracks passed, failed, skipped, expected-failure, and unexpected-pass counts
    - Print the four counts, list unexpected passes by name, and print the `tests/DEFECTS.md` path
    - Override `wasSuccessful()` in the custom result so an unexpected pass is reported but does not change the exit code
    - Exit 0 only when there are no non-expected-failure failures or errors
    - Parse the `--live` option and set `COMICVINE_LIVE=1` in `os.environ` before test discovery
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.6, 8.3, 9.3_

  - [x]* 1.3 Write property test for mock restoration
    - **Property 5: Mock swap is always restored**
    - Create `tests/test_mock_restore.py`; run passing, failing, and raising test functions under the fixture for 100+ iterations and assert the original `pycomicvine` binding is restored
    - **Validates: Requirements 2.1**

  - [x]* 1.4 Write property test for runner exit status
    - **Property 1: Exit status matches failure outcome**
    - Create `tests/test_runner_exit_status.py`; generate random mixes of outcomes (including unexpected passes) and assert exit status 0 iff no failing test outside the expected-failure set; an unexpected pass never changes the exit status
    - **Validates: Requirements 1.5, 1.6, 8.3**

  - [x]* 1.5 Write property test for runner counts
    - **Property 2: Reported counts match actual outcomes**
    - Create `tests/test_runner_counts.py`; assert printed counts equal actual category totals for random outcome sets
    - **Validates: Requirements 1.4**

  - [x]* 1.6 Write property test for expected-failure handling
    - **Property 7: Expected-failure tests never count as ordinary failures**
    - Create `tests/test_runner_expected_failure.py`; assert expected failures are excluded from the failed count and unexpected passes are reported by name without changing the exit code
    - **Validates: Requirements 8.2, 8.3**

- [x] 2. Implement pure logic tests
  - [x] 2.1 Write tests for `normalised_title`
    - Create `tests/test_normalised_title.py` covering titles with issue numbers, punctuation, leading articles, and empty strings
    - _Requirements: 3.1_

  - [x] 2.2 Write tests for `score_title`
    - Create `tests/test_score_title.py` covering exact, partial, and non-matching titles, with and without an issue number
    - _Requirements: 3.2_

  - [x] 2.3 Write tests for `keygen`
    - Create `tests/test_keygen.py` covering ordering by title score and by Comicvine identifier
    - _Requirements: 3.3_

  - [x] 2.4 Write tests for `build_term`
    - Create `tests/test_build_term.py` covering single-part, multi-part, and empty-part inputs
    - _Requirements: 3.4_

  - [x] 2.5 Write tests for `identify_results_keygen` and `_print_result`
    - Create `tests/test_identify_results_keygen.py` for ordering by title, authors, and identifiers
    - Create `tests/test_print_result.py` for plain and OPF output, capturing stdout with `contextlib.redirect_stdout`
    - _Requirements: 3.5, 3.6_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement mocked API tests
  - [x] 4.1 Write tests for `build_meta`
    - Create `tests/test_build_meta.py` verifying title, series, series index, authors, publication date, comments, and identifiers from Mock_Comicvine issue data
    - _Requirements: 4.1_

  - [x] 4.2 Write tests for `find_volumes` and `find_issues`
    - Create `tests/test_find_volumes_issues.py` covering a title query, a volume identifier, and an empty result
    - _Requirements: 4.2_

  - [x] 4.3 Write tests for `find_authors`
    - Create `tests/test_find_authors.py` covering matching, non-matching, and empty author lists
    - _Requirements: 4.3_

  - [x] 4.4 Write tests for `cover_urls`
    - Create `tests/test_cover_urls.py` covering with and without the best-cover option
    - _Requirements: 4.4_

  - [x] 4.5 Write tests for `retry_on_cv_error`
    - Create `tests/test_retry_on_cv_error.py` using `FakeClock` to patch sleep; verify retries up to the configured count and then re-raise or return as the Plugin specifies
    - _Requirements: 4.5_

  - [x]* 4.6 Write property test for retry decorator
    - **Property 3: Retry decorator calls exactly as configured**
    - Create `tests/test_retry_property.py`; for 100+ random N >= 1 and M, assert the call count is `min(N, M+1)` (or N if it never succeeds) and the final result or re-raised exception
    - Generate N >= 1 only; `retries=0` is excluded because of defect 8a and is covered by the Expected_Failure test in `tests/test_defects.py` (task 8.1) with `retries=0`, asserting one call and the returned result
    - **Validates: Requirements 4.5, 8.9**

  - [x] 4.7 Write tests for `TokenBucket`
    - Create `tests/test_token_bucket.py` using `FakeClock` and `isolated_jsonconfig`; verify tokens are granted up to capacity and refill over elapsed time
    - _Requirements: 4.6_

  - [x]* 4.8 Write property test for token bucket
    - **Property 4: Token bucket never exceeds capacity and refills monotonically**
    - Create `tests/test_token_bucket_property.py`; run random sequences of consume and clock advances for 100+ iterations
    - **Validates: Requirements 4.6**

  - [x] 4.9 Write tests for `Comicvine.identify`
    - Create `tests/test_identify.py` verifying end to end that matching Mock_Comicvine results are placed on the result queue
    - _Requirements: 4.7_

  - [x] 4.10 Write tests for `Comicvine.enqueue`
    - Create `tests/test_enqueue.py` verifying a built Metadata object is queued with the Plugin's source relationship set
    - _Requirements: 4.8_

  - [x] 4.11 Write tests for `Comicvine.download_cover`
    - Create `tests/test_download_cover.py` with a Mock_Comicvine cover URL and a stubbed browser; verify cover data is placed on the result queue
    - _Requirements: 4.9_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement CLI tests
  - Create `tests/test_cli_main.py` driving `Comicvine().cli_main(args)` directly with Mock_Comicvine and captured stdout
  - Cover the README `t:`, `a:`, `i:` examples, multiple `a:` arguments, `i:comicvine:<id>`, `i:comicvine-volume:<id>`, and `-o` OPF output
  - Verify the behavior for an unknown-prefix argument (currently silently ignored) and assert what actually happens
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 7. Implement packaging tests
  - [x] 7.1 Write packaging example tests
    - Create `tests/test_packaging.py` (no calibre import needed) verifying every `MANIFEST` entry exists, `plugin-import-name-comicvine.txt` is listed, and the Plugin class declares a name, version tuple, and minimum calibre version
    - Check the Plugin class name, version and minimum calibre version by reading `source.py` as text (e.g. with `ast`), since `source.py` imports calibre and cannot be imported without it
    - _Requirements: 6.1, 6.3, 6.4_

  - [x] 7.2 Write Manifest import-coverage test (required)
    - **Property 6: Manifest covers every file it must**
    - Extend `tests/test_packaging.py`: parse imports in plugin files and assert each in-repo module is in `MANIFEST`; this test is required, not optional
    - **Validates: Requirements 6.1, 6.2**

- [x] 8. Implement suspected defect tests and Defect_Report
  - [x] 8.1 Write Expected_Failure tests for `cli_main` and `utils.py` functions
    - Create `tests/test_defects.py` with `@unittest.expectedFailure` tests asserting correct behavior for:
      - `cli_main` (four Expected_Failure tests):
        - 1a: `a:Brian K. Vaughan & Fiona Staples` yields `["Brian K. Vaughan", "Fiona Staples"]` (split on `&` with whitespace stripped)
        - 1b: multiple `a:` arguments retain every author
        - 2: multiple `t:` or `i:` arguments are handled consistently (all honored, or repeats rejected with a message; same first-versus-last choice for `t:` and `i:`)
        - 3: non-numeric Comicvine id (e.g. `i:comicvine:abc`) gives a usage or error message and no exception
      - `normalised_title` returns `(Optional[str], list)` for `str`, `None`, `int`, and `bytes` inputs
      - `find_title`: query passed to `find_volumes` does not contain "AND None" when the title has no issue number
      - `score_title`: `title=None`, Levenshtein ratio computed inside token loop, float compared as string (flag as confirm under calibre runtime)
      - `keygen` string vs int identifier equality
      - `retry_on_cv_error`: `retries=0` calls the target once and returns its result; no sleep after final failed attempt (likely unexpected pass, which is reported but does not change the exit code)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_

  - [x] 8.2 Write Expected_Failure tests for `build_meta`, `identify`, and `download_cover`
    - Append to `tests/test_defects.py` tests for:
      - `build_meta`: non-numeric `issue_number` (confirm under calibre runtime), `person_credits=None`
      - `identify`: `abort`, `timeout`, ThreadPool closing, empty volume/issue intersection
      - `download_cover`: `cover_urls` failure handled and logged inside the error handling block
    - Do not mark any state-isolation test as an Expected_Failure unless a genuine Plugin defect causes the failure; fixture deficiencies are suite bugs (see task 8.5)
    - _Requirements: 8.1, 8.2, 8.10, 8.11, 8.12, 8.13_

  - [x] 8.3 Write the Defect_Report
    - Create `tests/DEFECTS.md` with one row per defect: affected function, file path, observed behavior, expected behavior, Expected_Failure test name
    - Include separate `cli_main` rows for 1a, 1b, 2, and 3
    - Mark 6c and 9a as "suspected, confirm under calibre runtime" and 8b as "suspected, likely already correct"
    - Include the unknown-prefix `cli_main` behavior as an `informational` row whose test-name column references the normal (non-expected-failure) test in `tests/test_cli_main.py` that records the behavior
    - _Requirements: 5.4, 9.1, 9.2_

  - [x]* 8.4 Write property test for Defect_Report structure
    - **Property 10: Defect report rows are structurally complete**
    - Create `tests/test_defect_report_structure.py`; parse `tests/DEFECTS.md` and assert every row has a non-empty affected function, file path, observed behavior, and expected behavior
    - Assert every non-informational row names an Expected_Failure test that exists in the suite, and every `informational` row names a normal (non-expected-failure) test that exists in the suite
    - **Validates: Requirements 9.2**

  - [x]* 8.5 Write state-isolation tests for the fixtures
    - **Property 9: Isolation fixtures prevent state leakage**
    - Create `tests/test_state_isolation.py` with ordinary (non-expected-failure) tests: mutate `TokenBucket`/`PREFS` state under `isolated_jsonconfig`/`isolated_prefs` in one test case, including a case that fails or raises, and assert the next test case observes the baseline state regardless of order
    - A failure here indicates a fixture deficiency to fix in `tests/fixtures.py`, not an Expected_Failure
    - **Validates: Requirements 8.13**

- [x] 9. Implement live smoke tests
  - [x] 9.1 Write Live_Smoke_Tests
    - Create `tests/test_live.py` skipped with `unittest.skipUnless(os.environ.get("COMICVINE_LIVE") == "1", "live tests not enabled (set COMICVINE_LIVE=1 or pass --live)")`; the `--live` option of the runner sets `COMICVINE_LIVE=1`, so this is the single check
    - Do not read `COMICVINE_API_KEY` and do not read, set, or modify `PREFS["api_key"]`; the subprocesses use the key already configured in the installed Plugin's Prefs
    - Skip with a reason if no key is configured, using a subprocess probe that reports only whether a key is present, never its value
    - Run `calibre-debug -e __init__.py` and assert exit 0
    - Run each README `calibre-debug -r Comicvine` example and assert output has at least one result
    - Add a `redact(text, secrets)` helper as a safeguard, applied to all captured stdout, stderr, and log output before printing or writing
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x]* 9.2 Write property test for output redaction
    - **Property 8: API key is never leaked in captured output**
    - Create `tests/test_redact.py`; for 100+ random non-empty secrets and texts (containing the secret zero or more times), assert the secret does not appear in `redact(text, [secret])`
    - **Validates: Requirements 7.6**

- [x] 10. Document testing in README
  - Add a "Testing" section to `README.md` covering running the Offline_Tests with `calibre-debug -e tests/run_tests.py`, enabling Live_Smoke_Tests with `COMICVINE_LIVE=1` or the `--live` option (using the API key already configured in the installed Plugin; no `COMICVINE_API_KEY` is needed and the suite does not modify Prefs), and reading `tests/DEFECTS.md`
  - Leave `MANIFEST` unchanged
  - _Requirements: 9.4, 9.5_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Fix touched_fields identifier keys and release 0.14.4
  - Approved exception to the "no plugin source changes" rule
  - [x] 12.1 Fix touched_fields keys and bump version to 0.14.4
    - In `source.py` change `touched_fields` entries `"identifiers:comicvine"` and `"identifiers:comicvine-volume"` to `"identifier:comicvine"` and `"identifier:comicvine-volume"` (calibre `Source.test_fields` in `base.py` line 467 checks `startswith('identifier:')`)
    - Bump `version` from `(0, 14, 3)` to `(0, 14, 4)` in `source.py`
    - Search for `0.14.3` / `0, 14, 3` and update every other place the version is recorded (README.md, MANIFEST-related files, and the `pylint/calibre_plugins/comicvine/source.py` copy)
    - _Requirements: 8.1, 8.2_
  - [x] 12.2 Add defect test and update Defect_Report
    - Add a test in `tests/test_defects.py` asserting every `touched_fields` key is a known field name or starts with `identifier:`; write it as a normal passing test now that the fix is applied (no `@expectedFailure`)
    - Add a row to `tests/DEFECTS.md` with status "fixed in 0.14.4", keeping `tests/test_defect_report_structure.py` passing
    - Update the `tests/test_packaging.py` version check if it pins the version
    - _Requirements: 7.1, 7.6_
  - [x] 12.3 Install plugin and run full suite including live tests
    - Install the plugin into calibre following `README.md` lines 26-27
    - Run `COMICVINE_LIVE=1 calibre-debug -e tests/run_tests.py` and report the results
    - Update the README Testing section if needed
    - _Requirements: 9.4, 9.5_
## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The Manifest import-coverage test (7.2) is required, not optional
- An unexpected pass of an Expected_Failure test is reported by name and does not change the runner's exit code
- Property tests are implemented with `unittest` and a seeded random loop of 100+ iterations, with no new third-party dependency
- Expected_Failure tests assert correct behavior and are expected to fail against the unmodified Plugin
- Calibre is required to run the suite; tests that depend on calibre's `Metadata` coercion must be confirmed under `calibre-debug`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "1.5", "1.6", "2.1", "2.2", "2.3", "2.4", "2.5"] },
    { "id": 3, "tasks": ["3"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "4.10", "4.11"] },
    { "id": 5, "tasks": ["5"] },
    { "id": 6, "tasks": ["6", "7.1", "8.1", "9.1", "10"] },
    { "id": 7, "tasks": ["7.2", "8.2", "9.2"] },
    { "id": 8, "tasks": ["8.3", "8.5"] },
    { "id": 9, "tasks": ["8.4"] },
    { "id": 10, "tasks": ["11"] },
    { "id": 11, "tasks": ["12.1"] },
    { "id": 12, "tasks": ["12.2"] },
    { "id": 13, "tasks": ["12.3"] }
  ]
}
```
