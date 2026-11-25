from pathlib import Path

import pytest

from doclens.synthetic.generate import SyntheticInvoice, generate_invoices
from doclens.synthetic.render import DEFAULT_FONT_PATH, write_invoices

pytestmark = pytest.mark.skipif(
    not DEFAULT_FONT_PATH.exists(), reason="default CJK font only exists on macOS"
)


def test_writes_png_pdf_and_gold_label_per_invoice(tmp_path: Path) -> None:
    invoices = generate_invoices(count=3, seed=1)

    write_invoices(invoices, tmp_path, DEFAULT_FONT_PATH)

    for synthetic in invoices:
        assert (tmp_path / f"{synthetic.id}.png").read_bytes().startswith(b"\x89PNG")
        assert (tmp_path / f"{synthetic.id}.pdf").read_bytes().startswith(b"%PDF")
        gold = (tmp_path / f"{synthetic.id}.json").read_text(encoding="utf-8")
        assert SyntheticInvoice.model_validate_json(gold) == synthetic


def test_same_seed_writes_identical_files(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    write_invoices(generate_invoices(count=6, seed=9), first, DEFAULT_FONT_PATH)
    write_invoices(generate_invoices(count=6, seed=9), second, DEFAULT_FONT_PATH)

    first_files = sorted(path.name for path in first.iterdir())
    assert first_files == sorted(path.name for path in second.iterdir())
    for name in first_files:
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
