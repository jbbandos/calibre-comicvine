"""Stored-id verification runner (not a unittest; not discovered).

For books whose pilot identify result (``tests/private/results.jsonl``) was a
non-match, look up the *stored* comicvine issue id (and comicvine-volume id)
directly on the Comicvine API and compare what Comicvine holds with the calibre
title/authors. This tells us whether calibre's stored ids are right (the plugin
returned the wrong thing) or wrong (the ids point at a different book).

Usage (plain python3, no calibre imports in this process):

    python3 tests/verify_stored_ids.py [--include-errors] [--delay 3.0]
                                       [--max-420 3] [--timeout 60]
                                       [--limit N] [--dry-run] [--report-only]

Each lookup runs in a ``calibre-debug -e tests/verify_stored_ids.py -- --worker``
subprocess (using the installed plugin's pycomicvine and its configured API key;
the key is never read here, printed, or written, and is scrubbed from errors).

Classifications:
    stored-ids-consistent             stored ids match the calibre book
    stored-ids-mismatch               stored ids point at a different book
    stored-issue-not-in-stored-volume stored issue belongs to another volume
    lookup-error                      lookup failed (incl. HTTP 420); retried
                                      on the next run

Private data only: ``tests/private/verify_results.jsonl`` and
``tests/private/verification.md`` (git-ignored; they may hold titles/authors).
"""
import difflib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
PRIVATE = os.path.join(HERE, "private")
SNAPSHOT = os.path.join(PRIVATE, "library_snapshot.json")
RESULTS = os.path.join(PRIVATE, "results.jsonl")
VERIFY_RESULTS = os.path.join(PRIVATE, "verify_results.jsonl")
REPORT = os.path.join(PRIVATE, "verification.md")
MARKER = "VERIFY_STORED_IDS_RESULT "

NON_MATCH = ("wrong-volume", "wrong-issue", "found-not-first", "no-result")
CLASSES = (
    "stored-ids-consistent",
    "stored-ids-mismatch",
    "stored-issue-not-in-stored-volume",
    "lookup-error",
)
ISSUE_TYPE_ID = 4000
VOLUME_TYPE_ID = 4050
ISSUE_FIELDS = ["id", "name", "issue_number", "volume", "person_credits",
                "cover_date", "store_date"]
VOLUME_FIELDS = ["id", "name", "publisher", "start_year", "count_of_issues"]
TITLE_THRESHOLD = 0.6        # similarity alone is enough
TITLE_WEAK_THRESHOLD = 0.4   # enough when at least one author overlaps


# ---------------------------------------------------------------- worker side
def _worker():
    """Look up one issue and volume inside calibre-debug; print a marker line."""
    query = json.loads(sys.stdin.read())
    out = {"error": None, "http_status": None, "issue": None, "volume": None}
    secret = ""
    stage = "issue"
    try:
        from calibre.customize.ui import initialize_plugins

        initialize_plugins()
        from calibre_plugins.comicvine import pycomicvine
        from calibre_plugins.comicvine.config import PREFS

        secret = str(PREFS["api_key"] or "").strip()
        pycomicvine.api_key = secret
        timeout = query.get("timeout", 60)

        def fetch(cls, type_id, rid, fields):
            cls._ensure_resource_url()
            url = "%s%d-%d/" % (cls._resource_url, type_id, int(rid))
            resp = cls._request(url, field_list=fields, timeout=timeout)
            return resp.results

        raw = fetch(pycomicvine.Issue, ISSUE_TYPE_ID, query["issue"], ISSUE_FIELDS)
        vol = raw.get("volume") or {}
        credits = raw.get("person_credits") or []
        out["issue"] = {
            "id": raw.get("id"),
            "name": raw.get("name"),
            "issue_number": raw.get("issue_number"),
            "volume_id": vol.get("id"),
            "volume_name": vol.get("name"),
            "people": [p.get("name") for p in credits if p.get("name")],
            "cover_date": raw.get("cover_date"),
            "store_date": raw.get("store_date"),
        }
        stage = "volume"
        vol_id = query.get("volume") or out["issue"]["volume_id"]
        if vol_id:
            time.sleep(query.get("pause", 1.0))
            v = fetch(pycomicvine.Volume, VOLUME_TYPE_ID, vol_id, VOLUME_FIELDS)
            pub = v.get("publisher") or {}
            out["volume"] = {
                "id": v.get("id"),
                "name": v.get("name"),
                "publisher": pub.get("name") if isinstance(pub, dict) else None,
                "start_year": v.get("start_year"),
                "count_of_issues": v.get("count_of_issues"),
            }
    except BaseException as exc:  # noqa: BLE001 - report everything
        out["http_status"] = getattr(exc, "code", None)
        text = f"{stage}: {type(exc).__name__}: {exc}"
        if secret:
            text = text.replace(secret, "***REDACTED***")
        out["error"] = text[:300]
    print(MARKER + json.dumps(out))
    sys.stdout.flush()


