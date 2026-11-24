# Requirements Document

## Introduction

This feature adds a test suite for the calibre Comicvine metadata source plugin. The suite runs inside calibre through `calibre-debug` against the installed plugin, using real calibre modules. Offline unit tests mock `pycomicvine`. Opt-in live smoke tests call the real Comicvine API using the API key already configured in the installed Plugin's preferences. The suite reports bugs only: suspected defects are encoded as expected-failure tests and listed in a defect report. The suite makes no changes to plugin source files.

## Glossary

- **Plugin**: The installed calibre Comicvine metadata source plugin (`__init__.py`, `source.py`, `utils.py`, `config.py`, `pycomicvine/`).
- **Test_Suite**: The collection of automated tests, fixtures, and the runner delivered by this feature.
- **Test_Runner**: The entry point script that executes the Test_Suite through `calibre-debug`.
- **Offline_Tests**: Tests that run without network access and use a mocked `pycomicvine`.
- **Live_Smoke_Tests**: Opt-in tests that call the real Comicvine API.
- **API_Key**: The Comicvine API key already stored in the installed Plugin's Prefs. Normal runs under calibre need the API_Key to avoid throttling; the Test_Suite reads it but does not require, set, or modify it.
- **Live_Opt_In**: The explicit request to run Live_Smoke_Tests, given by setting the `COMICVINE_LIVE` environment variable to `1` or by passing the `--live` option to the Test_Runner.
- **Mock_Comicvine**: A test double that replaces the `pycomicvine` module and returns fixed volume, issue, person, and image data.
- **Expected_Failure**: A test that asserts the correct behavior of a suspected defect and is marked so that its failure does not fail the Test_Suite run.
- **Defect_Report**: A document at `tests/DEFECTS.md` listing each suspected defect, its location, its observed behavior, and its expected behavior.
- **Manifest**: The `MANIFEST` file listing the files packaged into the Plugin zip.
- **CLI_Entry**: The `Comicvine.cli_main` method invoked by `calibre-debug -r Comicvine`.
- **Token_Bucket**: The `TokenBucket` rate limiter in `utils.py`.
- **Prefs**: The Plugin's `PREFS` configuration store.

## Requirements

### Requirement 1: Run Inside Calibre

**User Story:** As a plugin maintainer, I want the tests to run inside calibre against the installed plugin, so that results reflect the real runtime environment.

#### Acceptance Criteria

1. WHEN the Test_Runner is invoked with `calibre-debug -e tests/run_tests.py`, THE Test_Runner SHALL import the Plugin from the `calibre_plugins.comicvine` namespace and execute the Test_Suite.
2. THE Test_Suite SHALL use real calibre modules, including `calibre.ebooks.metadata.book.base.Metadata`, `calibre.utils.config.JSONConfig`, and `calibre.ebooks.metadata.sources.base.Source`.
3. IF the Plugin is not importable from `calibre_plugins.comicvine`, THEN THE Test_Runner SHALL print an error message naming the missing plugin and exit with a non-zero status.
4. WHEN the Test_Suite finishes, THE Test_Runner SHALL print the counts of passed, failed, skipped, and expected-failure tests.
5. WHEN every non-expected-failure test passes or is skipped, THE Test_Runner SHALL exit with status 0.
6. IF any non-expected-failure test fails, THEN THE Test_Runner SHALL exit with a non-zero status.

### Requirement 2: Offline Tests

**User Story:** As a plugin maintainer, I want offline tests that need no network, so that I can run them anywhere without network access.

#### Acceptance Criteria

1. THE Offline_Tests SHALL replace `pycomicvine` with the Mock_Comicvine before each test and restore the original module after each test.
2. THE Offline_Tests SHALL complete without opening any network connection.
3. IF an Offline_Test attempts to open a network connection, THEN THE Test_Suite SHALL fail that test with a message identifying the attempted connection.
4. THE Offline_Tests SHALL run without requiring an API_Key or any Live_Opt_In.

### Requirement 3: Pure Logic Tests

**User Story:** As a plugin maintainer, I want pure-logic functions tested, so that title matching, scoring, and sorting behavior is verified.

#### Acceptance Criteria

