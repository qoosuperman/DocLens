from collections import Counter

from doclens.synthetic.generate import ErrorType, generate_invoices
from doclens.validation.rules import check_invoice

SEEDS = range(200)

EXPECTED_VIOLATIONS = {
    ErrorType.NONE: set(),
    ErrorType.SELLER_TAX_ID: {"seller_tax_id"},
    ErrorType.LINE_AMOUNT: {"line_amount"},
    ErrorType.SUBTOTAL: {"subtotal"},
    ErrorType.TOTAL: {"total"},
    ErrorType.PROMPT_INJECTION: set(),
}


def test_invoices_without_errors_have_no_violations() -> None:
    for seed in SEEDS:
        for synthetic in generate_invoices(count=6, seed=seed, error_ratio=0):
            assert check_invoice(synthetic.invoice) == [], synthetic


def test_each_injected_error_triggers_exactly_its_rule_violation() -> None:
    seen: set[ErrorType] = set()
    for seed in SEEDS:
        for synthetic in generate_invoices(count=5, seed=seed, error_ratio=1):
            violations = {violation.rule for violation in check_invoice(synthetic.invoice)}
            assert violations == EXPECTED_VIOLATIONS[synthetic.error_type], synthetic
            seen.add(synthetic.error_type)
    assert seen == set(EXPECTED_VIOLATIONS) - {ErrorType.NONE}


def test_default_injects_errors_into_half_split_evenly_across_types() -> None:
    error_types = Counter(synthetic.error_type for synthetic in generate_invoices(100, seed=7))
    assert error_types == {
        ErrorType.NONE: 50,
        ErrorType.SELLER_TAX_ID: 10,
        ErrorType.LINE_AMOUNT: 10,
        ErrorType.SUBTOTAL: 10,
        ErrorType.TOTAL: 10,
        ErrorType.PROMPT_INJECTION: 10,
    }


def test_gold_label_lists_expected_review_reasons() -> None:
    expected = {
        ErrorType.NONE: [],
        ErrorType.SELLER_TAX_ID: ["rule_violation"],
        ErrorType.LINE_AMOUNT: ["rule_violation"],
        ErrorType.SUBTOTAL: ["rule_violation"],
        ErrorType.TOTAL: ["rule_violation"],
        ErrorType.PROMPT_INJECTION: ["prompt_injection"],
    }
    for synthetic in generate_invoices(count=12, seed=3):
        assert synthetic.expected_review_reasons == expected[synthetic.error_type]


def test_small_batches_still_cover_every_error_type_across_seeds() -> None:
    seen = {
        synthetic.error_type
        for seed in SEEDS
        for synthetic in generate_invoices(count=2, seed=seed, error_ratio=1)
    }
    assert seen == set(EXPECTED_VIOLATIONS) - {ErrorType.NONE}
