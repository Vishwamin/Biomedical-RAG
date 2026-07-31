from app.verification.claims import extract_claims


def test_extract_claims_splits_sentences_and_captures_citations():
    answer = "Treatment X reduced inflammation significantly [1]. However, sample size was small [2][3]."
    claims = extract_claims(answer)
    assert len(claims) == 2
    assert claims[0].citation_numbers == [1]
    assert claims[1].citation_numbers == [2, 3]
    assert "Treatment X" in claims[0].claim_text


def test_extract_claims_handles_no_citations():
    answer = "This is a plain sentence with no citation attached at all."
    claims = extract_claims(answer)
    assert len(claims) == 1
    assert claims[0].citation_numbers == []


def test_extract_claims_filters_short_fragments():
    answer = "Yes. No. This is a real substantive claim about biomarkers [1]."
    claims = extract_claims(answer)
    assert all(len(c.claim_text) >= 15 for c in claims)
    assert any("biomarkers" in c.claim_text for c in claims)


def test_extract_claims_empty_answer_returns_empty_list():
    assert extract_claims("") == []
    assert extract_claims("   ") == []


def test_extract_claims_ids_are_sequential():
    answer = "First claim goes here for testing. Second claim goes here too."
    claims = extract_claims(answer)
    assert [c.claim_id for c in claims] == ["claim_01", "claim_02"]


def test_regression_extract_claims_captures_fullwidth_bracket_citations():
    """
    Real bug: claims.py had its own independent ASCII-only citation regex,
    separate from generator.py's. Both now share one parser so this can't
    happen again in one call site while looking fixed in the other.
    """
    answer = "Elevated biomarker levels were observed in the treatment group \u30101\u3011\u30102\u3011."
    claims = extract_claims(answer)
    assert len(claims) == 1
    assert claims[0].citation_numbers == [1, 2]
