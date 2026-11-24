# Design Document

## Overview

The Test_Suite is a standalone set of Python test modules under `tests/`, executed inside calibre's bundled Python through `calibre-debug`. It is built on the standard library `unittest` framework (available inside the calibre runtime with no extra dependency), with a thin custom runner (`tests/run_tests.py`) that loads the plugin, discovers tests, and applies the exit-code and reporting rules from Requirement 1.

Three test layers exist:

- **Offline unit tests** (`tests/test_*.py`, excluding `test_live.py`) — run with `pycomicvine` replaced by `Mock_Comicvine`. No network access, no API key required.
- **Live smoke tests** (`tests/test_live.py`) — opt in through `COMICVINE_LIVE=1` in the environment or the `--live` option of `tests/run_tests.py` (the Live_Opt_In), use the API key already configured in the plugin's `PREFS`, and exercise the real plugin end to end through subprocess calls to `calibre-debug`. The suite never reads, sets, or prints an API key.
- **Static/packaging checks** (`tests/test_packaging.py`) — inspect the Manifest and repository tree without importing calibre at all (though still run through the same runner for uniform reporting).

No plugin source file (`__init__.py`, `source.py`, `utils.py`, `config.py`, `pycomicvine/*`) is modified. Suspected defects are encoded as `unittest.expectedFailure` tests and documented in `tests/DEFECTS.md`.

## Verification of Suspected Defects Against Current Code

Before designing the Expected_Failure tests, each suspected defect in Requirement 8 was checked against the actual source. Findings:

