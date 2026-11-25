"""Naming analysis runner: calibre vs Comicvine vs Goodreads (not a unittest).

For the pilot sample (same deterministic selection as ``live_library.py``)
this fetches, per book, what Comicvine holds for the *stored* issue id and what
the installed ``Goodreads`` metadata source returns, caches the raw answers,
and derives comparisons against the calibre title / series / series_index.

Usage (plain python3, no calibre imports in this process):

    python3 tests/analyse_naming.py [--pilot 40] [--no-id 5] [--seed 20240601]
                                    [--limit N] [--delay 3.0] [--max-420 3]
                                    [--timeout 60] [--source both|comicvine|goodreads]
                                    [--dry-run] [--report-only]

Comicvine: existing ``tests/private/verify_results.jsonl`` records (from
``verify_stored_ids.py``) are reused; only missing ones are queried, through
that script's worker (``calibre-debug -e verify_stored_ids.py -- --worker``;
the API key stays inside the worker and is never read, printed or written
here). After ``--max-420`` consecutive HTTP 420 responses the run stops; rerun
later to resume.

Goodreads: the plugin named ``Goodreads`` (installed in calibre) is called
through ``calibre-debug -e tests/analyse_naming.py -- --worker`` with
``identifiers={'goodreads': id}`` (or ``{'isbn': isbn}`` when there is no
Goodreads id). One call per book, conservative delay, timeout, no retry loops;
errors are recorded and retried on the next run.

calibre series / series_index and the goodreads / isbn identifiers are read
read-only from the library ``metadata.db`` (``mode=ro&immutable=1``). Override
the path with ``--db``.

Outputs (git-ignored, they hold titles): ``tests/private/naming_results.jsonl``
(raw cache, one record per book and source, appended) and
``tests/private/naming_derived.jsonl`` (comparisons, rewritten by each run).

Comparison classes
    title vs Comicvine   composed-exact, composed-normalised,
                         title-equals-issue-name, title-has-series-prefix,
                         differs, no-comicvine-data
    series vs volume     exact, normalised, volume-per-issue, differs,
                         no-calibre-series, no-comicvine-data
    index vs number      equal, differs, no-calibre-index, no-comicvine-data
    Goodreads            title: exact, normalised, title-has-series-prefix,
                         differs; series/index as above
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
PRIVATE = os.path.join(HERE, "private")
SNAPSHOT = os.path.join(PRIVATE, "library_snapshot.json")
NAMING_RESULTS = os.path.join(PRIVATE, "naming_results.jsonl")
NAMING_DERIVED = os.path.join(PRIVATE, "naming_derived.jsonl")
VERIFY_RESULTS = os.path.join(PRIVATE, "verify_results.jsonl")
DEFAULT_DB = "/media/calibre/Biblioteca/metadata.db"
MARKER = "ANALYSE_NAMING_GR_RESULT "
GOODREADS_PLUGIN = "Goodreads"


# ---------------------------------------------------------------- worker side
def _worker():
    """Run one Goodreads identify inside calibre-debug; print a marker line."""
    query = json.loads(sys.stdin.read())
    out = {"error": None, "results": []}
    try:
        from queue import Queue
        from threading import Event

        from calibre.customize.ui import initialize_plugins, metadata_plugins
        from calibre.utils.logging import ThreadSafeLog

        initialize_plugins()
        plugin = None
        for p in metadata_plugins(["identify"]):
            if p.name == GOODREADS_PLUGIN:
                plugin = p
                break
        if plugin is None:
            raise RuntimeError("metadata source %r not found" % GOODREADS_PLUGIN)
        log = ThreadSafeLog()
        log.filter_level = log.ERROR
        log.outputs = []
        queue = Queue()
        plugin.identify(
            log, queue, Event(), title=None, authors=None,
            identifiers=query["identifiers"], timeout=query.get("timeout", 60),
        )
        for meta in list(queue.queue)[:3]:
            out["results"].append({
                "title": meta.title,
                "authors": list(meta.authors or []),
                "series": meta.series,
                "series_index": meta.series_index,
                "identifiers": dict(meta.identifiers or {}),
            })
    except BaseException as exc:  # noqa: BLE001 - report everything
        out["error"] = ("%s: %s" % (type(exc).__name__, exc))[:300]
    print(MARKER + json.dumps(out))
    sys.stdout.flush()


# ------------------------------------------------------- pure comparison logic
def normalise(text):
    from verify_stored_ids import normalise as _n
    return _n(text)


def _num(value):
    """Parse an issue number / series index to float, or None."""
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        m = re.match(r"\s*(\d+(?:\.\d+)?)", str(value))
        return float(m.group(1)) if m else None


def compose_cv_title(volume_name, issue_number, issue_name):
    """Title as the plugin's ``build_meta`` composes it (see utils.py)."""
    title = f"{volume_name} #{issue_number}"
    if issue_name:
        title += f": {issue_name}"
    return title


