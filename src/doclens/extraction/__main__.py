"""擷取一張發票圖片：`python -m doclens.extraction invoice.png`。"""

import argparse
import sys
from pathlib import Path

import openai

from doclens.config import Settings
from doclens.extraction.extract import ExtractionError, extract_invoice


def main() -> None:
    parser = argparse.ArgumentParser(description="用 OpenAI 擷取一張發票圖片（PNG/JPG）並印出結果")
    parser.add_argument("image", type=Path, help="發票圖片路徑")
    args = parser.parse_args()

    settings = Settings()
    if not settings.openai_api_key:
        parser.error("沒有設定 OPENAI_API_KEY，請寫進 .env")
    if not args.image.is_file():
        parser.error(f"找不到檔案 {args.image}")

    client = openai.OpenAI(api_key=settings.openai_api_key)
    try:
        result = extract_invoice(
            args.image,
            client,
            model=settings.openai_model,
            max_retries=settings.extraction_max_retries,
        )
    except ValueError as error:
        parser.error(str(error))
    except ExtractionError as error:
        print(error, file=sys.stderr)
        sys.exit(1)

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