| # | Function | File:Lines | Verified against current code |
|---|----------|-----------|----------------------------------|
| 1a | `cli_main` — `&` split without stripping (Req 8.4a) | `source.py:117-119` | Confirmed. `authors = authors[0].split("&")` splits on the bare `&` character and never strips whitespace, so `a:Brian K. Vaughan & Fiona Staples` yields `["Brian K. Vaughan ", " Fiona Staples"]` instead of one stripped name per author. The Expected_Failure test asserts `["Brian K. Vaughan", "Fiona Staples"]`. |
| 1b | `cli_main` — multiple `a:` arguments (Req 8.4b) | `source.py:117-119` | Confirmed. Each `a:` arg does `authors.append(...)` then `authors = authors[0].split("&")`. The list is replaced by the split of element `[0]` only, so every later `a:` argument is discarded (e.g. `a:A` then `a:B` yields `["A"]`, not `["A", "B"]`). The Expected_Failure test asserts that every author from every `a:` argument is retained. |
| 2 | `cli_main` — multiple `t:` or `i:` arguments (Req 8.4c) | `source.py:115-122` | Confirmed for `t:` (`title = ...` overwrites) and `i:` (`ids[idtype] = int(identifier)` overwrites the same key). No warning or error is produced; the earlier value is silently lost. The Expected_Failure test asserts consistent handling: either all values are honored or repeats are rejected with a message, and the first-versus-last choice is the same for `t:` and `i:`. |
| 3 | `cli_main` — non-numeric Comicvine id (Req 8.4d) | `source.py:121-122` | Confirmed. `int(identifier)` raises `ValueError` uncaught for any non-numeric id string (e.g. `i:comicvine:abc`), crashing the CLI instead of reporting a usage or error message. The Expected_Failure test asserts a usage or error message and no exception. |
| 4 | `normalised_title` — return type | `utils.py:211-242` | Confirmed. For a `str` title it returns `(issue_number_or_None, list_of_tokens)`; for any non-`str` input it returns `(0, "")`, an `int` and a `str` instead of the same `(str_or_None, list)` shape. The expected return shape for every input type is `(Optional[str], list)`, so a non-`str` input should yield `(None, [])`. The Expected_Failure test asserts this shape for `str`, `None`, `int`, and `bytes` inputs. |
| 5 | `find_title` — literal `"AND None"` (Req 8.6) | `utils.py:245-257` | Confirmed. The query is built as `" AND ".join(title_tokens) + " AND " + str(issue_number)`. When no issue number is found in the title (the "no issue number found" case of Requirement 8.6), `issue_number` is `None`, so `str(issue_number)` yields the literal text `"None"`, producing a search query containing the substring `AND None` that is sent to `find_volumes`. The `volumeid` argument does not affect this. The Expected_Failure test uses a title with no issue number and asserts that the query passed to `find_volumes` does not contain `AND None`. |
| 6a | `score_title` — `title=None` | `utils.py:297` | Confirmed as a latent defect in the function itself. `match_year.search(title)` raises `TypeError` when `title` is `None`. `keygen` currently never calls `score_title` with `title=None` (it guards with `if title:`), so the bug is only observable by calling `score_title` directly — which is exactly what the Expected_Failure unit test does. |
| 6b | `score_title` — Levenshtein ratio computed inside the token loop | `utils.py:305-312` | Confirmed. `Levenshtein.ratio(volume, title)` does not depend on `token` at all, yet it is called once per entry in `title_tokens` and its score contribution is added every iteration, so the similarity penalty is multiplied by the number of tokens instead of applied once. |
| 6c | `score_title` — float compared as a string | `utils.py:295, 313, 315` | Suspected and plausible, not fully confirmed offline. `meta.series_index` is set in `build_meta` via `meta.series_index = str(issue.issue_number)` (`utils.py:136`), but `calibre.ebooks.metadata.book.base.Metadata` is documented to store `series_index` as a `float` field and may coerce the assignment. If calibre coerces it to `float`, line 313 (`metadata.series_index != issue_number`) compares a `float` to the `str` `issue_number` extracted by `normalised_title` and will never be equal by value, and line 315 (`metadata.series_index not in title`) applies the `in` operator to a `float`, which raises `TypeError`. Calibre is not installed in this environment, so this could not be executed directly; the Expected_Failure test must be run with `calibre-debug` to confirm whether the coercion happens, and `tests/DEFECTS.md` notes this as "suspected, confirm under calibre runtime." |
| 7 | `keygen` — string id vs int id equality | `utils.py:337-342` | Confirmed. `metadata.get_identifier("comicvine")` returns the string set by `set_identifier("comicvine", str(issue.id))` in `build_meta`. `identifiers["comicvine"]` can be an `int`, since `cli_main` builds `ids[idtype] = int(identifier)` (`source.py:122`). `"123" == 123` is `False` in Python, so the fast-path identifier match never triggers when identifiers arrive as ints. |
| 8a | `retry_on_cv_error` — `retries=0` | `utils.py:93` | Confirmed. `for retry in range(1, retries + 1)` with `retries=0` is `range(1, 1)`, an empty range, so `target_function` is never called and `retry_function` implicitly returns `None`, instead of calling the target once. |
| 8b | `retry_on_cv_error` — sleep after final failed attempt | `utils.py:108-112` | Checked, and the current code already does the right thing: the `if retry == retries: raise` check happens before `time.sleep(...)`, so no sleep occurs after the last failed attempt. This Expected_Failure test is included per Requirement 8.9 but is likely to be an **unexpected pass**; `tests/DEFECTS.md` flags it as "suspected, likely already correct" and the runner's unexpected-pass reporting (Requirement 8.3) is the mechanism that surfaces it. An unexpected pass is reported by name but does not change the exit code. The `retries=0` case (8a) is covered only by an Expected_Failure test in `test_defects.py`, not by the retry property test. |
| 9a | `build_meta` — non-numeric `issue_number` | `utils.py:122-150` (assignment at 136) | Confirmed as a latent risk. `str(issue.issue_number)` never raises regardless of type, but the resulting `meta.series_index` assignment may fail or misbehave under calibre's float coercion for genuinely non-numeric issue numbers (e.g. `"Annual"`), the same mechanism as defect 6c. Flagged as suspected, to confirm under calibre runtime. |
| 9b | `build_meta` — `person_credits=None` | `utils.py:133` | Confirmed. `authors = [p.name for p in issue.person_credits]` iterates `issue.person_credits` unconditionally; if it is `None` this raises `TypeError: 'NoneType' object is not iterable`. Only `issue` and `issue.volume` are null-checked at the top of the function. |
| 10a | `identify` — `abort` ignored | `source.py:162-234` | Confirmed. The `abort` parameter is accepted but never read anywhere in the method body; a caller signalling abort has no effect on the in-flight `ThreadPool.map` call. |
| 10b | `identify` — `timeout` ignored | `source.py:162-234` | Confirmed. The `timeout` parameter is accepted but never passed to `pycomicvine` calls or used to bound the `ThreadPool.map` call. |
| 10c | `identify` — `ThreadPool` never closed | `source.py:226-232` | Confirmed. `pool = ThreadPool(...)` is created, `pool.map(...)` is called inside `try`/`finally`, but the `finally` block only calls `shutdown.set()`; `pool.close()`/`pool.join()` are never called, leaking worker threads. |
| 10d | `identify` — empty intersection of volume/issue and author results | `source.py:220-224` | Confirmed as a behavioral edge case: `candidate_issues = issues.intersection(candidate_issues)` can legitimately become empty when the author search returns issues disjoint from the title-based candidates, silently yielding zero results with no fallback or logging. |
| 11 | `download_cover` — `cover_urls` failure not handled | `source.py:236-257` | Confirmed exactly as suspected. The `for url in utils.cover_urls(...)` call sits **outside** the `try` block; only `browser.open_novisit(...).read()` inside the loop body is guarded by `try`/`except Exception: log.exception(...)`. If `cover_urls` itself raises (e.g. the inner `pycomicvine.Issue` lookup fails), the exception propagates out of `download_cover` unhandled. |
| 12 | `Token_Bucket`/`Prefs` state leaking between tests (Req 8.13) | `utils.py:36-41`, `config.py:11` | Confirmed as a test-design hazard rather than a plugin bug: `TokenBucket.__init__` opens a real `JSONConfig("plugins/comicvine_tokens")` file on disk, and `config.py` module level `PREFS = JSONConfig('plugins/comicvine')` is a process-wide singleton. Any test that touches either without explicit save/restore will leak state into the next test and into the user's real calibre config. The Test_Suite must isolate both (see Fixtures, below). Per Requirement 8.13, ordinary tests verify that the fixtures prevent leakage; a state-isolation test is an Expected_Failure only when a genuine Plugin defect causes the failure, never because of a fixture deficiency. |

