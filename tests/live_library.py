"""Library-based live validation runner (not a unittest; not discovered).

Samples books from a private library snapshot and runs the *installed* plugin's
identify against the real Comicvine API, twice per book (title only, and
title + authors). Results are appended to ``tests/private/results.jsonl`` so an
interrupted run resumes where it stopped.

Usage (plain python3, no calibre imports in this process):

    python3 tests/live_library.py [--pilot 40] [--no-id 5] [--seed 20240601]
                                  [--limit N] [--delay 1.0] [--timeout 180]
                                  [--retry-errors] [--dry-run]

Each query runs in a ``calibre-debug -e tests/live_library.py -- --worker``
subprocess that reads the query as JSON on stdin and prints one marker line
with a JSON result. The worker uses the API key already configured in the
installed plugin's preferences; the key is never read by this process and is
scrubbed from any error text before it is emitted.

All private data (snapshot, results) lives under ``tests/private/``, which is
git-ignored. Results hold calibre ids and Comicvine ids, never titles/authors.

Classifications, for books with a comicvine id (expected issue id):
    match           expected issue ranked first
    found-not-first expected issue returned, but not ranked first
    wrong-volume    expected not returned; top result is in another volume
    wrong-issue     expected not returned; top result is in the expected
                    volume (or the expected volume is unknown)
    no-result       nothing returned
    error           API/plugin error or timeout (recorded, not a mismatch)
Books without a comicvine id get ``unverified`` (top candidate recorded).
"""
import json
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PRIVATE = os.path.join(HERE, "private")
SNAPSHOT = os.path.join(PRIVATE, "library_snapshot.json")
RESULTS = os.path.join(PRIVATE, "results.jsonl")
MARKER = "LIVE_LIBRARY_RESULT "
MODES = ("title", "title+authors")
MAX_CANDIDATES = 25


# ---------------------------------------------------------------- worker side
def _worker():
    """Run one identify inside calibre-debug and print a marker JSON line."""
    query = json.loads(sys.stdin.read())
    out = {"error": None, "results": []}
    secret = ""
    try:
        from calibre.customize.ui import initialize_plugins

        initialize_plugins()
        from calibre.utils.logging import ThreadSafeLog
        from calibre_plugins.comicvine.config import PREFS
        from calibre_plugins.comicvine.source import Comicvine
        from queue import Queue

        secret = str(PREFS["api_key"] or "").strip()
        plugin = Comicvine(None)
        log = ThreadSafeLog()
        log.filter_level = log.ERROR
        log.outputs = []  # discard all log output
        queue = Queue()
        title = query["title"]
        authors = query.get("authors") or []
        plugin.identify(
            log, queue, False, title=title, authors=authors,
            identifiers={}, timeout=query.get("timeout", 30),
        )
        ranking = plugin.identify_results_keygen(title, authors, {})
        for meta in sorted(queue.queue, key=ranking)[:MAX_CANDIDATES]:
            out["results"].append(
                {
                    "issue": str(meta.identifiers.get("comicvine")),
                    "volume": meta.identifiers.get("comicvine-volume"),
                    "title": meta.title,
                }
            )
    except BaseException as exc:  # noqa: BLE001 - report everything
        text = f"{type(exc).__name__}: {exc}"
        if secret:
            text = text.replace(secret, "***REDACTED***")
        out["error"] = text[:300]
    print(MARKER + json.dumps(out))
    sys.stdout.flush()


# ---------------------------------------------------------------- runner side
def select_sample(books, pilot, no_id, seed):
    """Deterministic sample: ``pilot - no_id`` with an id plus ``no_id`` without."""
    rng = random.Random(seed)
    with_id = sorted((b for b in books if b.get("comicvine")), key=lambda b: b["calibre_id"])
    without = sorted((b for b in books if not b.get("comicvine")), key=lambda b: b["calibre_id"])
    n_with = max(pilot - no_id, 0)
    return rng.sample(with_id, min(n_with, len(with_id))) + rng.sample(
        without, min(no_id, len(without))
    )


