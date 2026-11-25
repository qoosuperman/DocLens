# DocLens

AI 單據自動化：上傳發票（PDF／照片），用 LLM 擷取結構化欄位，經規則檢核後，把信心度低或檢核失敗的單據交給人工審核，最後寫入 ERP。

## MVP 範圍（第一階段）

1. 上傳發票 → OpenAI 多模態擷取，輸出對應 Pydantic schema，驗證失敗自動 retry
2. 規則檢核（guardrails）：統一編號檢查碼、品項小計、銷售額與總計
3. 低信心或檢核失敗 → LangGraph interrupt 交由人工審核（Streamlit 介面）
4. 審核通過 → 寫入假 ERP（Postgres）

後續階段：料號對應（RAG + 向量資料庫）、發票／採購單比對、PII 遮蔽、Langfuse 成本與追蹤。

## 開發

```bash
cp .env.example .env          # 填入 OPENAI_API_KEY
docker compose up -d          # Postgres
poetry env use python3.12
poetry install
poetry run pytest
poetry run ruff check . && poetry run mypy src tests
```

## 合成發票

產生附標準答案的三聯式統一發票，給 eval 與手動測試用。每張輸出 `<id>.png`、`<id>.pdf` 與 `<id>.json`（標準答案：發票上印的欄位、注入的錯誤類型、預期觸發的送審原因）。

```bash
poetry run python -m doclens.synthetic --count 20 --seed 42
```

| 參數 | 預設 | 說明 |
| --- | --- | --- |
| `--count` | 20 | 發票張數 |
| `--seed` | 0 | 同一個 seed 產生的檔案完全相同 |
| `--out` | `data/synthetic` | 輸出目錄（不進版控） |
| `--error-ratio` | 0.5 | 注入錯誤的比例；有錯的發票平均分給 5 種錯誤：賣方統編檢查碼、品項小計、銷售額、總計、prompt injection（備註印上誘導模型的文字） |
| `--font` | `/System/Library/Fonts/STHeiti Medium.ttc` | CJK 字型路徑；非 macOS 需自行指定 |