No defect required a source file change to confirm; all were verified by static reading of `source.py` and `utils.py`, except 6c and 9a which depend on calibre's `Metadata.series_index` coercion and are marked "suspected, confirm under calibre runtime" since calibre is not installed in this analysis environment.

## Architecture

```
tests/
  __init__.py             # makes tests/ a package for discovery
  run_tests.py          # Test_Runner for calibre-debug -e
  DEFECTS.md             # Defect_Report
  mock_comicvine.py       # Mock_Comicvine double + fixture helpers
  fixtures.py             # shared fixtures: fake clock, isolated JSONConfig, isolated PREFS
  test_mock_restore.py            # Property 5
  test_runner_exit_status.py      # Property 1
  test_runner_counts.py           # Property 2
  test_runner_expected_failure.py # Property 7
  test_retry_property.py          # Property 3
  test_token_bucket_property.py   # Property 4
  test_state_isolation.py         # Property 9
  test_redact.py                  # Property 8
  test_defect_report_structure.py # Property 10
  test_packaging.py       # Requirement 6, Property 6
  test_normalised_title.py
  test_score_title.py
  test_keygen.py
  test_build_term.py      # Requirement 3
  test_identify_results_keygen.py
  test_print_result.py
  test_build_meta.py
  test_find_volumes_issues.py
  test_find_authors.py
  test_cover_urls.py
  test_retry_on_cv_error.py
  test_token_bucket.py     # Requirement 4
  test_identify.py
  test_enqueue.py
  test_download_cover.py
  test_cli_main.py         # Requirement 5
  test_defects.py          # Expected_Failure tests, Requirement 8
  test_live.py              # Requirement 7 (opt-in, includes redact helper)
```

`run_tests.py` is invoked as `calibre-debug -e tests/run_tests.py`. It:

0. Parses the `--live` option; when present, sets `COMICVINE_LIVE=1` in `os.environ` before test discovery.
1. Verifies `calibre_plugins.comicvine` is importable; on failure prints an error naming the plugin and calls `sys.exit(1)` (Requirement 1.3).
2. Uses `unittest.TestLoader().discover("tests", pattern="test_*.py")`.
3. Runs the suite with a custom `unittest.TextTestRunner` subclass and a custom `TestResult` subclass that tracks pass, fail, skip, expected-failure, and unexpected-pass counts separately. This `TestResult` deliberately overrides unittest's default behavior: the default `wasSuccessful()` returns `False` when there are unexpected successes, whereas the custom result ignores unexpected passes when computing success.
4. Leaves live-test skipping to `test_live.py` (a `unittest.skipUnless` on the opt-in flag), so the runner needs no special case (Requirement 7.1).
5. Prints the four counts (Requirement 1.4), lists each unexpected pass by name (Requirement 8.3), and prints the `tests/DEFECTS.md` path (Requirement 9.3).
6. Exits `0` only if there are zero failures or errors outside the expected-failure set (Requirements 1.5, 1.6). An unexpected pass is reported but does **not** change the exit code.

