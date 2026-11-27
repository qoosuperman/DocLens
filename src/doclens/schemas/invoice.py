"""台灣統一發票的領域模型：只放格式約束，業務規則見 `validation/rules.py`。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(description="品名，照單據原文")
    quantity: Decimal = Field(gt=0, description="數量")
    unit_price: Decimal = Field(ge=0, description="單價（未稅）")
    amount: Decimal = Field(ge=0, description="小計（未稅），單據上印的金額")


class Invoice(BaseModel):
    invoice_number: str = Field(pattern=r"^[A-Z]{2}\d{8}$", description="發票號碼，例如 AB12345678")
    invoice_date: date = Field(description="發票日期")
    seller_tax_id: str = Field(pattern=r"^\d{8}$", description="賣方統一編號")
    buyer_tax_id: str | None = Field(default=None, pattern=r"^\d{8}$", description="買方統一編號")
    line_items: list[LineItem] = Field(min_length=1)
    subtotal: Decimal = Field(ge=0, description="銷售額合計（未稅）")
    tax: Decimal = Field(ge=0, description="營業稅")
    total: Decimal = Field(ge=0, description="總計（含稅）")