# ------------------------------------------------------- pure comparison logic
def normalise(text):
    """Lowercase, strip accents/punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def title_similarity(calibre_title, cv_texts):
    """Best similarity (0..1) between the calibre title and any CV text."""
    a = normalise(calibre_title)
    best = 0.0
    for text in cv_texts:
        b = normalise(text)
        if not a or not b:
            continue
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        ta, tb = set(a.split()), set(b.split())
        jaccard = len(ta & tb) / len(ta | tb)
        best = max(best, ratio, jaccard)
    return round(best, 3)


def cv_title_forms(issue_name, issue_number, volume_name):
    """Candidate renderings of the Comicvine title for comparison."""
    forms = []
    num = "" if issue_number in (None, "") else "#%s" % issue_number
    if volume_name:
        forms.append(f"{volume_name} {num}".strip())
        if issue_name:
            forms.append(f"{volume_name} {num} {issue_name}".strip())
            forms.append(f"{volume_name} {issue_name}")
    if issue_name:
        forms.append(str(issue_name))
    return forms


def author_overlap(calibre_authors, cv_people):
    """Fraction (0..1) of calibre authors present in the CV credits, plus count."""
    mine = {normalise(a) for a in (calibre_authors or [])}
    mine.discard("")
    mine.discard("unknown")
    theirs = {normalise(p) for p in (cv_people or [])}
    if not mine:
        return 0.0, 0
    hit = len(mine & theirs)
    return round(hit / len(mine), 3), hit


def classify(book, issue, volume, error):
    """Return (classification, details dict). Pure; no I/O."""
    if error and str(error).startswith("issue: ObjectNotFoundError"):
        # The stored issue id does not exist on Comicvine: the id is wrong.
        return "stored-ids-mismatch", {"note": "stored issue id not found"}
    if error or not issue:
        return "lookup-error", {}
    stored_vol = book.get("comicvine-volume")
    actual_vol = issue.get("volume_id")
    if stored_vol and actual_vol is not None and str(stored_vol) != str(actual_vol):
        return "stored-issue-not-in-stored-volume", {}
    vol_name = (volume or {}).get("name") or issue.get("volume_name")
    forms = cv_title_forms(issue.get("name"), issue.get("issue_number"), vol_name)
    sim = title_similarity(book.get("title"), forms)
    frac, hits = author_overlap(book.get("authors"), issue.get("people"))
    details = {"title_similarity": sim, "author_overlap": frac, "authors_matched": hits}
    if sim >= TITLE_THRESHOLD or (hits > 0 and sim >= TITLE_WEAK_THRESHOLD):
        return "stored-ids-consistent", details
    return "stored-ids-mismatch", details


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


def select_books(books, pilot_records, include_errors=False):
    """Books with a stored issue id and at least one non-match pilot result.

    Returns a list sorted by calibre_id; each item is the snapshot book plus a
    ``pilot`` dict mapping mode -> classification.
    """
    wanted = set(NON_MATCH) | ({"error"} if include_errors else set())
    pilot = {}
    for rec in pilot_records:
        pilot.setdefault(rec["calibre_id"], {})[rec["mode"]] = rec["classification"]
    by_id = {b["calibre_id"]: b for b in books}
    out = []
    for cid in sorted(pilot):
        book = by_id.get(cid)
        if not book or not book.get("comicvine"):
            continue
        if wanted & set(pilot[cid].values()):
            out.append(dict(book, pilot=pilot[cid]))
    return out


def latest_records(records):
    """Last record per calibre_id."""
    latest = {}
    for rec in records:
        latest[rec["calibre_id"]] = rec
    return latest


def pending_books(selected, records):
    """Selected books not yet classified (lookup-error counts as pending)."""
    done = {cid for cid, r in latest_records(records).items()
            if r.get("classification") != "lookup-error"}
    return [b for b in selected if b["calibre_id"] not in done]


def run_lookup(book, delay, timeout):
    payload = {
        "issue": book["comicvine"],
        "volume": book.get("comicvine-volume"),
        "timeout": timeout,
        "pause": delay,
    }
    try:
        proc = subprocess.run(
            ["calibre-debug", "-e", os.path.abspath(__file__), "--", "--worker"],
            input=json.dumps(payload),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout * 3 + 60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "http_status": None, "issue": None, "volume": None}
    for line in proc.stdout.splitlines():
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    return {"error": f"no worker output (exit {proc.returncode})",
            "http_status": None, "issue": None, "volume": None}


def record_for(book, data):
    cls, details = classify(book, data["issue"], data["volume"], data["error"])
    rec = {
        "calibre_id": book["calibre_id"],
        "classification": cls,
        "pilot": book.get("pilot"),
        "stored_issue": book.get("comicvine"),
        "stored_volume": book.get("comicvine-volume"),
        "calibre_title": book.get("title"),
        "calibre_authors": book.get("authors"),
        "cv_issue": data["issue"],
        "cv_volume": data["volume"],
        "http_status": data["http_status"],
        "error": data["error"],
        "ts": int(time.time()),
    }
    rec.update(details)
    return rec


def write_report(records, path=REPORT):
    latest = latest_records(records)
    counts = {c: 0 for c in CLASSES}
    for rec in latest.values():
        counts[rec["classification"]] = counts.get(rec["classification"], 0) + 1
    lines = ["# Stored-id verification (private, git-ignored)", "", "## Summary", ""]
    lines += [f"- {c}: {counts[c]}" for c in counts]
    lines += [f"- total: {len(latest)}", "", "## Books", ""]
    for cid in sorted(latest):
        r = latest[cid]
        issue = r.get("cv_issue") or {}
        vol = r.get("cv_volume") or {}
        lines += [
            f"### calibre id {cid}: {r['classification']}",
            "",
            f"- pilot results: {r.get('pilot')}",
            f"- stored ids: issue {r.get('stored_issue')}, volume {r.get('stored_volume')}",
            f"- calibre: {r.get('calibre_title')!r} by {r.get('calibre_authors')}",
            f"- comicvine issue: volume {issue.get('volume_name')!r} "
            f"(id {issue.get('volume_id')}) #{issue.get('issue_number')} "
            f"{issue.get('name')!r}, cover {issue.get('cover_date')}, "
            f"store {issue.get('store_date')}",
            f"- comicvine people: {issue.get('people')}",
            f"- comicvine volume: {vol.get('name')!r}, publisher {vol.get('publisher')}, "
            f"start {vol.get('start_year')}, issues {vol.get('count_of_issues')}",
            f"- title similarity: {r.get('title_similarity')}, "
            f"author overlap: {r.get('author_overlap')}",
        ]
        if r.get("error"):
            lines.append(f"- error: {r['error']} (http {r.get('http_status')})")
        lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return counts


def main(argv):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--include-errors", action="store_true",
                    help="also verify books whose pilot result was 'error'")
    ap.add_argument("--delay", type=float, default=3.0,
                    help="seconds between lookups (default 3.0)")
    ap.add_argument("--max-420", type=int, default=3, dest="max_420",
                    help="stop after N consecutive HTTP 420 responses (default 3)")
    ap.add_argument("--timeout", type=int, default=60, help="per-request timeout (s)")
    ap.add_argument("--limit", type=int, default=None, help="verify at most N books")
    ap.add_argument("--dry-run", action="store_true",
                    help="list calibre ids and stored ids only; no API call")
    ap.add_argument("--report-only", action="store_true",
                    help="regenerate tests/private/verification.md and exit")
    args = ap.parse_args(argv)

    records = read_jsonl(VERIFY_RESULTS)
    if args.report_only:
        print("summary:", json.dumps(write_report(records), sort_keys=True))
        return 0

    with open(SNAPSHOT, encoding="utf-8") as fh:
        books = json.load(fh)
    selected = select_books(books, read_jsonl(RESULTS), args.include_errors)
    pending = pending_books(selected, records)
    if args.limit is not None:
        pending = pending[: args.limit]
    print(f"selected={len(selected)} pending={len(pending)} "
          f"done={len(selected) - len(pending_books(selected, records))}")
    if args.dry_run:
        for b in pending:
            print(f"calibre_id={b['calibre_id']} issue={b['comicvine']} "
                  f"volume={b.get('comicvine-volume')} pilot={b['pilot']}")
        return 0

    os.makedirs(PRIVATE, exist_ok=True)
    consecutive_420 = 0
    stopped = False
    for i, book in enumerate(pending, 1):
        data = run_lookup(book, min(args.delay, 5.0), args.timeout)
        rec = record_for(book, data)
        with open(VERIFY_RESULTS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        records.append(rec)
        print(f"[{i}/{len(pending)}] calibre_id={rec['calibre_id']}: "
              f"{rec['classification']}")
        consecutive_420 = consecutive_420 + 1 if rec["http_status"] == 420 else 0
        if args.max_420 and consecutive_420 >= args.max_420:
            print(f"Stopping: {consecutive_420} consecutive HTTP 420 (throttled) "
                  "responses. Retry later; lookup-error books are retried "
                  "automatically on the next run.")
            stopped = True
            break
        if i < len(pending):
            time.sleep(args.delay)
    counts = write_report(records)
    print("summary:", json.dumps(counts, sort_keys=True))
    print(f"report: {os.path.relpath(REPORT)}")
    return 1 if stopped else 0


if "--worker" in sys.argv[1:]:
    _worker()
elif __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
