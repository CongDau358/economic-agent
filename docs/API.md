# Economic Agent — API Reference

Base URL: `http://localhost:8000`  
Auth header: `X-API-Key: <your-key>` (bắt buộc trừ `/health`)

---

## GET /health

Kiểm tra trạng thái server.  
**Không cần auth.**

**Response:**
```json
{
  "status": "ok",
  "version": "1.1.0",
  "auth_enabled": true,
  "cache": "memory",
  "rate_limiting": true,
  "jobs": { "total": 3, "done": 2, "pending": 1 }
}
```

---

## POST /upload

Nạp dữ liệu vào knowledge base. Xử lý **async** — trả về `job_id` ngay.

**Form data:**

| Field | Type | Required | Mô tả |
|-------|------|----------|-------|
| `source_type` | string | ✓ | `pdf` / `excel` / `news` / `text` |
| `company` | string | ✓ | Tên công ty |
| `sector` | string | ✓ | Ngành |
| `text` | string | — | Văn bản thô (khi `source_type=text`) |
| `url` | string | — | URL tin tức (khi `source_type=news`) |
| `file` | file | — | File PDF/Excel/Word |

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Ingestion queued — poll /jobs/{job_id} để theo dõi"
}
```

**Rate limit:** 10 req/min/IP

---

## GET /jobs

Danh sách ingestion jobs.

**Query params:**

| Param | Mô tả |
|-------|-------|
| `company` | Filter theo tên công ty |
| `status` | `pending` / `running` / `done` / `failed` |
| `limit` | Số lượng tối đa (default 50, max 200) |

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "...",
      "status": "done",
      "company": "Vinamilk",
      "source_type": "pdf",
      "created_at": 1700000000.0,
      "updated_at": 1700000030.0,
      "result": { "chunk_count": 42 },
      "error": null
    }
  ],
  "count": 1
}
```

---

## GET /jobs/{job_id}

Chi tiết một job.

**Response khi done:**
```json
{
  "job_id": "...",
  "status": "done",
  "company": "Vinamilk",
  "source_type": "pdf",
  "result": {
    "chunk_count": 42,
    "embedded_count": 42,
    "validation": { "valid_chunk_count": 42, "warnings": [] }
  }
}
```

**Response khi failed:**
```json
{
  "job_id": "...",
  "status": "failed",
  "error": "No extractable content found in PDF"
}
```

---

## POST /predict

Phân tích xu hướng bằng deterministic scoring.

