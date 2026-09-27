from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from pathlib import Path

from sanad.corpus import db
from sanad.corpus.models import Record, Source
from sanad.corpus.schema import SOURCE_SCHEMA_SQL
from sanad.corpus.surahs import surah_name

from .audit_lists import NEVER_CUT, UNSCORABLE
from .fetch import fetch_source
from .lockfile import LockedSource, load_lockfile
from .openiti import ParsedOpeniti
from .tanzil import ParsedTanzil, ParsedTanzilXml, parser_for

log = logging.getLogger(__name__)

_Parsed = ParsedTanzil | ParsedTanzilXml | ParsedOpeniti


class BuildError(Exception):
    pass


def _register_source(conn: sqlite3.Connection, locked: LockedSource,
                     parsed: _Parsed, today: str) -> None:
    db.insert_source(conn, Source(
        id=locked.id, kind=locked.kind, title=locked.title,
        publisher=locked.publisher, edition=locked.edition, url=locked.url,
        license_id=locked.license_id, license_url=locked.license_url,
        attribution=parsed.attribution, retrieved_at=today,
        upstream_sha256=parsed.content_sha256,
        modifications=locked.modifications,
    ))


_Ayat = list[tuple[int, int, str, str | None]]


def _parse(locked: LockedSource, raw: str) -> _Parsed:
    """The one call site both passes route through to turn raw source text
    into a parsed result -- via parser_for, the single place where a
    lockfile format maps to a parser. Do not call parse_tanzil /
    parse_tanzil_xml directly from build_corpus; that duplication is
    exactly how the translation pass ended up ignoring format entirely."""
    return parser_for(locked.format)(raw)


def _as_ayat(parsed: ParsedTanzil | ParsedTanzilXml) -> _Ayat:
    """Normalizes either parser's output to (surah, ayah, text, bismillah)
    tuples. Only the XML export carries a bismillah; the pipe (txt-2)
    export has none to give, since it prepends the Bismillah into the
    ayah 1 text itself instead of modelling it separately."""
    if isinstance(parsed, ParsedTanzilXml):
        return list(parsed.ayat)
    return [(s, a, t, None) for s, a, t in parsed.verses]


# The printed edition marks a second narration carrying the same number with
# a bare miim -- "مكرر", repeated. It is not a duplicate row: 619 says
# congregational prayer exceeds individual prayer by twenty-seven degrees and
# "619 م" says twenty-five.
_MUKARRAR = "م"

# The display title for each collection's citations, plain ASCII with
# hamza/'ayn dropped -- the house style already used for surah names
# (surah_name_en renders "Al-Fatihah", "An-Nisa", ...; see
# sanad.corpus.surahs). Only "bukhari" is in the lockfile today; the other
# five are dormant until their own sources are added in later Stage A3 tasks,
# but the titles are fixed now so a future addition is a lockfile edit, not a
# code change.
_COLLECTION_TITLE = {
    "bukhari": "Sahih al-Bukhari",
    "muslim": "Sahih Muslim",
    "abudawud": "Sunan Abi Dawud",
    "tirmidhi": "Jami at-Tirmidhi",
    "nasai": "Sunan an-Nasai",
    "ibnmajah": "Sunan Ibn Majah",
}


def _reference_display(collection: str, unit, occurrence: int) -> str:
    """A citation a reader can look up, and that no other record shares.

    Five numbers are printed twice in this edition. Rendering both of a pair
    as "Sahih al-Bukhari 619" would put two different narrations behind one
    citation -- the same defect Stage A had to solve for duplicate verses,
    reappearing on the hadith side. Four of the five pairs mark the second
    with the edition's own mukarrar miim, so that marker is used. 3905 is
    printed twice with no marker at all; there is nothing in the source to
    render, so the ordinal from the record id is shown instead, plainly
    enough that a reader can see it is ours and not the edition's.

    `collection` only changes the title prefix -- the mukarrar miim and the
    occurrence suffix are properties of the edition's numbering, not of which
    collection it belongs to, so they apply identically to every collection.
    """
    title = _COLLECTION_TITLE.get(collection)
    if title is None:
        raise BuildError(
            f"{collection!r} has no display title in _COLLECTION_TITLE. "
            "Add one rather than let a citation render with the wrong name.")
    ref = f"{title} {unit.hadith_no}"
    if unit.is_repeat:
        return f"{ref} {_MUKARRAR}"
    if occurrence > 1:
        return f"{ref} ({occurrence})"
    return ref


