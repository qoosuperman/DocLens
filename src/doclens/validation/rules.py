"""Deterministic business-rule checks run after LLM extraction."""

from decimal import Decimal

from pydantic import BaseModel

from doclens.schemas.invoice import Invoice
from doclens.validation.tax_id import is_valid_tax_id

# Line amounts are often rounded to whole dollars on printed invoices.
_TOLERANCE = Decimal("1")


class RuleViolation(BaseModel):
    rule: str
    message: str


def check_invoice(invoice: Invoice) -> list[RuleViolation]:
    violations: list[RuleViolation] = []

    if not is_valid_tax_id(invoice.seller_tax_id):
        violations.append(
            RuleViolation(
                rule="seller_tax_id", message=f"賣方統編 {invoice.seller_tax_id} 檢查碼錯誤"
            )
        )
    if invoice.buyer_tax_id is not None and not is_valid_tax_id(invoice.buyer_tax_id):
        violations.append(
            RuleViolation(
                rule="buyer_tax_id", message=f"買方統編 {invoice.buyer_tax_id} 檢查碼錯誤"
            )
        )

    for index, item in enumerate(invoice.line_items):
        expected = item.quantity * item.unit_price
        if abs(expected - item.amount) > _TOLERANCE:
            violations.append(
                RuleViolation(
                    rule="line_amount",
                    message=f"第 {index + 1} 項小計 {item.amount} ≠ 數量×單價 {expected}",
                )
            )

    line_sum = sum((item.amount for item in invoice.line_items), Decimal("0"))
    if abs(line_sum - invoice.subtotal) > _TOLERANCE:
        violations.append(
            RuleViolation(
                rule="subtotal", message=f"銷售額 {invoice.subtotal} ≠ 品項加總 {line_sum}"
            )
        )

    if invoice.subtotal + invoice.tax != invoice.total:
        violations.append(
            RuleViolation(
                rule="total",
                message=f"總計 {invoice.total} ≠ 銷售額 {invoice.subtotal} + 稅額 {invoice.tax}",
            )
        )

    return violations
