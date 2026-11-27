import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
import openai
import pytest

from doclens.extraction.extract import ExtractionError, extract_invoice
from doclens.schemas.invoice import Invoice, LineItem


class FakeModel:
    """依序回傳預先寫好的原始輸出，並記錄收到的每個 request。"""

    def __init__(self, outputs: list[str], status_code: int = 200) -> None:
        self._outputs = list(outputs)
        self._status_code = status_code
        self.requests: list[dict[str, Any]] = []

    def client(self) -> openai.OpenAI:
        transport = httpx2.MockTransport(self._handle)
        # 關掉 SDK 對 429、5xx 的自動重試，request 次數才只反映 Instructor 的重問。
        return openai.OpenAI(
            api_key="test", http_client=httpx2.Client(transport=transport), max_retries=0
        )

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        if self._status_code != 200:
            return httpx2.Response(self._status_code, json={"error": {"message": "fake error"}})
        content = self._outputs.pop(0)
        return httpx2.Response(
            200,
            json={
                "id": f"chatcmpl-{len(self.requests)}",
                "object": "chat.completion",
                "created": 0,
                "model": "fake",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
            },
        )


def raw_output(**invoice_overrides: Any) -> str:
    invoice: dict[str, Any] = {
        "invoice_number": "AB12345678",
        "invoice_date": "2026-11-01",
        "seller_tax_id": "22099131",
        "buyer_tax_id": "04595257",
        "line_items": [
            {"description": "A4 影印紙", "quantity": 10, "unit_price": 120, "amount": 1200},
            {"description": "碳粉匣", "quantity": 2, "unit_price": 1500, "amount": 3000},
        ],
        "subtotal": 4200,
        "tax": 210,
        "total": 4410,
    }
    invoice.update(invoice_overrides)
    return json.dumps(
        {
            "invoice": invoice,
            "unreadable_fields": ["line_items[1].amount"],
            "instruction_text_detected": True,
        },
        ensure_ascii=False,
    )


@pytest.fixture
def image(tmp_path: Path) -> Path:
    path = tmp_path / "invoice.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return path


def test_extraction_converts_to_invoice(image: Path) -> None:
    fake = FakeModel([raw_output()])

    result = extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=2)

    assert result.unreadable_fields == ["line_items[1].amount"]
    assert result.instruction_text_detected is True
    assert result.invoice.to_invoice() == Invoice(
        invoice_number="AB12345678",
        invoice_date=date(2026, 11, 1),
        seller_tax_id="22099131",
        buyer_tax_id="04595257",
        line_items=[
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
        subtotal=Decimal("4200"),
        tax=Decimal("210"),
        total=Decimal("4410"),
    )


@pytest.mark.parametrize(
    ("invalid", "field"),
    [
        ({"invoice_date": "0115-11-01"}, "invoice_date"),
        ({"seller_tax_id": "2209913"}, "seller_tax_id"),
        ({"line_items": []}, "line_items"),
        (
            {
                "line_items": [
                    {"description": "A4 影印紙", "quantity": 0, "unit_price": 120, "amount": 0}
                ]
            },
            "quantity",
        ),
    ],
    ids=["roc-year-date", "malformed-tax-id", "no-line-items", "zero-quantity"],
)
def test_invalid_output_is_fed_back_and_retried(
    image: Path, invalid: dict[str, Any], field: str
) -> None:
    fake = FakeModel([raw_output(**invalid), raw_output()])

    result = extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=2)

    assert result.invoice.invoice_date == date(2026, 11, 1)
    assert len(fake.requests) == 2
    # 只看最後一則錯誤回饋；前一則是模型上次的輸出，本來就含所有欄位名稱。
    feedback = fake.requests[1]["messages"][-1]["content"]
    assert field in feedback


def test_business_rule_violations_are_not_retried(image: Path) -> None:
    # 總計對不上（4200 + 210 ≠ 9999）是業務規則問題，照單據回傳，留給規則檢查。
    fake = FakeModel([raw_output(total=9999)])

    result = extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=2)

    assert len(fake.requests) == 1
    assert result.invoice.to_invoice().total == Decimal("9999")


def test_non_integer_amounts_convert_to_exact_decimals(image: Path) -> None:
    fake = FakeModel(
        [
            raw_output(
                line_items=[
                    {"description": "膠帶", "quantity": 0.5, "unit_price": 19.9, "amount": 9.95}
                ],
                subtotal=9.95,
                tax=0.5,
                total=10.45,
            )
        ]
    )

    invoice = extract_invoice(
        image, fake.client(), model="gpt-4o-mini", max_retries=2
    ).invoice.to_invoice()

    item = invoice.line_items[0]
    assert (item.quantity, item.unit_price, item.amount) == (
        Decimal("0.5"),
        Decimal("19.9"),
        Decimal("9.95"),
    )
    assert (invoice.subtotal, invoice.tax, invoice.total) == (
        Decimal("9.95"),
        Decimal("0.5"),
        Decimal("10.45"),
    )


def test_unsupported_image_format_is_rejected_before_calling_the_model(tmp_path: Path) -> None:
    image = tmp_path / "invoice.gif"
    image.write_bytes(b"GIF89a")
    fake = FakeModel([raw_output()])

    with pytest.raises(ValueError, match="不支援的圖片格式"):
        extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=2)

    assert fake.requests == []


@pytest.mark.parametrize("max_retries", [0, 2])
def test_raises_after_max_retries(image: Path, max_retries: int) -> None:
    fake = FakeModel([raw_output(invoice_date="0115-11-01")] * (max_retries + 1))

    with pytest.raises(ExtractionError):
        extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=max_retries)

    assert len(fake.requests) == max_retries + 1


def test_document_is_sent_only_in_user_message_with_strict_schema(image: Path) -> None:
    fake = FakeModel([raw_output()])

    extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=2)

    request = fake.requests[0]
    system, user = request["messages"]
    assert system["role"] == "system"
    assert "data:image" not in json.dumps(system)
    assert user["role"] == "user"
    assert user["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert request["model"] == "gpt-4o-mini"
    assert request["response_format"]["json_schema"]["strict"] is True


@pytest.mark.parametrize(
    ("status_code", "error"),
    [
        (401, openai.AuthenticationError),
        (429, openai.RateLimitError),
        (500, openai.InternalServerError),
    ],
)
def test_api_errors_are_not_reported_as_validation_failures(
    image: Path, status_code: int, error: type[openai.APIError]
) -> None:
    fake = FakeModel([], status_code=status_code)

    with pytest.raises(error):
        extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=2)

    assert len(fake.requests) == 1
