from app.generation.citation_parsing import contains_citation, find_citation_numbers, find_citation_numbers_sorted


def test_finds_ascii_bracket_citations():
    assert find_citation_numbers("Supported by evidence [1] and [2].") == [1, 2]


def test_finds_fullwidth_bracket_citations():
    assert find_citation_numbers("Supported by evidence \u30101\u3011 and \u30102\u3011.") == [1, 2]


def test_finds_mixed_bracket_styles_in_same_text():
    assert find_citation_numbers("First point [1], second point \u30102\u3011, third [3].") == [1, 2, 3]


def test_tolerates_internal_whitespace_in_either_bracket_style():
    assert find_citation_numbers("Claim [ 1 ] and claim \u3010 2 \u3011.") == [1, 2]


def test_deduplicates_while_preserving_first_seen_order():
    assert find_citation_numbers("[3] appears, then [1], then [3] again.") == [3, 1]
    assert find_citation_numbers_sorted("[3] appears, then [1], then [3] again.") == [1, 3]


def test_no_citations_returns_empty_list():
    assert find_citation_numbers("A sentence with no citation markers at all.") == []


def test_contains_citation_detects_either_bracket_style():
    assert contains_citation("supported [1]") is True
    assert contains_citation("supported \u30101\u3011") is True
    assert contains_citation("not supported at all") is False