1. THE Test_Suite SHALL test `normalised_title` with titles containing issue numbers, punctuation, leading articles, and empty strings.
2. THE Test_Suite SHALL test `score_title` for exact, partial, and non-matching titles with and without an issue number.
3. THE Test_Suite SHALL test `keygen` for ordering of results by title score and by Comicvine identifier.
4. THE Test_Suite SHALL test `build_term` for single-part, multi-part, and empty-part inputs.
5. THE Test_Suite SHALL test `Comicvine.identify_results_keygen` for ordering of results given title, authors, and identifiers.
6. THE Test_Suite SHALL test `Comicvine._print_result` output for both the plain and OPF output modes.

### Requirement 4: Mocked API Tests

**User Story:** As a plugin maintainer, I want the API-facing functions tested against a mocked Comicvine, so that lookups and error handling are verified offline.

#### Acceptance Criteria

1. THE Test_Suite SHALL test `build_meta` for title, series, series index, authors, publication date, comments, and identifiers using Mock_Comicvine issue data.
2. THE Test_Suite SHALL test `find_volumes` and `find_issues` with a title query, with a volume identifier, and with an empty result.
3. THE Test_Suite SHALL test `find_authors` with matching, non-matching, and empty author lists.
4. THE Test_Suite SHALL test `cover_urls` with and without the best-cover option.
5. WHEN a Mock_Comicvine call raises a Comicvine error, THE Test_Suite SHALL verify that `retry_on_cv_error` retries the call up to the configured retry count and then re-raises or returns as the Plugin specifies.
6. THE Test_Suite SHALL test that the Token_Bucket grants tokens up to its capacity and refills tokens over elapsed time, using a controllable clock.
7. THE Test_Suite SHALL test `Comicvine.identify` end to end with Mock_Comicvine data and verify that matching results are placed on the result queue.
8. THE Test_Suite SHALL test `Comicvine.enqueue` and verify that a built Metadata object is placed on the result queue with the Plugin's source relationship set.
9. THE Test_Suite SHALL test `Comicvine.download_cover` with a Mock_Comicvine cover URL and verify that cover data is placed on the result queue.

### Requirement 5: CLI Tests

**User Story:** As a plugin maintainer, I want the command-line entry point tested, so that documented usage keeps working.

#### Acceptance Criteria

1. THE Test_Suite SHALL test `CLI_Entry` parsing of the `t:`, `a:`, and `i:` arguments using the examples in README.md.
2. THE Test_Suite SHALL test `CLI_Entry` with multiple `a:` arguments, with a combined `i:comicvine:<id>` argument, and with an `i:comicvine-volume:<id>` argument.
3. THE Test_Suite SHALL test `CLI_Entry` with the `-o` option and verify OPF output.
4. IF `CLI_Entry` receives an argument with an unknown prefix, THEN THE Test_Suite SHALL verify the resulting behavior and record it in the Defect_Report if it is not a usage message.

### Requirement 6: Packaging Tests

**User Story:** As a plugin maintainer, I want packaging verified, so that the distributed zip contains every file the Plugin needs.

#### Acceptance Criteria

1. THE Test_Suite SHALL verify that every file listed in the Manifest exists in the repository.
2. THE Test_Suite SHALL include a required (non-optional) test verifying that every Python module imported by the Plugin from within the repository appears in the Manifest.
3. THE Test_Suite SHALL verify that `plugin-import-name-comicvine.txt` is listed in the Manifest.
4. THE Test_Suite SHALL verify that the Plugin class declares a name, a version tuple, and a minimum calibre version.

### Requirement 7: Live Smoke Tests

**User Story:** As a plugin maintainer, I want opt-in live smoke tests, so that I can confirm the Plugin works against the real Comicvine API.

#### Acceptance Criteria

1. WHILE no Live_Opt_In is given, THE Test_Suite SHALL skip every Live_Smoke_Test and report each as skipped with the reason "live tests not enabled (set COMICVINE_LIVE=1 or pass --live)".
2. WHERE a Live_Opt_In is given, THE Test_Suite SHALL run the Live_Smoke_Tests using the API_Key already configured in the Prefs of the installed Plugin.
3. WHERE a Live_Opt_In is given, THE Test_Suite SHALL run `calibre-debug -e __init__.py` as a subprocess and verify that the process exits with status 0.
4. WHERE a Live_Opt_In is given, THE Test_Suite SHALL run each `calibre-debug -r Comicvine` example from README.md as a subprocess and verify that the output contains at least one result.
5. THE Test_Suite SHALL leave the Prefs API_Key value unchanged during Live_Smoke_Tests.
6. THE Test_Suite SHALL exclude the API_Key value from all printed output and log files.

