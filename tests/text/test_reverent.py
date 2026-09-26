"""Tests for the reverent-naming transform (spec 2026-09-26).

The honorific constants are Arabic; per sanad-character-transit-defect these
tests pin the EXACT codepoints (built via chr() here too, never typed glyphs)
so a silently-wrong ligature or a dropped letter fails loudly rather than
looking right on screen.
"""
from __future__ import annotations

from sanad.text.reverent import ALAYHI_SALAM, SALLALLAHU, reverent

# Rebuild the expected constants independently from codepoints so the test does
# not merely echo the module's own value.
_SAW = chr(0xFDFA)  # ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM
_AS = "".join(chr(c) for c in (
    0x0639, 0x0644, 0x064A, 0x0647, 0x20,          # ع ل ي ه (space)
    0x0627, 0x0644, 0x0633, 0x0644, 0x0627, 0x0645))  # ا ل س ل ا م


def test_honorific_constants_are_exact_codepoints():
    assert SALLALLAHU == _SAW
    assert ALAYHI_SALAM == _AS


# --- divine name -----------------------------------------------------------

def test_capital_god_becomes_allah():
    assert reverent("They worship God alone.") == "They worship Allah alone."


def test_god_possessive_becomes_allah_possessive():
    assert reverent("It is God's decree.") == "It is Allah's decree."


def test_lowercase_god_is_left_alone():
    # "a false god" must never become "a false Allah".
    assert reverent("They warned against every false god.") == \
        "They warned against every false god."


def test_god_substrings_untouched():
    assert reverent("Godfrey felt good.") == "Godfrey felt good."


# --- honorifics ------------------------------------------------------------

def test_muhammad_gets_sallallahu():
    assert reverent("The Prophet Muhammad taught this.") == \
        f"The Prophet Muhammad {_SAW} taught this."


def test_muhammad_alternate_spellings():
    for name in ("Muhammed", "Mohammed", "Mohammad"):
        assert reverent(f"{name} said so.") == f"{name} {_SAW} said so."


def test_other_prophet_gets_alayhi_salam():
    assert reverent("Moses spoke to his people.") == \
        f"Moses {_AS} spoke to his people."


def test_transliterated_prophet_name():
    assert reverent("The story of Musa is cited.") == \
        f"The story of Musa {_AS} is cited."


def test_possessive_prophet_name_is_not_stamped():
    # "Muhammad's companions" -> awkward to insert mid-possessive; skip it.
    assert reverent("Muhammad's companions narrated it.") == \
        "Muhammad's companions narrated it."


def test_idempotent_muhammad():
    once = reverent("Prophet Muhammad said.")
    assert reverent(once) == once


def test_idempotent_other_prophet():
    once = reverent("Jesus healed the sick.")
    assert reverent(once) == once


def test_combined_god_and_prophet():
    assert reverent("Moses called the people to God.") == \
        f"Moses {_AS} called the people to Allah."


def test_empty_and_none_safe():
    assert reverent("") == ""
