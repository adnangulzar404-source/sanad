from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from .build import build_corpus
from .fetch import HashMismatch
from .lockfile import LockfileError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sanad-ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="build the corpus database")
    b.add_argument("--lockfile", type=Path, default=Path("ingest/corpus.lock.toml"))
    b.add_argument("--out", type=Path, default=Path("data/sanad.db"))
    b.add_argument("--cache", type=Path, default=Path(".corpus-cache"))
    b.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s")

    try:
        stats = build_corpus(args.lockfile, args.out, args.cache)
    except (LockfileError, HashMismatch) as exc:
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
