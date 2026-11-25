import pytest

from doclens.validation.tax_id import is_valid_tax_id


@pytest.mark.parametrize("tax_id", ["22099131", "04595257", "10458575", "10458574"])
def test_valid_tax_ids(tax_id: str) -> None:
    assert is_valid_tax_id(tax_id)


@pytest.mark.parametrize("tax_id", ["22099132", "12345678", "1234567", "ABCDEFGH", ""])
def test_invalid_tax_ids(tax_id: str) -> None:
    assert not is_valid_tax_id(tax_id)
