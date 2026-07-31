from app.evaluation.metrics import evaluate_refusal, mean_reciprocal_rank, precision_at_k, recall_at_k


def test_precision_at_k_all_relevant():
    assert precision_at_k(["a.pdf", "a.pdf", "a.pdf"], {"a.pdf"}, k=3) == 1.0


def test_precision_at_k_partial_match():
    assert precision_at_k(["a.pdf", "b.pdf", "c.pdf"], {"a.pdf"}, k=3) == 1 / 3


def test_precision_at_k_no_expected_returns_zero():
    assert precision_at_k(["a.pdf"], set(), k=3) == 0.0


def test_precision_at_k_empty_retrieval_returns_zero():
    assert precision_at_k([], {"a.pdf"}, k=3) == 0.0


def test_recall_at_k_finds_all_expected():
    assert recall_at_k(["a.pdf", "b.pdf"], {"a.pdf", "b.pdf"}, k=2) == 1.0


def test_recall_at_k_partial():
    assert recall_at_k(["a.pdf", "c.pdf"], {"a.pdf", "b.pdf"}, k=2) == 0.5


def test_recall_at_k_respects_k_cutoff():
    assert recall_at_k(["c.pdf", "d.pdf", "a.pdf"], {"a.pdf"}, k=2) == 0.0


def test_mrr_first_position():
    assert mean_reciprocal_rank(["a.pdf", "b.pdf"], {"a.pdf"}) == 1.0


def test_mrr_second_position():
    assert mean_reciprocal_rank(["b.pdf", "a.pdf"], {"a.pdf"}) == 0.5


def test_mrr_not_found_returns_zero():
    assert mean_reciprocal_rank(["b.pdf", "c.pdf"], {"a.pdf"}) == 0.0


def test_mrr_no_expected_returns_zero():
    assert mean_reciprocal_rank(["a.pdf"], set()) == 0.0


def test_evaluate_refusal_correct_refusal_on_unanswerable_case():
    outcome = evaluate_refusal(is_answerable=False, insufficient_evidence=True)
    assert outcome.correct_refusal is True
    assert outcome.false_refusal is None


def test_evaluate_refusal_incorrect_non_refusal_on_unanswerable_case():
    outcome = evaluate_refusal(is_answerable=False, insufficient_evidence=False)
    assert outcome.correct_refusal is False
    assert outcome.false_refusal is None


def test_evaluate_refusal_false_refusal_on_answerable_case():
    outcome = evaluate_refusal(is_answerable=True, insufficient_evidence=True)
    assert outcome.false_refusal is True
    assert outcome.correct_refusal is None


def test_evaluate_refusal_correct_non_refusal_on_answerable_case():
    outcome = evaluate_refusal(is_answerable=True, insufficient_evidence=False)
    assert outcome.false_refusal is False
    assert outcome.correct_refusal is None