**Body:**
```json
{
  "company": "Vinamilk",
  "ticker": "VNM.HM",
  "financial_signals": ["revenue_up", "margin_stable", "eps_beat"],
  "sentiment_signals": ["analyst_upgrade", "positive_news"],
  "macro_signals": ["policy_support", "interest_rate_down"],
  "enrich_with_market_data": false
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `company` | string | Tên công ty (bắt buộc) |
| `ticker` | string | Ticker chứng khoán, VD: `VNM.HM`, `VIC.HM` |
| `financial_signals` | list | Tín hiệu tài chính (xem bảng signals) |
| `sentiment_signals` | list | Tín hiệu sentiment |
| `macro_signals` | list | Tín hiệu vĩ mô |
| `enrich_with_market_data` | bool | Tự động lấy data từ yfinance + FRED |

**Response:**
```json
{
  "company": "Vinamilk",
  "status": "OK",
  "score": 0.724,
  "trend": {
    "short_term": "bullish",
    "near_term": "bullish"
  },
  "confidence": 0.87,
  "executive_summary": "Vinamilk cho thấy xu hướng tăng trưởng ngắn hạn...",
  "financial_signals": { "score": 0.6, "inputs": ["revenue_up", "eps_beat"] },
  "sentiment_signals": { "score": 0.4, "inputs": ["analyst_upgrade"] },
  "macro_signals":     { "score": 0.3, "inputs": ["policy_support"] },
  "scenarios": { "bull": 0.844, "base": 0.724, "bear": 0.574 },
  "risks": ["cost_up"],
  "opportunities": ["revenue_up", "eps_beat"],
  "assumptions": ["Trọng số: Tài chính 50%, Sentiment 30%, Vĩ mô 20%"],
  "warnings": [],
  "_cached": false
}
```

**Rate limit:** 30 req/min/IP

### Signal Reference

**Financial signals:**
`revenue_up` · `revenue_down` · `profit_up` · `profit_down` · `margin_expansion` · `margin_compression` · `eps_beat` · `eps_miss` · `cash_flow_positive` · `cash_burn` · `debt_reduction` · `debt_increase` · `guidance_raised` · `guidance_lowered` · `dividend_increase` · `dividend_cut` · `buyback` · `impairment` · `cost_up` · `cost_down`

**Sentiment signals:**
`positive_news` · `negative_news` · `analyst_upgrade` · `analyst_downgrade` · `insider_buying` · `insider_selling` · `institutional_buying` · `short_interest_high` · `media_positive` · `media_negative` · `regulatory_concern` · `litigation_risk` · `management_change` · `management_positive` · `esg_positive` · `esg_negative`

**Macro signals:**
`policy_support` · `interest_rate_down` · `interest_rate_stable` · `interest_rate_high` · `inflation_stable` · `inflation_elevated` · `gdp_growth` · `gdp_contraction` · `credit_easing` · `credit_tightening` · `fx_favorable` · `fx_headwind` · `commodity_cost_up` · `commodity_cost_down` · `sector_tailwind` · `sector_headwind` · `low_volatility` · `high_volatility` · `geopolitical_risk`

---

## POST /ask

Hỏi đáp dựa trên knowledge base (RAG + Hybrid retrieval).

**Body:**
```json
{
  "question": "Rủi ro chính của Vinamilk trong quý tới là gì?",
  "company": "Vinamilk",
  "sector": "Consumer Staples",
  "year": "2024",
  "retrieval_mode": "hybrid",
  "top_k": 5
}
```

| Field | Mô tả |
|-------|-------|
| `question` | Câu hỏi (min 3 ký tự) |
| `company` | Filter theo công ty |
| `sector` | Filter theo ngành |
| `year` | Filter theo năm |
| `retrieval_mode` | `hybrid` / `dense` / `sparse` |
| `top_k` | Số chunks retrieve (1–10, default 4) |

**Response:**
```json
{
  "answer": "Các rủi ro chính bao gồm...",
  "citations": [
    { "source": "Q3_2024_Report.pdf", "score": 0.91 }
  ],
  "confidence": 0.84,
  "_cached": false
}
```

**Rate limit:** 20 req/min/IP

---

## WebSocket /ws/analyze

Streaming real-time analysis.

**Connect:** `ws://localhost:8000/ws/analyze`

**Client gửi:**
```json
{
  "company": "Vinamilk",
  "ticker": "VNM.HM",
  "question": "Phân tích tổng thể"
}
```

**Server stream:**
```json
{"type": "status", "msg": "Đang truy xuất evidence..."}
{"type": "status", "msg": "Tìm thấy 5 evidence chunks"}
{"type": "status", "msg": "Đang chạy trend scoring..."}
{"type": "result", "data": { "company": "...", "rag": {}, "trend": {}, "market": {} }}
{"type": "done"}
```

**Error event:**
```json
{"type": "error", "msg": "Mô tả lỗi"}
```

---

## Error Format

Tất cả lỗi trả về JSON chuẩn:

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Dữ liệu đầu vào không hợp lệ",
  "details": [
    { "field": "body → company", "msg": "field required", "type": "missing" }
  ]
}
```

| HTTP | error code | Nguyên nhân |
|------|-----------|-------------|
| 401 | `UNAUTHORIZED` | Thiếu `X-API-Key` header |
| 403 | `FORBIDDEN` | API key không hợp lệ |
| 404 | `NOT_FOUND` | Job ID không tồn tại |
| 422 | `VALIDATION_ERROR` | Body không đúng format |
| 429 | `RATE_LIMITED` | Vượt giới hạn request |
| 500 | `INTERNAL_SERVER_ERROR` | Lỗi server |