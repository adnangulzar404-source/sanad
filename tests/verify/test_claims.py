import pytest
from sanad.verify.claims import RiskCode, detect_claims, requires_handoff, route_risk


def test_detects_unanimity_claim():
    kinds = {c.kind for c in detect_claims("All scholars agree this is obligatory.")}
    assert "unanimity" in kinds


def test_detects_ijma_spelling():
    assert "unanimity" in {c.kind for c in detect_claims("There is ijma on this.")}


def test_detects_hadith_citation_without_edition():
    assert "hadith_unverifiable" in {c.kind for c in detect_claims("Bukhari 99999 says...")}


def test_detects_legal_conclusion():
    claims = detect_claims("Therefore Islam requires every convert to follow one school.")
    assert "legal_conclusion" in {c.kind for c in claims}


def test_clean_text_yields_no_claims():
    assert detect_claims("This surah has four verses.") == []


def test_personal_question_routes_to_handoff():
    assert route_risk("Can I marry my cousin?") is RiskCode.PERSONAL_RULING
    assert route_risk("Should I divorce my wife?") is RiskCode.PERSONAL_RULING


def test_high_risk_topic_routes_to_handoff():
    assert route_risk("Explain the ruling on apostasy and takfir.") is RiskCode.HIGH_RISK


def test_disputed_topic_is_flagged_but_not_handoff():
    assert route_risk("What do the four madhhabs say about this?") is RiskCode.DISPUTED
    assert requires_handoff(RiskCode.DISPUTED) is False


def test_general_question_is_general():
    assert route_risk("How many verses are in Al-Ikhlas?") is RiskCode.GENERAL


def test_personal_outranks_high_risk():
    # a personal framing must win, because it changes who should answer
    assert route_risk("Should I divorce my wife over apostasy?") is RiskCode.PERSONAL_RULING


def test_handoff_required_for_personal_and_high_risk():
    assert requires_handoff(RiskCode.PERSONAL_RULING) is True
    assert requires_handoff(RiskCode.HIGH_RISK) is True
    assert requires_handoff(RiskCode.GENERAL) is False


@pytest.mark.parametrize(
    "q",
    [
        "Is it permissible for me to delay my prayers when travelling?",
        "Is it permitted to pay zakat to my parents?",
        "Must I make up the fasts I missed?",
        "Would it be wrong for me to take this job?",
        "Am I obliged to pray if I am sick?",
        "Am I required to fast while pregnant?",
        "Do I have to repay a debt my father left?",
        "Is it a sin for me to miss Friday prayer for work?",
    ],
)
def test_personal_ruling_phrasings_are_all_diverted(q):
    assert route_risk(q) is RiskCode.PERSONAL_RULING


@pytest.mark.parametrize(
    "q",
    [
        "For a woman in my position, what are the inheritance rules?",
        "For someone facing my situation, what does Islam say?",
        "Given my circumstances, what does the Quran advise?",
        "In my case, how is the estate divided?",
        "What should a person in my circumstances do?",
    ],
)
def test_personal_circumstance_phrases_divert_without_a_normative_word(q):
    assert route_risk(q) is RiskCode.PERSONAL_RULING


@pytest.mark.parametrize(
    "q",
    [
        "Is it permitted to work in banking?",
        "Is it permissible for a woman to go out without mahram?",
    ],
)
def test_abstract_doctrinal_questions_stay_general(q):
    # deliberately NOT diverted: no asker-specific framing.
    assert route_risk(q) is RiskCode.GENERAL
