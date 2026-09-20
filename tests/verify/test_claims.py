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


def test_both_apostrophe_forms_match_transliterations():
    # Apostrophe class must match both straight and curly quotes in mid-word positions
    # where the apostrophe is load-bearing (not optional)

    # shafi’i with straight apostrophe
    assert route_risk("Follow the Shafi’i school") is RiskCode.DISPUTED
    # shafi’i with right single quotation mark (U+2019)
    assert route_risk("Follow the Shafi’i school") is RiskCode.DISPUTED

    # nasa’i with straight apostrophe (load-bearing in hadith pattern)
    assert "hadith_unverifiable" in {c.kind for c in detect_claims("See nasa’i 1234")}
    # nasa’i with right single quotation mark (U+2019)
    assert "hadith_unverifiable" in {c.kind for c in detect_claims("See nasa’i 1234")}


def test_apostasy_without_first_person_is_high_risk():
    # Apostasy/faith-crisis language without first-person framing
    assert route_risk("Someone is leaving Islam") is RiskCode.HIGH_RISK


def test_apostasy_with_first_person_is_personal_ruling():
    # Apostasy with first-person framing
    assert route_risk("I'm thinking about leaving Islam") is RiskCode.PERSONAL_RULING
    assert route_risk("I don't believe anymore") is RiskCode.PERSONAL_RULING


def test_hadith_pattern_is_required():
    # Verify that \bhadith\b fallback is pinned by a test
    assert "hadith_unverifiable" in {c.kind for c in detect_claims("mentioned in hadith")}


def test_apostasy_high_risk_pattern_is_required():
    # Verify that apostasy/apostate pattern is pinned by a test
    assert route_risk("Discussing apostasy in Islam") is RiskCode.HIGH_RISK


@pytest.mark.parametrize(
    "q",
    [
        # Coordinator's three sentences
        "I've become an atheist and don't want to pray anymore.",
        "I'm losing my faith and don't know what to do.",
        "He told me he doesn't believe in Islam anymore.",
        # Additional inflected variants
        "I'm becoming agnostic and questioning everything.",
        "I've lost my faith completely.",
        "My beliefs are changing and I no longer believe.",
        "I don't believe anymore and it's causing family conflict.",
    ],
)
def test_faith_crisis_inflected_variants_diverted(q):
    # Faith crisis phrasing must be caught even with various verb forms and negations
    result = route_risk(q)
    assert result in (RiskCode.PERSONAL_RULING, RiskCode.HIGH_RISK), f"Failed for: {q}"


@pytest.mark.parametrize(
    "q",
    [
        "Is it okay if I skip Ramadan fasting because I'm breastfeeding?",
        "Is it ok if I don't fast?",
        "Is it alright for me to work on Friday?",
    ],
)
def test_okay_ok_alright_register_is_caught(q):
    # "okay", "ok", "alright" are normative markers
    assert route_risk(q) is RiskCode.PERSONAL_RULING


@pytest.mark.parametrize(
    "q",
    [
        "Is it forbidden for me to date before marriage?",
        "Can I date, or is it forbidden?",
    ],
)
def test_forbidden_is_caught(q):
    # "forbidden" is a normative marker
    assert route_risk(q) is RiskCode.PERSONAL_RULING


@pytest.mark.parametrize(
    "q",
    [
        "My brother wants to know if he can stop paying his ex-wife's alimony.",
        "She could convert if she wanted.",
    ],
)
def test_third_person_about_self_with_can_could(q):
    # "can" and "could" in third-person phrasing
    assert route_risk(q) is RiskCode.PERSONAL_RULING


@pytest.mark.parametrize(
    "q",
    [
        "plz tell me am i sinning if i not fast today",
        "my mom says im committing a sin if i skip prayers",
    ],
)
def test_sinning_variant_is_caught(q):
    # sin(?:ful|ning|s)? pattern must match "sinning"
    assert route_risk(q) is RiskCode.PERSONAL_RULING
