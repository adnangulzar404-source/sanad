from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from .build import BuildError, build_corpus
from .fetch import HashMismatch
from .lockfile import LockfileError
from .tanzil import TanzilParseError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sanad-ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="build the corpus database")
    b.add_argument("--lockfile", type=Path, default=Path("ingest/corpus.lock.toml"))
    b.add_argument("--out", type=Path, default=Path("data/sanad.db"))
    b.add_argument("--cache", type=Path, default=Path(".corpus-cache"))
    # Regenerated on every build so it cannot go stale against the corpus it
    # describes. It is a review artifact, not an input: nothing reads it back,
    # and no record is filtered on it. Deterministic, so a rebuild that leaves
    # it unchanged leaves the working tree clean.
    b.add_argument("--noise-report", type=Path,
                   default=Path("docs/hadith-noise-report.md"))
    b.add_argument("-v", "--verbose", action="store_true")

    e = sub.add_parser("embed", help="generate embeddings into the vectors sidecar DB")
    e.add_argument("--db", type=Path, default=Path("data/sanad-quran.db"))
    e.add_argument("--vectors", type=Path, default=Path("data/sanad-vectors.db"))
    e.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s")

    if args.command == "embed":
        from sanad.retrieve.voyage import resolve_voyage_key

        from .embed import run_embed
        key = resolve_voyage_key()
        if not key:
            print("error: VOYAGE_API_KEY is not set; embedding needs a Voyage key. "
                  "The rest of the corpus builds and serves without one.",
                  file=sys.stderr)
            return 1
        stats = run_embed(args.db, args.vectors, key=key)
        print(f"embedded {stats['embedded']}, skipped {stats['skipped']} "
              f"(total {stats['total']}) -> {args.vectors}")
        return 0

    try:
        stats = build_corpus(args.lockfile, args.out, args.cache,
                             noise_report=args.noise_report)
    except (LockfileError, HashMismatch, TanzilParseError, BuildError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(f"built {args.out}")
    print(f"  records      {stats['records']}")
    print(f"  sources      {stats['sources']}")
    print(f"  db sha256    {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
