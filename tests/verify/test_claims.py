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
