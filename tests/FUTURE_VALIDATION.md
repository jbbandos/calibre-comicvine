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
