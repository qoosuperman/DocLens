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
    """Returns pre-written raw outputs in order and records every request it receives."""

    def __init__(self, outputs: list[str], status_code: int = 200) -> None:
        self._outputs = list(outputs)
        self._status_code = status_code
        self.requests: list[dict[str, Any]] = []

    def client(self) -> openai.OpenAI:
        transport = httpx2.MockTransport(self._handle)
        return openai.OpenAI(api_key="test", http_client=httpx2.Client(transport=transport))

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
    ],
    ids=["roc-year-date", "malformed-tax-id"],
)
def test_invalid_output_is_fed_back_and_retried(
    image: Path, invalid: dict[str, Any], field: str
) -> None:
    fake = FakeModel([raw_output(**invalid), raw_output()])

    result = extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=2)

    assert result.invoice.invoice_date == date(2026, 11, 1)
    assert len(fake.requests) == 2
    retry_messages = json.dumps(fake.requests[1]["messages"], ensure_ascii=False)
    assert field in retry_messages


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


def test_api_errors_are_not_reported_as_validation_failures(image: Path) -> None:
    fake = FakeModel([], status_code=401)

    with pytest.raises(openai.AuthenticationError):
        extract_invoice(image, fake.client(), model="gpt-4o-mini", max_retries=2)

    assert len(fake.requests) == 1
