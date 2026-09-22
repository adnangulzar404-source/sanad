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
             "content_sha256", "modifications")
# Keep in sync with sanad_ingest.tanzil.parser_for, which maps each of
# these to a parser. Validated here too, not just there, so a typo like
# "xlm" fails at lockfile-load time with a message naming the source and
# the bad value -- as early as possible -- rather than surfacing later as
# parser_for's ValueError (kept as a belt-and-braces backstop) or, worse,
# being silently accepted by a naive dispatch that treats "anything but
# xml" as the pipe format.
_VALID_FORMATS = frozenset({"xml", "txt-2", "openiti-markdown"})
# Each format declares its own count field, and that field is REQUIRED for
# that format -- not simply optional across the board. An unchecked record/
# line count is exactly how a truncated download would pass silently, so
# "either field, if present" is not good enough: the field matching the
# source's own format must be present. Tanzil's verse-per-line exports
# (xml, txt-2) count in `expected_lines`; OpenITI's hadith-per-record
# markdown counts in `expected_records`, since "line" has no meaning there
# (a single hadith spans multiple raw lines via `~~` continuations).
_COUNT_FIELD_BY_FORMAT = {
    "xml": "expected_lines",
    "txt-2": "expected_lines",
    "openiti-markdown": "expected_records",
}


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
    modifications: str
    expected_lines: int | None = None
    expected_records: int | None = None
    commit: str | None = None
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
        count_field = _COUNT_FIELD_BY_FORMAT[entry["format"]]
        if count_field not in entry:
            raise LockfileError(
                f"source {entry['id']!r} has format {entry['format']!r}, "
                f"which requires {count_field!r}, but it is missing")
        if not _SHA256.match(entry["content_sha256"]):
            raise LockfileError(
                f"source {entry['id']!r} has a malformed sha256")
        out.append(LockedSource(**{k: entry.get(k) for k in
                                   list(_REQUIRED) +
                                   ["expected_lines", "expected_records", "commit",
                                    "publisher", "edition", "license_url"]}))

    if not out:
        # A lockfile with zero [[source]] entries parses "successfully" and
        # would otherwise let `build_corpus` silently emit a valid-looking
        # but empty database -- the reproducibility contract this file is
        # supposed to enforce, defeated by an empty file passing validation.
        raise LockfileError(f"lockfile has no [[source]] entries: {path}")
    return out
