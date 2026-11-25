from datetime import date
from decimal import Decimal
from typing import Any

from doclens.schemas.invoice import Invoice, LineItem
from doclens.validation.rules import check_invoice


def make_invoice(**overrides: Any) -> Invoice:
    fields: dict[str, Any] = {
        "invoice_number": "AB12345678",
        "invoice_date": date(2026, 11, 1),
        "seller_tax_id": "22099131",
        "buyer_tax_id": "04595257",
        "line_items": [
            LineItem(
                description="A4 影印紙",
                quantity=Decimal("10"),
                unit_price=Decimal("120"),
                amount=Decimal("1200"),
            ),
            LineItem(
                description="碳粉匣",
                quantity=Decimal("2"),
                unit_price=Decimal("1500"),
                amount=Decimal("3000"),
            ),
        ],
        "subtotal": Decimal("4200"),
        "tax": Decimal("210"),
        "total": Decimal("4410"),
    }
    fields.update(overrides)
    return Invoice(**fields)


def rules_of(invoice: Invoice) -> set[str]:
    return {violation.rule for violation in check_invoice(invoice)}


def test_consistent_invoice_has_no_violations() -> None:
    assert check_invoice(make_invoice()) == []


def test_bad_seller_tax_id() -> None:
    assert rules_of(make_invoice(seller_tax_id="22099132")) == {"seller_tax_id"}


def test_line_amount_mismatch() -> None:
    items = [
        LineItem(
            description="A4 影印紙",
            quantity=Decimal("10"),
            unit_price=Decimal("120"),
            amount=Decimal("1300"),
        )
    ]
    invoice = make_invoice(
        line_items=items, subtotal=Decimal("1300"), tax=Decimal("65"), total=Decimal("1365")
    )
    assert rules_of(invoice) == {"line_amount"}


def test_subtotal_mismatch() -> None:
    invoice = make_invoice(subtotal=Decimal("4000"), tax=Decimal("200"), total=Decimal("4200"))
    assert rules_of(invoice) == {"subtotal"}


def test_total_mismatch() -> None:
    assert rules_of(make_invoice(total=Decimal("4400"))) == {"total"}
