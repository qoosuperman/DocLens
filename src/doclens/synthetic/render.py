"""Draw synthetic invoices as PNG and PDF, and write their gold labels as JSON."""

from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from doclens.synthetic.generate import SyntheticInvoice

# Heiti TC ships with every macOS install; other platforms pass --font.
DEFAULT_FONT_PATH = Path("/System/Library/Fonts/STHeiti Medium.ttc")

_DPI = 150
_PAGE_SIZE = (1240, 1754)  # A4 at 150 DPI
_MARGIN = 90
_INK = "black"
_STAMP_RED = (200, 30, 30)
# Table columns: (header, right edge x); the first column is left-aligned.
_COLUMNS = (("品名", 640), ("數量", 800), ("單價", 980), ("金額", _PAGE_SIZE[0] - _MARGIN))


def write_invoices(invoices: list[SyntheticInvoice], out_dir: Path, font_path: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts = _Fonts(font_path)
    for synthetic in invoices:
        image = _draw(synthetic, fonts)
        image.save(out_dir / f"{synthetic.id}.png")
        # Pillow stamps PDFs with the current time by default; pin it so output is reproducible.
        issued = synthetic.invoice.invoice_date.timetuple()
        image.save(
            out_dir / f"{synthetic.id}.pdf", resolution=_DPI, creationDate=issued, modDate=issued
        )
        (out_dir / f"{synthetic.id}.json").write_text(
            synthetic.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )


class _Fonts:
    def __init__(self, path: Path) -> None:
        self.title = ImageFont.truetype(str(path), 52)
        self.body = ImageFont.truetype(str(path), 30)
        self.small = ImageFont.truetype(str(path), 24)


def _draw(synthetic: SyntheticInvoice, fonts: _Fonts) -> Image.Image:
    invoice = synthetic.invoice
    image = Image.new("RGB", _PAGE_SIZE, "white")
    draw = ImageDraw.Draw(image)
    left, right = _MARGIN, _PAGE_SIZE[0] - _MARGIN

    draw.text(
        (_PAGE_SIZE[0] // 2, 110), "統一發票（三聯式）", font=fonts.title, fill=_INK, anchor="mm"
    )
    day = invoice.invoice_date
    draw.text(
        (_PAGE_SIZE[0] // 2, 185),
        f"中華民國 {day.year - 1911} 年 {day.month:02d} 月 {day.day:02d} 日",
        font=fonts.body,
        fill=_INK,
        anchor="mm",
    )

    y = 260
    for label, value in (
        ("發票號碼", invoice.invoice_number),
        ("買受人", synthetic.buyer_name),
        ("統一編號", invoice.buyer_tax_id or ""),
    ):
        draw.text((left, y), f"{label}：{value}", font=fonts.body, fill=_INK)
        y += 50

    y += 20
    draw.line((left, y, right, y), fill=_INK, width=3)
    y += 15
    _draw_row(draw, y, [header for header, _ in _COLUMNS], fonts.body)
    y += 50
    draw.line((left, y, right, y), fill=_INK, width=1)
    for item in invoice.line_items:
        y += 15
        _draw_row(
            draw,
            y,
            [
                item.description,
                _number(item.quantity),
                _number(item.unit_price),
                _number(item.amount),
            ],
            fonts.body,
        )
        y += 45
    y += 15
    draw.line((left, y, right, y), fill=_INK, width=3)

    y += 25
    for label, amount in (
        ("銷售額合計", invoice.subtotal),
        ("營業稅（5%）", invoice.tax),
        ("總計", invoice.total),
    ):
        draw.text((left, y), label, font=fonts.body, fill=_INK)
        draw.text((right, y), _number(amount), font=fonts.body, fill=_INK, anchor="ra")
        y += 55
    draw.line((left, y, right, y), fill=_INK, width=1)

    y += 25
    for line in _wrap(draw, f"備註：{synthetic.note}", fonts.body, right - left):
        draw.text((left, y), line, font=fonts.body, fill=_INK)
        y += 45

    _draw_seller_stamp(draw, synthetic, fonts)
    return image


def _draw_row(
    draw: ImageDraw.ImageDraw, y: int, cells: list[str], font: ImageFont.FreeTypeFont
) -> None:
    draw.text((_MARGIN, y), cells[0], font=font, fill=_INK)
    for cell, (_, right_edge) in zip(cells[1:], _COLUMNS[1:], strict=True):
        draw.text((right_edge, y), cell, font=font, fill=_INK, anchor="ra")


def _draw_seller_stamp(
    draw: ImageDraw.ImageDraw, synthetic: SyntheticInvoice, fonts: _Fonts
) -> None:
    """The seller's 統一發票專用章: name and tax ID in a red box at the bottom right."""
    width, height = 520, 200
    x1, y1 = _PAGE_SIZE[0] - _MARGIN, _PAGE_SIZE[1] - _MARGIN
    x0, y0 = x1 - width, y1 - height
    draw.rectangle((x0, y0, x1, y1), outline=_STAMP_RED, width=4)
    center = (x0 + x1) // 2
    lines = (
        (synthetic.seller_name, fonts.body),
        (f"統一編號 {synthetic.invoice.seller_tax_id}", fonts.body),
        ("統一發票專用章", fonts.small),
    )
    for index, (text, font) in enumerate(lines):
        draw.text((center, y0 + 45 + index * 55), text, font=font, fill=_STAMP_RED, anchor="mm")


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int
) -> list[str]:
    lines = [""]
    for char in text:
        if draw.textlength(lines[-1] + char, font=font) > max_width:
            lines.append("")
        lines[-1] += char
    return lines


def _number(value: Decimal) -> str:
    return f"{value:,}"
