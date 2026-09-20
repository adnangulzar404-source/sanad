from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

SUPPORTED_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# "format" is required, not defaulted: this file is the provenance contract,
# and an implicit default is precisely how the wrong Tanzil export (txt-2,
# which prepends the Bismillah to ayah 1) got chosen without anyone noticing.
_REQUIRED = ("id", "kind", "format", "title", "url", "license_id",
             "content_sha256", "expected_lines", "modifications")
# Keep in sync with sanad_ingest.tanzil.parser_for, which maps each of
# these to a parser. Validated here too, not just there, so a typo like
# "xlm" fails at lockfile-load time with a message naming the source and
# the bad value -- as early as possible -- rather than surfacing later as
# parser_for's ValueError (kept as a belt-and-braces backstop) or, worse,
# being silently accepted by a naive dispatch that treats "anything but
# xml" as the pipe format.
_VALID_FORMATS = frozenset({"xml", "txt-2"})


class LockfileError(Exception):
    pass


@dataclass(frozen=True)
class LockedSource:
    id: str
    kind: str
    format: str
    title: str
    url: str
    license_id: str
    content_sha256: str
    expected_lines: int
    modifications: str
    publisher: str | None = None
    edition: str | None = None
    license_url: str | None = None


def load_lockfile(path: str | Path) -> list[LockedSource]:
    path = Path(path)
    if not path.is_file():
        raise LockfileError(f"lockfile not found: {path}")

    data = tomllib.loads(path.read_text(encoding="utf-8"))

    version = data.get("lockfile_version")
    if version != SUPPORTED_VERSION:
        raise LockfileError(
            f"unsupported lockfile version {version!r}; expected {SUPPORTED_VERSION}")

    out: list[LockedSource] = []
    for entry in data.get("source", []):
        missing = [f for f in _REQUIRED if f not in entry]
        if missing:
            raise LockfileError(
                f"source {entry.get('id', '<unnamed>')!r} missing: {', '.join(missing)}")
        if entry["format"] not in _VALID_FORMATS:
            raise LockfileError(
                f"source {entry['id']!r} has an unsupported format "
                f"{entry['format']!r}; expected one of {sorted(_VALID_FORMATS)}")
        if not _SHA256.match(entry["content_sha256"]):
            raise LockfileError(
                f"source {entry['id']!r} has a malformed sha256")
        out.append(LockedSource(**{k: entry.get(k) for k in
                                   list(_REQUIRED) + ["publisher", "edition", "license_url"]}))

    if not out:
        # A lockfile with zero [[source]] entries parses "successfully" and
        # would otherwise let `build_corpus` silently emit a valid-looking
        # but empty database -- the reproducibility contract this file is
        # supposed to enforce, defeated by an empty file passing validation.
        raise LockfileError(f"lockfile has no [[source]] entries: {path}")
    return out