def _hadith_records(
    parsed: ParsedOpeniti, locked: LockedSource
) -> list[Record]:
    """The hadith records, as SOURCE-ONLY rows.

    Derived columns (`text_ar_sha256`, the three `norm_*`) are left NULL and
    the `full` record variant is not constructed here at all: both are
    recomputable from the source columns, so `sanad_ingest.materialize` derives
    them from the committed source-only DB instead. See
    `corpus.models.RecordVariant` for why a cut record still needs a second
    representation -- it is just built later, not here.

    `reference_display` IS written here (Stage A3 ruling R-A3-6): it depends on
    `HadithUnit.is_repeat` and a build-time occurrence counter, neither a stored
    column, so it cannot be recomputed downstream and stays a committed source
    column. The duplicate-`reference_display` rejection therefore stays here too.
    """
    out: list[Record] = []
    seen: dict[str, int] = {}
    for u in parsed.units:
        # text_ar is the PRIMARY MATN: never the isnad in front of it, never
        # the further narrations the edition appends behind it. This is the
        # whole of spec §7: similarity.ratio scores the entire stored string,
        # so a 40-character quotation weighed against a 300-character narrator
        # chain lands near 0.13 against a 0.86 threshold. The chain is stored
        # and displayed but never scored; the addenda are stored, displayed,
        # AND scored -- not as part of this string, but as the record's second
        # representation below.
        text = u.matn_ar
        if not text.strip():
            raise BuildError(
                f"{locked.id}: {u.record_id} has an empty scored text. An empty "
                "text_ar is a live verification hazard, so the build stops "
                "rather than ship one. Six of these existed before the parser "
                "learned to read the edition's continuation lines and its "
                "end-of-unit boundary marks; a new one means the source "
                "changed shape again, not that this record should be dropped.")
        seen[u.hadith_no] = seen.get(u.hadith_no, 0) + 1
        out.append(Record(
            id=u.record_id,
            source_id=locked.id,
            kind="hadith",
            collection=locked.collection,
            book_no=u.kitab_no,
            chapter_ar=u.bab_ar,
            hadith_no=u.hadith_no,
            numbering_scheme="bugha-1987",
            text_ar=text,
            isnad_ar=u.isnad_ar,
            addenda_ar=u.addenda_ar,
            # Carried straight through from the audited list in openiti.py.
            # The build never decides this; it only refuses to lose it.
            unscorable_reason=u.unscorable_reason,
            # Derived columns left NULL -- materialize() fills them in.
            text_ar_sha256=None,
            norm_light=None,
            norm_standard=None,
            norm_aggressive=None,
            reference_display=_reference_display(
                locked.collection, u, seen[u.hadith_no]),
        ))

    refs: dict[str, str] = {}
    for r in out:
        if r.reference_display in refs:
            raise BuildError(
                f"{locked.id}: {r.id} and {refs[r.reference_display]} both render "
                f"as {r.reference_display!r}. Two records behind one citation is "
                "the duplicate-reference defect; the build stops rather than ship it.")
        refs[r.reference_display] = r.id

    # Every record the unscorable audit names must still be in the corpus.
    # The list is a judgement about specific records; an entry whose record
    # has gone is an audit that silently covers less than it claims, and the
    # digest check in openiti._unscorable_reason cannot see it because it only
    # fires on records that ARE present. `parse_openiti` emits nothing but
    # "hadith:bukhari:" ids, so this is the one ingest path the list belongs
    # to and the check needs no source-specific guard.
    present = {r.id for r in out}
    for list_name, audited in (("unscorable", UNSCORABLE.get(locked.collection, {})),
                               ("do-not-cut", NEVER_CUT.get(locked.collection, {}))):
        missing = sorted(set(audited) - present)
        if missing:
            raise BuildError(
                f"{locked.id}: {', '.join(missing)} are on the {list_name} audit "
                "list but are not in the parsed corpus. Either the source no "
                "longer carries these records -- in which case the entries must "
                "go, and the surrounding records be read again -- or the parser "
                "stopped producing them, which is a much worse bug. Either way "
                "the build stops rather than ship an audit that covers less than "
                "it says it does.")
    return out


_NOISE_HEADER = """# Hadith OCR noise report

GENERATED by `sanad-ingest build` -- do not edit by hand.

**No text was altered.** Every record listed here is ingested exactly as
published, offending characters and all. Sanad does not correct scripture, and
`content_sha256` in the lockfile is only meaningful if what ships is what was
fetched.

This is a review artifact, never a filter. It exists so that:

1. nobody picks a corrupt record as an eval case and calibrates the matcher
   against damaged text, and
2. the scale of the OCR damage in this source is a measured number rather
   than a vague worry.

A flagged record simply scores badly and returns `NOT_FOUND` or `NEAR_MATCH`,
which is honest: the engine is reporting that the stored text does not match
the quotation, and it does not.

Flagged: every character in a record's **matn** outside the Arabic block
(U+0600-U+06FF) and whitespace. Neither the isnad nor the appended addenda are
scanned -- neither is ever scored or searched, so damage there cannot mislead
an eval case.
"""