def compare_title(cal_title, composed, issue_name, series):
    """Classify the calibre title against the Comicvine composed title."""
    if not composed:
        return "no-comicvine-data"
    if cal_title == composed:
        return "composed-exact"
    nt = normalise(cal_title)
    if nt == normalise(composed):
        return "composed-normalised"
    if issue_name and nt == normalise(issue_name):
        return "title-equals-issue-name"
    ns = normalise(series)
    if ns and (nt == ns or nt.startswith(ns + " ")):
        return "title-has-series-prefix"
    return "differs"


def compare_series(cal_series, remote_series, issue_name=None, count=None):
    """Classify the calibre series against a Comicvine volume / GR series."""
    if remote_series in (None, ""):
        return "no-comicvine-data"
    if not cal_series:
        return "no-calibre-series"
    if cal_series == remote_series:
        return "exact"
    nr = normalise(remote_series)
    if normalise(cal_series) == nr:
        return "normalised"
    if count == 1 or (issue_name and normalise(issue_name) == nr):
        return "volume-per-issue"
    return "differs"


def compare_index(cal_index, remote_number):
    if remote_number in (None, ""):
        return "no-comicvine-data"
    if cal_index in (None, ""):
        return "no-calibre-index"
    a, b = _num(cal_index), _num(remote_number)
    if a is None or b is None:
        return "equal" if str(cal_index) == str(remote_number) else "differs"
    return "equal" if a == b else "differs"


def compare_goodreads_title(cal_title, gr_title, gr_series):
    if not gr_title:
        return "no-comicvine-data"
    if cal_title == gr_title:
        return "exact"
    nt = normalise(cal_title)
    if nt == normalise(gr_title):
        return "normalised"
    ns = normalise(gr_series)
    if ns and (nt == ns or nt.startswith(ns + " ")):
        return "title-has-series-prefix"
    return "differs"


def derive(book, cv, gr):
    """Comparison record for one book. ``cv``/``gr`` are cache records or None."""
    out = {
        "calibre_id": book["calibre_id"],
        "calibre_title": book.get("title"),
        "calibre_series": book.get("series"),
        "calibre_series_index": book.get("series_index"),
    }
    issue = (cv or {}).get("issue") or {}
    vol = (cv or {}).get("volume") or {}
    if issue:
        vname = vol.get("name") or issue.get("volume_name")
        composed = compose_cv_title(vname, issue.get("issue_number"), issue.get("name"))
        out["cv_composed_title"] = composed
        out["cv_issue_name"] = issue.get("name")
        out["cv_volume_name"] = vname
        out["cv_issue_number"] = issue.get("issue_number")
        out["cv_title"] = compare_title(book.get("title"), composed,
                                        issue.get("name"), vname)
        out["cv_series"] = compare_series(book.get("series"), vname,
                                          issue.get("name"),
                                          vol.get("count_of_issues"))
        out["cv_index"] = compare_index(book.get("series_index"),
                                        issue.get("issue_number"))
    result = ((gr or {}).get("results") or [None])[0]
    if result:
        out["gr_title_text"] = result.get("title")
        out["gr_series_text"] = result.get("series")
        out["gr_series_index_text"] = result.get("series_index")
        out["gr_title"] = compare_goodreads_title(book.get("title"),
                                                  result.get("title"),
                                                  result.get("series"))
        out["gr_series"] = compare_series(book.get("series"), result.get("series"))
        out["gr_index"] = compare_index(book.get("series_index"),
                                        result.get("series_index"))
    return out