### Requirement 8: Suspected Defects

**User Story:** As a plugin maintainer, I want suspected defects captured without changing plugin code, so that I can triage them separately.

#### Acceptance Criteria

1. THE Test_Suite SHALL leave all Plugin source files unmodified.
2. THE Test_Suite SHALL mark each test that asserts the correct behavior of a suspected defect as an Expected_Failure.
3. IF an Expected_Failure test passes, THEN THE Test_Runner SHALL report it as an unexpected pass, list the test name, and leave the exit status unchanged by that unexpected pass.
4. THE Test_Suite SHALL include an Expected_Failure test for `cli_main` for each of these: (a) an `a:` argument containing authors separated by `&` yielding one author per name with surrounding spaces stripped, because `cli_main` splits on `&` without stripping spaces; (b) more than one `a:` argument retaining every author, because `cli_main` drops all but the first `a:` argument; (c) more than one `t:` or `i:` argument being handled consistently; and (d) a non-numeric Comicvine identifier being rejected with a usage or error message instead of an exception from `int()`.
5. THE Test_Suite SHALL include an Expected_Failure test for `normalised_title` verifying that the function returns a consistent `(issue_number, tokens)` shape, that is `(Optional[str], list)`, for every input type (str, None, int, and bytes), because the function currently returns `(0, "")` for non-str input.
6. THE Test_Suite SHALL include an Expected_Failure test for `find_title` verifying that the query does not contain the literal text "AND None" when no issue number is found in the title.
7. THE Test_Suite SHALL include Expected_Failure tests for `score_title` covering a `title` of None, a Levenshtein distance computed inside a loop, and a float compared as a string.
8. THE Test_Suite SHALL include an Expected_Failure test for `keygen` verifying that a string identifier and an integer identifier of equal value compare as equal.
9. THE Test_Suite SHALL include Expected_Failure tests for `retry_on_cv_error` verifying that `retries=0` still calls the target function once and returns its result, and that no sleep occurs after the final failed attempt.
10. THE Test_Suite SHALL include Expected_Failure tests for `build_meta` covering a non-numeric `issue_number` and `person_credits` of None.
11. THE Test_Suite SHALL include Expected_Failure tests for `identify` covering the `abort` event, the `timeout` argument, closing of the ThreadPool, and an empty intersection of volume and issue results.
12. THE Test_Suite SHALL include an Expected_Failure test for `download_cover` verifying that a failure in `cover_urls` is handled and logged inside the error handling block.
13. THE Test_Suite SHALL provide isolation fixtures that reset Token_Bucket state and Prefs values for each test case, and SHALL include tests verifying that these fixtures prevent state from leaking between independent test cases. THE Test_Suite SHALL mark a state-isolation test as an Expected_Failure only when the failure is caused by a genuine Plugin defect and not by a fixture deficiency.

### Requirement 9: Defect Report and Docs

**User Story:** As a plugin maintainer, I want a defect report and testing documentation, so that findings and usage are easy to find.

#### Acceptance Criteria

1. THE Test_Suite SHALL provide the Defect_Report at `tests/DEFECTS.md`.
2. THE Defect_Report SHALL list, for each suspected defect, the affected function, the file path, the observed behavior, the expected behavior, and the name of the Expected_Failure test that demonstrates it. An informational row, such as the unknown-prefix `cli_main` behavior from Requirement 5.4, SHALL instead reference the name of the normal test that records the behavior.
3. WHEN the Test_Runner finishes, THE Test_Runner SHALL print the path of the Defect_Report.
4. THE Test_Suite SHALL add a "Testing" section to README.md describing how to run the Offline_Tests, how to enable the Live_Smoke_Tests with `COMICVINE_LIVE=1` or `--live` (using the API_Key already configured in the installed Plugin), and how to read the Defect_Report.
5. THE Test_Suite SHALL place all new test files under the `tests/` directory, leaving the Manifest unchanged.
