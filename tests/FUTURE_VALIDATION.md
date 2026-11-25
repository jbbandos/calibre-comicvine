# Future validation cases

Cases recorded for validation when the search logic is reworked. Nothing here
is covered by an automated test yet, and the plugin has not been changed for it.

## Disney Masters: subtitle used as volume search terms

**Search (calibre):** title `Disney masters: The Case of the Vanishing Bandit`,
author `Paul Murry`.

**Expected:** Comicvine issue 675881
(https://comicvine.gamespot.com/disney-masters-3-walt-disneys-mickey-mouse-the-cas/4000-675881/),
title "Disney Masters #3: Walt Disney's Mickey Mouse: The Case of the Vanishing
Bandit", volume 110742 ("Disney Masters"), issue number 3, publisher
Fantagraphics. Creators include Paul Murry, Carl Fallberg, Erik Rosengarten,
Garry Leach and Susan Daigle-Leach.

**Observed (plugin 0.14.4, CLI `calibre-debug -r Comicvine -- -v ...`):** no result.

| Search | Volume found | Result |
|---|---|---|
| `Disney masters: The Case of the Vanishing Bandit` + `a:Paul Murry` | 41199 | none |
| `Disney Masters #3` + `a:Paul Murry` | 110742 | issue 675881 found |
| `Disney Masters` + `a:Paul Murry` | 110742 | 27 issues, includes 675881 |

**Cause:** with no `#N` in the title, `find_title` builds the volume query from
every token, including the issue subtitle:
`disney AND masters: AND case AND of AND vanishing AND bandit AND None`.
The subtitle belongs to the issue name, not the volume name, so the query
matches volume 41199 and the author filter then removes everything.
Related: the literal `AND None` (DEFECTS.md row 5) and the trailing colon kept
on the token `masters:`.

**Possible fix (not applied):**
1. With no issue number and no issue by the requested authors, search again
   using only the title text before the first `:` ("Disney Masters").
2. Keep the author filter and let `score_title` rank issues by the subtitle.
3. Strip trailing punctuation from tokens and leave `None` out of the query.
4. Add an offline test with Mock_Comicvine and a live test for this title,
   author, issue id 675881 and volume id 110742.

# Matching and naming improvements (from the library pilot)

Source: a 40-book pilot comparing calibre titles/series with Comicvine and
Goodreads (private data under `tests/private/`, git-ignored; scripts
`tests/live_library.py`, `tests/verify_stored_ids.py`, `tests/analyse_naming.py`).
No book titles or authors are recorded here. Nothing below is applied.

Order of work: fix GitHub issue #5 (cover download returns HTTP 403) first, then
implement items 6 and 7. Items 1-5 and 8 are stored for later evaluation.

## Findings that drive the changes

- Comicvine stores only the bare issue name. The plugin composes the title as
  `<volume> #<n>: <name>`. About 74% of pilot titles equal that composition.
- Some calibre titles hold only the issue name (no series words). In title mode
  none of those matched, because the volume search has no series tokens.
- Comicvine names differ from calibre/Goodreads only in case, accents, a leading
  article or a translated series name.
- Generic issue names (`TPB`, `HC`, `OGN`, `GN`, `Volume n`) carry no information
  and add words that do not appear in the volume name.

## Proposed change 6: case, accent and article-insensitive comparison

Where: `utils.py`, used by `normalised_title`, `score_title` and `keygen`.

```python
import unicodedata

_ARTICLES = ("the ", "a ", "an ")

def fold(text):
    """Casefold, strip accents and punctuation, drop a leading article."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s#]", " ", text.casefold())
    text = re.sub(r"\s+", " ", text).strip()
    for article in _ARTICLES:
        if text.startswith(article):
            return text[len(article):]
    return text
```

In `score_title`, compare folded strings:

```diff
-    volume = f"{metadata.series.lower()} #{metadata.series_index}"
+    volume = fold(f"{metadata.series} #{metadata.series_index}")
+    title = fold(title)
-    for token in title_tokens:
-        if token not in volume:
+    for token in map(fold, title_tokens):
+        if token not in volume:
```

Also:
- Apply `fold` to the tokens in `normalised_title` before they are joined into
  the Comicvine query, so accented titles still match.
- Ignore YYYYMM-style indexes (six digits) when testing whether the series index
  appears in the title, since Comicvine and calibre use different conventions.
- This function also contains defects 6a-6c in `tests/DEFECTS.md` (title=None
  crash, Levenshtein inside the token loop, numeric `series_index` in a string
  test). Fix them in the same change, and turn their expected-failure tests into
  normal tests.

Tests to add (offline, no network):
- `fold("Un certain Monsieur Kô") == fold("un certain monsieur ko")`.
- A leading "The" is ignored on both sides.
- `score_title` gives the same score for accented and unaccented variants.
- Existing `tests/test_score_title.py` and `tests/test_normalised_title.py` still pass.

Risk: folding the query can widen the match set. Compare ranking results on the
pilot before and after.

## Proposed change 7: generic issue names treated as empty

Decision (user): generic names are dropped in `build_meta`, so new downloads no
longer carry `: HC`, `: OGN` and similar. Books that already have a `comicvine`
identifier are matched by that id: `Comicvine.identify` already looks the issue
up directly and returns, so the title is not used to match them. The new
metadata is then offered by calibre as an update of the stored title. Matching
code is not changed for item 7. The two options considered were:

- Matching only: ignore generic names when scoring and when
  forming the volume query. `build_meta` keeps producing the same title, so
  titles already stored in calibre keep matching.
- Also in `build_meta` (chosen): new downloads drop `: HC`, `: OGN` and similar,
  which changes titles for users who already have them.

Where: `utils.py`, new helper next to `normalised_title`.

```python
_GENERIC_NAME = re.compile(
    r"^(?:tpb|hc|sc|gn|ogn|hardcover|softcover|graphic novel|"
    r"vol(?:ume)?\.?\s*\d+|book\s*\d+)$",
    re.IGNORECASE,
)

def is_generic_issue_name(name, issue_number=None):
    """True for names such as TPB, HC, OGN or 'Volume 2'."""
    name = (name or "").strip()
    if not name:
        return True
    match = _GENERIC_NAME.match(name)
    if not match:
        return False
    number = re.search(r"\d+", name)
    # 'Volume 2' is only generic when it repeats the issue number.
    return number is None or issue_number is None or number.group() == str(issue_number)
```

Use it in `score_title` (strip a generic name from the compared text) and when
dropping trailing sub-title tokens from the volume query.

Tests to add:
- `TPB`, `HC`, `OGN`, `GN`, empty and `None` are generic.
- `Volume 2` is generic for issue 2 and not generic for issue 5.
- A real name such as "The Gold Eater" is not generic.
- `build_meta` output is unchanged (guard test) unless the decision above says otherwise.

## Stored for later evaluation (not scheduled)

1. Use calibre series and series index as the primary volume and issue query.
   calibre's identify API passes only title, authors and identifiers, so this
   needs a workaround (for example parsing a `series #n` pattern from the title).
2. Prefer the stored `comicvine-volume` identifier when present. In the pilot,
   18 of 19 stored id pairs were consistent, and the title queries did not use them.
3. Remove the sub-title after `#n:` from the volume query and use it only to score
   issue names (the sub-title words are currently ANDed into the volume search).
4. Penalise collected-edition volumes and prefer volumes with more issues; break
   ties between same-named volumes by publisher or year. `max_volumes` defaults
   to 2 and may cut the right volume.
5. Accept issue #1 when a one-issue volume's name equals the full title, or when
   the issue name contains the calibre series.
8. Use Goodreads only as an optional series and index cross-check. It never
   carries `#n`, uses its own title style, and 6 of 16 series differed.

## Validation recipe (re-run after each change)

All of these need the Comicvine API and the private snapshot, and are throttled
by Comicvine, so run them on separate days:

1. `COMICVINE_LIVE=1 calibre-debug -e tests/run_tests.py` (offline suite plus live smoke tests).
2. `python3 tests/live_library.py` (pilot queries; compare the classification
   counts in `tests/private/discrepancies.md` before and after).
3. `python3 tests/analyse_naming.py --report-only` to rebuild the naming report.