# ---------------------------------------------------------------- runner side
def read_jsonl(path):
    recs = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    continue
    return recs


def read_calibre_fields(db_path, ids):
    """series, series_index, goodreads, isbn per book id; read-only access."""
    uri = "file:%s?mode=ro&immutable=1" % db_path
    con = sqlite3.connect(uri, uri=True)
    try:
        info = {}
        for cid in ids:
            row = con.execute(
                "SELECT b.series_index, s.name FROM books b "
                "LEFT JOIN books_series_link l ON l.book = b.id "
                "LEFT JOIN series s ON s.id = l.series WHERE b.id = ?", (cid,)
            ).fetchone()
            d = {"series": None, "series_index": None, "goodreads": None, "isbn": None}
            if row:
                d["series_index"], d["series"] = row
            for typ, val in con.execute(
                "SELECT type, val FROM identifiers WHERE book = ? "
                "AND type IN ('goodreads', 'isbn')", (cid,)
            ):
                d[typ] = val
            info[cid] = d
        return info
    finally:
        con.close()


def latest(records, source):
    out = {}
    for r in records:
        if r.get("source") == source:
            out[r["calibre_id"]] = r
    return out


def is_error(rec):
    return bool(rec.get("error"))


def pending_for(source, books, cache, verify):
    """Books still needing a query for ``source``."""
    done = latest(cache, source)
    todo = []
    for b in books:
        if source == "comicvine":
            if not b.get("comicvine"):
                continue
            v = verify.get(b["calibre_id"])
            if v and v.get("classification") != "lookup-error" and v.get("cv_issue"):
                continue  # reusable verify record
        else:
            if not (b.get("goodreads") or b.get("isbn")):
                continue
        rec = done.get(b["calibre_id"])
        if rec and not is_error(rec):
            continue
        todo.append(b)
    return todo


def comicvine_record(book, verify, cache):
    """Best Comicvine data for a book: fresh cache record, else verify record."""
    rec = latest(cache, "comicvine").get(book["calibre_id"])
    if rec and not is_error(rec):
        return rec
    v = verify.get(book["calibre_id"])
    if v and v.get("cv_issue"):
        return {"issue": v["cv_issue"], "volume": v.get("cv_volume"),
                "source": "verify-cache"}
    return None


def run_goodreads(book, timeout):
    ids = ({"goodreads": str(book["goodreads"])} if book.get("goodreads")
           else {"isbn": str(book["isbn"])})
    try:
        proc = subprocess.run(
            ["calibre-debug", "-e", os.path.abspath(__file__), "--", "--worker"],
            input=json.dumps({"identifiers": ids, "timeout": timeout}),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=timeout * 2 + 60, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "results": []}
    for line in proc.stdout.splitlines():
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    return {"error": "no worker output (exit %s)" % proc.returncode, "results": []}