## Components and Interfaces

### Mock_Comicvine (`tests/mock_comicvine.py`)

A module-shaped test double with the same public surface the plugin touches: `Issue`, `Issues`, `Volume`, `Volumes`, `Person`, `People`, `hook_register`, `hook_run`, and `error` (re-exporting the real `pycomicvine.error` exception classes, since `utils.retry_on_cv_error` and callers catch those concrete types). It is backed by small in-memory fixture records (one volume, one issue, one person, one set of image URLs) so the same fixture data can be asserted against in multiple tests.

A context manager / `unittest.TestCase` mixin, `with_mock_comicvine()`, is responsible for:

- Saving a reference to the real `calibre_plugins.comicvine.pycomicvine` module object.
- Monkey-patching the `pycomicvine` names used by `source.py`, `utils.py`, and `config.py` to point at `Mock_Comicvine` for the duration of a test (`setUp`).
- Restoring the saved reference in `tearDown`, unconditionally (using `addCleanup` so restoration happens even if the test body raises) — this directly implements the Requirement 2.1 fixture invariant and is the behavior validated by the design's Property 5 below.
- Installing a `socket.socket` guard (raising `AssertionError` naming the attempted host/port) for the duration of offline tests, satisfying Requirement 2.2/2.3.

### Fixtures (`tests/fixtures.py`)