def _write_noise_report(path: Path, locked: LockedSource,
                        parsed: ParsedOpeniti, records: list[Record]) -> None:
    ref_by_id = {r.id: r.reference_display for r in records}
    lines = [
        _NOISE_HEADER,
        f"Source: `{locked.id}` ({locked.edition})",
        "",
        (f"Records ingested: {len(parsed.units)} &nbsp;&nbsp; "
         f"Records flagged: {len(parsed.noisy)}"),
        "",
        "| Record | Citation | Characters | Codepoints |",
        "| --- | --- | --- | --- |",
    ]
    for record_id, chars in parsed.noisy:
        codepoints = " ".join(f"U+{ord(c):04X}" for c in chars)
        lines.append(
            f"| `{record_id}` | {ref_by_id.get(record_id, '')} | "
            f"`{chars}` | {codepoints} |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("wrote noise report %s (%d flagged)", path, len(parsed.noisy))


def build_corpus(lockfile: Path, out_db: Path, cache_dir: Path,
                 noise_report: Path | None = None) -> dict[str, int]:
    out_db = Path(out_db)
    if out_db.exists():
        out_db.unlink()

    # SOURCE_SCHEMA_SQL only: the committed DB carries no record_variants, no
    # records_fts and no derived indexes. materialize() re-creates all of them.
    conn = db.connect(out_db, read_only=False, schema=SOURCE_SCHEMA_SQL)
    today = _dt.datetime.now(tz=_dt.timezone.utc).date().isoformat()
    locked_sources = load_lockfile(lockfile)

    # Pass 1: quran-arabic sources. translations.record_id references
    # records.id, so every ayah record must exist before any translation row
    # referencing it is inserted -- we cannot rely on lockfile order for
    # that, so Arabic and translation sources are handled in separate
    # passes rather than a single loop.
    for locked in locked_sources:
        if locked.kind != "quran-arabic":
            continue

        raw = fetch_source(locked, cache_dir)
        parsed = _parse(locked, raw)
        _register_source(conn, locked, parsed, today)

        records = []
        for surah, ayah, text, bismillah in _as_ayat(parsed):
            name_ar, name_en = surah_name(surah)
            records.append(Record(
                id=f"quran:{surah}:{ayah}", source_id=locked.id, kind="ayah",
                surah=surah, ayah=ayah, surah_name_ar=name_ar, surah_name_en=name_en,
                text_ar=text, bismillah=bismillah,
                # Derived columns left NULL -- materialize() fills them in.
                text_ar_sha256=None,
                norm_light=None,
                norm_standard=None,
                norm_aggressive=None,
                reference_display=f"{name_en} {surah}:{ayah}",
            ))
        db.insert_records(conn, records)
        log.info("inserted %d records from %s", len(records), locked.id)

    # Pass 2: hadith sources. Nothing references these rows, so they could sit
    # in either other pass; they get their own because they are a different
    # shape of source, and because the noise report is written from exactly
    # one place.
    for locked in locked_sources:
        if locked.kind != "hadith-arabic":
            continue

        raw = fetch_source(locked, cache_dir)
        parsed = _parse(locked, raw)
        _register_source(conn, locked, parsed, today)

        records = _hadith_records(parsed, locked)
        # The wholly-Qur'anic integrity gate needs norm_standard, which the
        # source-only build no longer computes; it now runs inside
        # materialize() over the derived DB. record_variants are derived there
        # too, so nothing but source rows is written here.
        db.insert_records(conn, records)
        log.info("inserted %d records from %s", len(records), locked.id)
        if noise_report is not None:
            _write_noise_report(Path(noise_report), locked, parsed, records)

    # Pass 3: quran-translation sources, now that every record they
    # reference exists.
    for locked in locked_sources:
        if locked.kind in ("quran-arabic", "hadith-arabic"):
            continue
        if locked.kind != "quran-translation":
            log.warning("skipping %s: kind %r not handled in Stage A",
                        locked.id, locked.kind)
            continue

        raw = fetch_source(locked, cache_dir)
        parsed = _parse(locked, raw)
        _register_source(conn, locked, parsed, today)

        translations = [
            (f"quran:{surah}:{ayah}", locked.id, "en", text)
            for surah, ayah, text, _bismillah in _as_ayat(parsed)
        ]
        db.insert_translations(conn, translations)
        log.info("inserted %d translations from %s", len(translations), locked.id)

    # No rebuild_fts here: records_fts is a derived table absent from the
    # source-only DB. materialize() builds it.
    stats = db.corpus_stats(conn)
    conn.close()
    return stats
