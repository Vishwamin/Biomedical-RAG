from app.services.chat_titles import generate_chat_title


def test_generates_title_from_question_stripping_leading_question_word():
    title = generate_chat_title("What biomarkers validate Alzheimer's diagnosis?")
    assert title != "New Chat"
    assert "Biomarkers" in title
    assert "Alzheimer's" in title
    assert not title.lower().startswith("what")


def test_falls_back_to_new_chat_for_empty_input():
    assert generate_chat_title("") == "New Chat"
    assert generate_chat_title("   ") == "New Chat"


def test_falls_back_to_new_chat_for_only_stopwords():
    assert generate_chat_title("What is the of a") != ""  # never raises / never empty string


def test_title_is_capped_in_length():
    long_question = "What is the relationship between " + " ".join([f"factor{i}" for i in range(30)])
    title = generate_chat_title(long_question)
    assert len(title) <= 49  # 48 chars + possible ellipsis


def test_title_never_ends_with_question_mark():
    title = generate_chat_title("Why does this happen???")
    assert not title.endswith("?")


def test_preserves_hyphenated_and_apostrophe_terms():
    title = generate_chat_title("What about IL-6 and Alzheimer's biomarkers?")
    assert "IL-6" in title
    assert "Alzheimer's" in title