def load_done(retry_errors):
    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if retry_errors and rec.get("classification") == "error":
                    continue
                done.add((rec["calibre_id"], rec["mode"]))
    return done


def classify(book, results, error):
    if error:
        return "error"
    if not book.get("comicvine"):
        return "unverified" if results else "no-result"
    if not results:
        return "no-result"
    expected = str(book["comicvine"])
    ids = [r["issue"] for r in results]
    if ids[0] == expected:
        return "match"
    if expected in ids:
        return "found-not-first"
    exp_vol = book.get("comicvine-volume")
    if exp_vol and str(results[0]["volume"]) != str(exp_vol):
        return "wrong-volume"
    return "wrong-issue"


def run_query(book, mode, timeout):
    payload = {
        "title": book["title"],
        "authors": book["authors"] if mode == "title+authors" else [],
        "timeout": 30,
    }
    try:
        proc = subprocess.run(
            ["calibre-debug", "-e", os.path.abspath(__file__), "--", "--worker"],
            input=json.dumps(payload),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return [], "timeout"
    for line in proc.stdout.splitlines():
        if line.startswith(MARKER):
            data = json.loads(line[len(MARKER):])
            return data["results"], data["error"]
    return [], f"no worker output (exit {proc.returncode})"


def record_for(book, mode, results, error):
    top = results[0] if results else None
    rec = {
        "calibre_id": book["calibre_id"],
        "mode": mode,
        "classification": classify(book, results, error),
        "expected_issue": book.get("comicvine"),
        "expected_volume": book.get("comicvine-volume"),
        "n_results": len(results),
        "returned_issue_ids": [r["issue"] for r in results],
        "top_issue": top["issue"] if top else None,
        "top_volume": top["volume"] if top else None,
        "top_title": top["title"] if top else None,
        "error": error,
        "ts": int(time.time()),
    }
    if book.get("comicvine"):
        ids = rec["returned_issue_ids"]
        expected = str(book["comicvine"])
        rec["expected_returned"] = expected in ids
        rec["expected_first"] = bool(ids) and ids[0] == expected
        rec["expected_rank"] = ids.index(expected) + 1 if expected in ids else None
    return rec


def main(argv):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pilot", type=int, default=40, help="total books (default 40)")
    ap.add_argument("--no-id", type=int, default=5, dest="no_id",
                    help="of those, books without a comicvine id (default 5)")
    ap.add_argument("--seed", type=int, default=20240601)
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after this many books (for smoke tests)")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between queries (plugin rate limiting also applies)")
    ap.add_argument("--timeout", type=int, default=180, help="per-query timeout (s)")
    ap.add_argument("--retry-errors", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the selection size and pending work only")
    args = ap.parse_args(argv)

    with open(SNAPSHOT, encoding="utf-8") as fh:
        books = json.load(fh)
    sample = select_sample(books, args.pilot, args.no_id, args.seed)
    if args.limit is not None:
        sample = sample[: args.limit]
    done = load_done(args.retry_errors)
    pending = [(b, m) for b in sample for m in MODES if (b["calibre_id"], m) not in done]
    print(f"sample={len(sample)} queries pending={len(pending)} done={len(done)}")
    if args.dry_run:
        return 0

    os.makedirs(PRIVATE, exist_ok=True)
    counts = {}
    for i, (book, mode) in enumerate(pending, 1):
        results, error = run_query(book, mode, args.timeout)
        rec = record_for(book, mode, results, error)
        with open(RESULTS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        counts[rec["classification"]] = counts.get(rec["classification"], 0) + 1
        print(f"[{i}/{len(pending)}] calibre_id={rec['calibre_id']} "
              f"{mode}: {rec['classification']}")
        if i < len(pending):
            time.sleep(args.delay)
    print("summary:", json.dumps(counts, sort_keys=True))
    return 0


if "--worker" in sys.argv[1:]:
    _worker()
elif __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
