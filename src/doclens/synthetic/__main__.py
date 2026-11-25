"""Generate synthetic invoices: `python -m doclens.synthetic --count 20 --seed 42`."""

import argparse
from collections import Counter
from pathlib import Path

from doclens.synthetic.generate import generate_invoices
from doclens.synthetic.render import DEFAULT_FONT_PATH, write_invoices


def main() -> None:
    parser = argparse.ArgumentParser(
        description="產生合成三聯式統一發票（PNG、PDF 與標準答案 JSON）"
    )
    parser.add_argument("--count", type=int, default=20, help="發票張數（預設 20）")
    parser.add_argument("--seed", type=int, default=0, help="亂數種子，同一個 seed 結果相同")
    parser.add_argument(
        "--out", type=Path, default=Path("data/synthetic"), help="輸出目錄（預設 data/synthetic）"
    )
    parser.add_argument(
        "--error-ratio", type=float, default=0.5, help="注入錯誤的比例，0 到 1（預設 0.5）"
    )
    parser.add_argument(
        "--font",
        type=Path,
        default=DEFAULT_FONT_PATH,
        help=f"CJK 字型路徑（預設 {DEFAULT_FONT_PATH}）",
    )
    args = parser.parse_args()

    if not args.font.exists():
        parser.error(f"找不到字型 {args.font}，請用 --font 指定 CJK 字型")
    try:
        invoices = generate_invoices(args.count, args.seed, args.error_ratio)
    except ValueError as error:
        parser.error(str(error))

    write_invoices(invoices, args.out, args.font)
    error_types = Counter(synthetic.error_type.value for synthetic in invoices)
    print(f"已產生 {len(invoices)} 張發票到 {args.out}：{dict(sorted(error_types.items()))}")


if __name__ == "__main__":
    main()