def append(rec):
    os.makedirs(PRIVATE, exist_ok=True)
    with open(NAMING_RESULTS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def write_derived(books, cache, verify):
    cv_cache = latest(cache, "comicvine")
    gr_cache = latest(cache, "goodreads")
    rows = []
    for b in books:
        cv = comicvine_record(b, verify, cache) if b.get("comicvine") else None
        gr = gr_cache.get(b["calibre_id"])
        if gr and is_error(gr):
            gr = None
        rows.append(derive(b, cv, gr))
    os.makedirs(PRIVATE, exist_ok=True)
    with open(NAMING_DERIVED, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    counts = {}
    for r in rows:
        for key in ("cv_title", "cv_series", "cv_index",
                    "gr_title", "gr_series", "gr_index"):
            if key in r:
                k = "%s=%s" % (key, r[key])
                counts[k] = counts.get(k, 0) + 1
    del cv_cache
    return counts


def main(argv):
    import argparse
    import live_library
    import verify_stored_ids

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pilot", type=int, default=40)
    ap.add_argument("--no-id", type=int, default=5, dest="no_id")
    ap.add_argument("--seed", type=int, default=20240601)
    ap.add_argument("--limit", type=int, default=None,
                    help="query at most N books per source")
    ap.add_argument("--delay", type=float, default=3.0,
                    help="seconds between queries (default 3.0)")
    ap.add_argument("--max-420", type=int, default=3, dest="max_420")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--source", choices=("both", "comicvine", "goodreads"),
                    default="both")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true",
                    help="list pending queries only; no API call, no key access")
    ap.add_argument("--report-only", action="store_true",
                    help="rewrite naming_derived.jsonl from cached data and exit")
    args = ap.parse_args(argv)

    with open(SNAPSHOT, encoding="utf-8") as fh:
        snapshot = json.load(fh)
    sample = live_library.select_sample(snapshot, args.pilot, args.no_id, args.seed)
    fields = read_calibre_fields(args.db, [b["calibre_id"] for b in sample])
    books = [dict(b, **fields[b["calibre_id"]]) for b in sample]
    cache = read_jsonl(NAMING_RESULTS)
    verify = verify_stored_ids.latest_records(read_jsonl(VERIFY_RESULTS))

    if args.report_only:
        print("summary:", json.dumps(write_derived(books, cache, verify),
                                     sort_keys=True))
        return 0

    sources = ("comicvine", "goodreads") if args.source == "both" else (args.source,)
    work = {}
    for s in sources:
        work[s] = pending_for(s, books, cache, verify)
        if args.limit is not None:
            work[s] = work[s][: args.limit]
    print("sample=%d " % len(books) + " ".join(
        "%s pending=%d" % (s, len(work[s])) for s in sources))
    if args.dry_run:
        for s in sources:
            for b in work[s]:
                ident = (("issue=%s volume=%s" % (b["comicvine"], b.get("comicvine-volume")))
                         if s == "comicvine" else
                         ("goodreads=%s" % b["goodreads"] if b.get("goodreads")
                          else "isbn=%s" % b["isbn"]))
                print("%s calibre_id=%s %s" % (s, b["calibre_id"], ident))
        return 0

    stopped = False
    consecutive_420 = 0
    for i, b in enumerate(work.get("comicvine", []), 1):
        data = verify_stored_ids.run_lookup(b, min(args.delay, 5.0), args.timeout)
        rec = {"calibre_id": b["calibre_id"], "source": "comicvine",
               "issue": data["issue"], "volume": data["volume"],
               "http_status": data["http_status"], "error": data["error"],
               "ts": int(time.time())}
        append(rec)
        cache.append(rec)
        print("[comicvine %d/%d] calibre_id=%s: %s" % (
            i, len(work["comicvine"]), b["calibre_id"],
            "error" if rec["error"] else "ok"))
        consecutive_420 = consecutive_420 + 1 if rec["http_status"] == 420 else 0
        if args.max_420 and consecutive_420 >= args.max_420:
            print("Stopping: %d consecutive HTTP 420 (throttled) responses. "
                  "Rerun later to resume; errored books are retried." % consecutive_420)
            stopped = True
            break
        if i < len(work["comicvine"]):
            time.sleep(args.delay)

    consecutive_fail = 0
    for i, b in enumerate(work.get("goodreads", []) if not stopped else [], 1):
        data = run_goodreads(b, args.timeout)
        rec = {"calibre_id": b["calibre_id"], "source": "goodreads",
               "query": "goodreads" if b.get("goodreads") else "isbn",
               "results": data["results"], "error": data["error"],
               "ts": int(time.time())}
        append(rec)
        cache.append(rec)
        print("[goodreads %d/%d] calibre_id=%s: %s" % (
            i, len(work["goodreads"]), b["calibre_id"],
            "error" if rec["error"] else ("ok" if rec["results"] else "no-result")))
        consecutive_fail = consecutive_fail + 1 if rec["error"] else 0
        if args.max_420 and consecutive_fail >= args.max_420:
            print("Stopping: %d consecutive Goodreads errors. Rerun later to "
                  "resume." % consecutive_fail)
            stopped = True
            break
        if i < len(work["goodreads"]):
            time.sleep(max(args.delay, 3.0))

    print("summary:", json.dumps(write_derived(books, cache, verify), sort_keys=True))
    return 1 if stopped else 0


if "--worker" in sys.argv[1:]:
    _worker()
elif __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
