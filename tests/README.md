# tests

The unittest suite is run with `calibre-debug -e tests/run_tests.py`; see the
"Testing" section of the top-level `README.md`.

## Library-based live validation (`live_library.py`)

`live_library.py` is a runner script, not a test. Its name does not match
`test_*.py`, so `run_tests.py` never discovers it. It calls the real Comicvine
API through the installed plugin, so it uses rate limit.

It reads a private library snapshot from `tests/private/library_snapshot.json`
(a JSON list of objects with `calibre_id`, `title`, `authors`, `comicvine`
and `comicvine-volume`). Everything under `tests/private/` is git-ignored.
Do not put real titles, authors or keys in tracked files.

Run it with plain Python 3 (it launches `calibre-debug` itself):

    python3 tests/live_library.py                 # pilot: 40 books = 35 with id + 5 without
    python3 tests/live_library.py --pilot 40 --no-id 5 --seed 20240601
    python3 tests/live_library.py --limit 2       # smoke test on the first 2 books
    python3 tests/live_library.py --dry-run       # show pending work only
    python3 tests/live_library.py --retry-errors  # re-run queries that errored

For each selected book it runs the installed plugin's identify twice (title
only, then title plus authors), without passing identifiers. The API key is
the one already configured in the plugin's preferences; it is never read by
the runner, printed, or written to output. Each query has a timeout
(`--timeout`, default 180 s) and the runner pauses `--delay` seconds between
queries, on top of the plugin's own rate limiting.

The sample is deterministic for a given `--seed`. Results are appended to
`tests/private/results.jsonl`, one line per book and mode, holding calibre
and Comicvine ids but no titles or authors. Re-running skips queries already
recorded, so an interrupted run resumes.

Classifications for books with a comicvine id: `match`, `found-not-first`,
`wrong-volume`, `wrong-issue` (not returned, top result in the expected or an
unknown volume), `no-result`, and `error` (API error or timeout, kept
separate from mismatches). Books without an id are `unverified`, with the top
candidate recorded.

## Stored-id verification (`verify_stored_ids.py`)

`verify_stored_ids.py` is also a runner script (not discovered by
`run_tests.py`). For books whose pilot result in `tests/private/results.jsonl`
was a non-match (`wrong-volume`, `wrong-issue`, `found-not-first`,
`no-result`; plus `error` with `--include-errors`), it looks up the stored
`comicvine` issue id and `comicvine-volume` id directly on the Comicvine API
and compares the title and authors Comicvine holds with the calibre ones.

    python3 tests/verify_stored_ids.py --dry-run          # list calibre ids and stored ids; no API call
    python3 tests/verify_stored_ids.py                    # run lookups (resumable)
    python3 tests/verify_stored_ids.py --include-errors --delay 5 --max-420 3
    python3 tests/verify_stored_ids.py --report-only      # rebuild the report from stored records

Each lookup runs in a `calibre-debug -e tests/verify_stored_ids.py -- --worker`
subprocess using the plugin's `pycomicvine` and the API key already in the
plugin preferences; the key is never printed or written. Books are classified
as `stored-ids-consistent`, `stored-ids-mismatch`,
`stored-issue-not-in-stored-volume` or `lookup-error`.

Records are appended to `tests/private/verify_results.jsonl` and the report is
written to `tests/private/verification.md` (both git-ignored; they contain
titles and authors). Re-running skips classified books and retries
`lookup-error` ones. After `--max-420` consecutive HTTP 420 (throttled)
responses (default 3) the run stops with a message; retry later. `--delay`
(default 3 s) spaces the lookups.

## Naming analysis (`analyse_naming.py`)

Compares calibre title, series and series index with what Comicvine (stored
issue id) and the installed `Goodreads` metadata source return, for the same
pilot sample as `live_library.py`. Run with plain `python3`:

    python3 tests/analyse_naming.py [--delay 3.0] [--max-420 3] [--timeout 60]
                                    [--source both|comicvine|goodreads]
                                    [--limit N] [--dry-run] [--report-only]

Comicvine lookups reuse `tests/private/verify_results.jsonl` records and query
only the missing books through the `verify_stored_ids.py` worker; the API key
is never read or printed here. Goodreads is called once per book through
`calibre-debug` (by Goodreads id, else ISBN). calibre series/series index and
the identifiers are read read-only from the library `metadata.db` (`--db` to
override). Raw answers are appended to `tests/private/naming_results.jsonl`
(finished books are skipped, errors retried on the next run) and comparisons
are written to `tests/private/naming_derived.jsonl`; both are git-ignored.
After `--max-420` consecutive HTTP 420 (or Goodreads errors) the run stops;
rerun later to resume. `--dry-run` lists pending queries without any API call.
