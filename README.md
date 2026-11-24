# Comicvine
A calibre metadata source plugin for comicvine.com.

# Fork
This fork is is now the "official" version of the plugin (jbbandos@github). 
The owner of the original code (@xchewtoyx) was informed.
It is due to a rework, to better handle the idiossincracies of the comicvine search

## Install

Dependencies:

 * pycomicvine (https://github.com/authmillenon/pycomicvine)
 * Levenshtein (optional)

For convenience, a modified version of pycomicvine 0.9 is included in
the distribution to make sure there are no external dependencies.
This will only be loaded if the module is not found elsewhere in the
system path.

Create a plugin zip file containing the files listed in MANIFEST and
install.

On a Unix system this can be done using:

    $ zip Comicvine -@ < MANIFEST
    $ calibre-customize -a Comicvine.zip

The single command `calibre-customize -b .` from within the source
directory will also work, but will include many unnecessary files.

## Usage 

Allows you to search comicvine for metadata for your comics and
graphic novels stored in Calibre.

You will need an API Key to use this source
 
Get one at (http://www.comicvine.com/api/)

Once configured you can use this plugin from the GUI (download
metadata) or from the fetch-ebook-metadata command.  

Both of these methods will try all active metadata sources, and only
return the most preferred result.

To return all comicvine matches from the command line you can search
using:

    $ calibre-debug -r Comicvine [t:title] [a:author] [i:type:id]

This will search for comics that match the given fields.  Any spaces
should be enclosed in quotes, e.g.: 

    $ calibre-debug -r Comicvine t:'The Invisibles #15' \
        a:'Grant Morrison'
    Found: The Invisibles #15: She-Man, Part Three: Apocalipstick [1995-12-01 00:00:00]
    Found: The Invisibles, Volume Two #15: The Philadelphia Experiment [1998-05-01 00:00:00]

or:

    $ calibre-debug -r Comicvine i:comicvine:41736
    Found: The Invisibles #15: She-Man, Part Three: Apocalipstick [1995-12-01 00:00:00]

    $ calibre-debug -r Comicvine t:'Batman #12' i:comicvine-volume:42721
    (0000) - 349621: Batman #12: Ghost in the Machine; [2012-08-08]

You can specify more authors in a query by separating them with " & " as they 
are shown in calibre metadata. Remember to enclose the whole authors query string 
in quotes.

## Testing

The test suite lives in `tests/` and runs inside calibre against the
installed plugin (`calibre_plugins.comicvine`), so install the plugin
first. It uses `unittest` and needs no extra dependencies. The suite
does not modify any plugin source file and is not part of `MANIFEST`.

### Offline tests

Run everything with:

    $ calibre-debug -e tests/run_tests.py

The offline tests replace `pycomicvine` with a mock (`tests/mock_comicvine.py`),
open no network connections, and need no API key. They cover:

 * pure logic: `normalised_title`, `score_title`, `keygen`, `build_term`,
   `identify_results_keygen`, `_print_result`
   (`test_normalised_title.py`, `test_score_title.py`, `test_keygen.py`,
   `test_build_term.py`, `test_identify_results_keygen.py`,
   `test_print_result.py`)
 * mocked API behavior: `build_meta`, `find_volumes`/`find_issues`,
   `find_authors`, `cover_urls`, `retry_on_cv_error`, `TokenBucket`,
   `identify`, `enqueue`, `download_cover` (`test_build_meta.py`,
   `test_find_volumes_issues.py`, `test_find_authors.py`,
   `test_cover_urls.py`, `test_retry_on_cv_error.py`,
   `test_token_bucket.py`, `test_identify.py`, `test_enqueue.py`,
   `test_download_cover.py`)

Shared helpers are in `tests/fixtures.py` (fake clock, isolated
`JSONConfig` and `PREFS`) and `tests/mock_comicvine.py`. Further test
modules cover the command line (`test_cli_main.py`), packaging
(`test_packaging.py`), and suspected defects (`test_defects.py`). They run
with the same command.

At the end of a run the runner prints the number of passed, failed,
skipped, and expected-failure tests, lists each skipped test with its
skip reason, lists any unexpected passes, and prints the path of the
defect report. It exits with status 0 unless a
test fails outside the expected-failure set.

### Live smoke tests

Live tests call the real Comicvine API. They are skipped by default
(reason: "live tests not enabled (set COMICVINE_LIVE=1 or pass --live)").
Enable them with either:

    $ COMICVINE_LIVE=1 calibre-debug -e tests/run_tests.py
    $ calibre-debug -e tests/run_tests.py --live

They use the API key already configured in the installed plugin's
preferences. No `COMICVINE_API_KEY` is needed, and the suite does not
read, change, or print the key. If no key is configured, the live tests
are skipped. They live in `tests/test_live.py` and run
`calibre-debug -e __init__.py` and each `calibre-debug -r Comicvine`
example from this README, checking for a zero exit status and at least
one result.

### Defect report

The suite only reports bugs; it never changes plugin code. Suspected
defects are written as expected-failure tests that assert the correct
behavior, so they fail today without failing the run. They are listed in
`tests/DEFECTS.md`, with one row per defect giving the affected
function, file path, observed behavior, expected behavior, and the name of
the test that demonstrates it. Rows marked `informational` describe
behavior that is not asserted as a defect and point to a normal test that
records it.

If an expected-failure test starts to pass, the runner lists it as an
unexpected pass. This does not change the exit status, but usually means
the defect was fixed or the report entry is wrong, so update
`tests/DEFECTS.md`.

## Contribute 

You can contribute to calibre-comicvine by submitting issue tickets on GitHub
(https://github.com/jbbandos/calibre-comicvine), including Pull
Requests. 
You can contribute to pycomicvine lib by submitting issue tickets on GitHub
(https://github.com/miri64/pycomicvine), including Pull
Requests. 
You can test the comicvine plugin by calling:

    calibre-debug -e __init__.py

## License
Copyright (c) 2013 Russell Heilling
Changes and updates Copyright (c) 2021,2022 Bernardo Bandos

pycomicvine is Copyright (c) Martin Lenders
