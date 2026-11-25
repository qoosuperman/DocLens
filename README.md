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