- `FakeClock`: a controllable clock object with `.advance(seconds)` and `.now()`, injected into `TokenBucket` tests in place of `time.time`/`time.sleep` so Requirement 4.6 can be tested deterministically and quickly.
- `isolated_jsonconfig(name)`: a context manager that redirects `JSONConfig` to a temporary directory (via monkey-patching `calibre.utils.config.JSONConfig`'s base path or substituting a plain dict-backed stand-in with the same `__getitem__`/`refresh()`/`defaults` surface) so `TokenBucket` tests never touch the real on-disk config, and restores/deletes it after each test.
- `isolated_prefs()`: same idea for the module-level `PREFS` singleton in `config.py` — snapshot `PREFS` contents before a test, restore them after, regardless of outcome.

These two fixtures are what Requirement 8.13 requires: `test_state_isolation.py` contains ordinary (non-expected-failure) tests asserting that two independently-run test cases that mutate `TokenBucket`/`PREFS` state each observe the same baseline when the fixtures are applied. A state-isolation test is marked Expected_Failure only if a genuine Plugin defect makes it fail; a failure caused by a deficiency in the fixtures themselves is a suite bug to fix, not an expected failure.

### Defect_Report (`tests/DEFECTS.md`)

Generated once by hand (not dynamically re-generated at test time, to keep the report readable and stable), with one row per defect, each row naming: affected function, file path, observed behavior, expected behavior, and the Expected_Failure test name. Content mirrors the verification table above. `test_defects.py`'s Expected_Failure tests are cross-checked against this file by `test_defect_report_structure.py`, which parses `tests/DEFECTS.md` and confirms every row has the affected function, file path, observed behavior, and expected behavior, and that every named test exists in the suite: an Expected_Failure test for defect rows, a normal test for informational rows (Requirement 9.2).

Informational rows (for example the unknown-prefix `cli_main` behavior) describe observed behavior that is not asserted as a defect. They are marked `informational` and, in the test-name column, reference the name of the normal (non-expected-failure) test that records the behavior, rather than an Expected_Failure test.

### CLI_Entry tests (`tests/test_cli_main.py`)

Drive `Comicvine().cli_main(args)` directly (no subprocess) with `pycomicvine` mocked, capturing `sys.stdout` via `contextlib.redirect_stdout`. Covers the README examples verbatim (Requirement 5.1), multiple `a:`/`i:` combinations (5.2), `-o`/OPF output (5.3), and an unknown-prefix argument (5.4) — the latter is checked against actual behavior (an unknown-prefix arg is currently silently ignored, since no `if arg.startswith(...)` branch matches it and no `else` exists) and recorded as an informational row in `tests/DEFECTS.md` if it is not a usage message; it is a usage gap rather than a crash, so the row references the normal test in `test_cli_main.py` that records the behavior, not an Expected_Failure.

### Live_Smoke_Tests (`tests/test_live.py`)

- Opt-in: the Live_Opt_In is `COMICVINE_LIVE=1` in the environment or the `--live` option of `tests/run_tests.py`; `--live` sets `COMICVINE_LIVE=1` in the process environment before discovery, so `test_live.py` has a single check. Without it, the tests are skipped suite-wide via `unittest.skipUnless(os.environ.get("COMICVINE_LIVE") == "1", "live tests not enabled (set COMICVINE_LIVE=1 or pass --live)")`, and each is reported as skipped with exactly that reason. The suite never reads `COMICVINE_API_KEY` and does not accept a key from the environment.
- Key source: the subprocesses run `calibre-debug` against the installed plugin, which uses the API key already stored in its own `PREFS`. The tests do not read, write, or override `PREFS["api_key"]`, so there is nothing to restore. If no key is configured in `PREFS`, the live tests skip with a reason saying so (checked by a subprocess probe that reports only whether a key is present, never its value).
- Uses `subprocess.run(["calibre-debug", "-e", "__init__.py"], ...)` and `subprocess.run(["calibre-debug", "-r", "Comicvine", ...README examples...], ...)`, asserting exit code `0` / non-empty result output respectively.
- No key is ever printed. As a safeguard, all captured subprocess output and logger output still passes through `redact(text, secrets)` before being printed or written, replacing any known secret string with `***REDACTED***`. `redact` lives in `tests/test_live.py` and is unit-tested by `tests/test_redact.py`.

## Data Models

Mock fixture records are plain `dataclasses` (or simple namespaces, matching the project's existing lack of dataclass usage — a judgment call documented here as a minor new dependency on `dataclasses`, which is standard library only):

```python
@dataclass
class MockVolume:
    id: int
    name: str
    publisher: "MockPublisher | None"
    description: str = ""

@dataclass
class MockIssue:
    id: int
    name: str
    volume: MockVolume
    issue_number: str
    person_credits: list  # list[MockPerson] or None, to drive defect 9b
    description: str = ""
    store_date: "datetime | None" = None
    cover_date: "datetime | None" = None
    image: dict = field(default_factory=dict)
```

No persistent data model is introduced for the plugin itself; the Test_Suite's only "storage" is the temporary, isolated `JSONConfig` stand-ins described above.

## Error Handling

- Import failures of the plugin (Requirement 1.3) are caught at the top of `run_tests.py` around the discovery import, printing `f"Comicvine plugin not importable from calibre_plugins.comicvine: {exc}"` and exiting `1` before any test runs.
- Network-connection attempts inside offline tests raise `AssertionError` from the socket guard rather than actually connecting, and that `AssertionError` is surfaced as an ordinary test failure with the attempted address in its message (Requirement 2.3).
- Fixture restoration (`Mock_Comicvine` swap-back, `PREFS`/`TokenBucket` isolation) is always registered via `addCleanup`, which `unittest` guarantees runs even when the test body raises, so a failing test cannot leave global state corrupted for the next test.
- Expected_Failure tests use `@unittest.expectedFailure`; an `AssertionError` (or the specific exception the defect analysis above predicts, e.g. `TypeError` for defect 9b) inside such a test is treated as expected, while unexpectedly passing is reported by `run_tests.py`'s custom `TestResult` (Requirement 8.3).
- Subprocess-based live tests capture both stdout and stderr and pass them through `redact` before any print or log. They never modify `PREFS`.
- An unexpected pass is reported by name and does not change the exit code; only failures and errors outside the expected-failure set do.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — here, the Test_Suite and Test_Runner being built, not the plugin under test (whose own behavior is deliberately left unmodified and is instead documented via the Defect_Report).*

### Property 1: Exit status matches failure outcome

For any set of test results produced by a run (any mixture of passed, failed, skipped, expected-failure, and unexpected-pass outcomes), the Test_Runner SHALL exit with status 0 if and only if the set contains no failing test outside the expected-failure set.

**Validates: Requirements 1.5, 1.6, 8.3**

### Property 2: Reported counts match actual outcomes

For any set of test results, the four counts printed by the Test_Runner (passed, failed, skipped, expected-failure) SHALL equal the actual number of tests in each corresponding category.

**Validates: Requirements 1.4**

### Property 3: Retry decorator calls exactly as configured

For any retry count N >= 1 and any function that raises on its first M calls then succeeds (or never succeeds), `retry_on_cv_error(retries=N)` SHALL call the wrapped function exactly `min(N, M+1)` times (or N times if it never succeeds), returning the function's result on the first success and re-raising the final exception if no call within the first N attempts succeeds.

The property test generates N >= 1 only. The `N = 0` case is intentionally excluded because the current implementation never calls the target (defect 8a); it is covered by an Expected_Failure test in `test_defects.py` that uses `retries=0` and asserts one call and the returned result. The property statement above is the intended contract for N >= 1, and once defect 8a is fixed the generator can be widened to N >= 0.

**Validates: Requirements 4.5, 8.9**

### Property 4: Token bucket never exceeds capacity and refills monotonically

For any sequence of `consume()` calls interleaved with elapsed-time advances on a fake clock, the number of tokens available from `TokenBucket` SHALL never exceed the configured burst capacity, and SHALL be a non-decreasing function of elapsed time until that capacity is reached.

**Validates: Requirements 4.6**

### Property 5: Mock swap is always restored

For any offline test function — including one that raises an exception or fails an assertion — running it under the `with_mock_comicvine()` fixture SHALL leave `calibre_plugins.comicvine.pycomicvine` bound to the original module object once the fixture's cleanup has run.

**Validates: Requirements 2.1**

### Property 6: Manifest covers every file it must

For every file path listed in `MANIFEST`, that file SHALL exist in the repository; and for every module imported by the plugin files from within the `calibre_plugins.comicvine` namespace, the corresponding file SHALL be listed in `MANIFEST`. The import-coverage check is a required (non-optional) test per Requirement 6.2.

**Validates: Requirements 6.1, 6.2**

### Property 7: Expected-failure tests never count as ordinary failures

For any test decorated as an Expected_Failure, if it fails or raises, the Test_Runner SHALL NOT include it in the failed count or in the non-expected-failure failure set used by Property 1; if it unexpectedly passes, the Test_Runner SHALL report its name as an unexpected pass.

**Validates: Requirements 8.2, 8.3**

### Property 8: API key is never leaked in captured output

For any non-empty secret string and any text (including text that contains the secret zero or more times), `redact(text, [secret])` SHALL return text in which the secret does not appear. This is a safeguard property: the live tests do not handle an API key directly, but all captured subprocess and log output is still redacted.

**Validates: Requirements 7.6**

### Property 9: Isolation fixtures prevent state leakage

For any sequence of mutations applied to `TokenBucket` state or `PREFS` values inside a test that uses `isolated_jsonconfig` / `isolated_prefs`, the state observed at the start of the next test SHALL equal the baseline state captured before the first test, regardless of test order or whether the mutating test passed or failed. This verifies the suite's own isolation fixtures; the plugin's lack of built-in isolation is documented separately by the Expected_Failure tests.

**Validates: Requirements 8.13**

### Property 10: Defect report rows are structurally complete

For every row in `tests/DEFECTS.md`, the row SHALL contain a non-empty affected function, file path, observed behavior, and expected behavior. Every row that is not marked `informational` SHALL also name an Expected_Failure test that exists in the Test_Suite. Every `informational` row SHALL instead name a normal (non-expected-failure) test that exists in the Test_Suite.

**Validates: Requirements 9.2**

## Testing Strategy

**Unit tests** (example-based) cover: README-literal CLI invocations (Requirement 5), specific Mock_Comicvine-backed scenarios for `build_meta`/`find_volumes`/`find_issues`/`find_authors`/`cover_urls`/`identify`/`enqueue`/`download_cover` (Requirement 4), `_print_result` plain vs OPF output (Requirement 3.6), and the packaging/manifest example checks that don't need randomization (Requirement 6.3, 6.4).

**Property tests** (implemented with `unittest` + a lightweight in-repo random-input loop of >= 100 iterations per property, since adding `hypothesis` as a new third-party dependency is avoidable for this scope — each property test loops with `random.seed` variation and asserts the invariant every iteration) cover Properties 1-10 above, plus the plugin-logic properties already implied by Requirement 3 (`normalised_title`, `score_title`, `keygen`, `build_term`, `identify_results_keygen`) using randomized titles/tokens/identifiers as inputs, run against the real (unmodified) plugin functions so they also double as regression coverage for the confirmed defects once/if the plugin is fixed later.

**Expected_Failure tests** (Requirement 8) are ordinary `unittest` tests decorated with `@unittest.expectedFailure`, one per confirmed-or-suspected defect in the verification table above, each asserting the *expected* (bug-free) behavior so that the assertion currently fails for the documented reason.
