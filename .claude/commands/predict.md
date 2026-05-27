---
description: Predict short-term and near-term economic trend using deterministic scoring, evidence quality assessment, and confidence calibration.
---

# /predict

## Purpose

Phân tích xu hướng ngắn hạn (1–3 tháng) và trung hạn (3–6 tháng) cho một công ty hoặc ngành.
Kết quả bao gồm trend direction, confidence band, risks, opportunities và citations đầy đủ.

## Maps To

- Agent: `economic-intelligence-agent`
- Skills (theo thứ tự bắt buộc):
  1. `evidence-quality-assessment` — chạy trước, loại bỏ chunks không đủ tin cậy
  2. `signal-extraction` — trích xuất signals từ evidence đã qua quality gate
  3. `macro-context-analysis` — overlay vĩ mô nếu có macro chunks
  4. `trend-analysis` — TrendEngine deterministic scoring
  5. `confidence-calibration` — tính confidence với penalty table đầy đủ
  6. `sector-comparison` — so sánh peer nếu corpus có dữ liệu peer
- Rules:
  - `retrieval-governance-rules.md`
  - `financial-signal-rules.md`
  - `multi-period-analysis-rules.md`
  - `output-completeness-rules.md`
  - `agent-scope-rules.md`
  - `hallucination-prevention.md`
  - `conflict-resolution-rules.md`

## Execution Pipeline

### Bước 1 — Validate Input
- Xác nhận `company` và `signals` có trong request.
- Normalize tên công ty, ticker, sector alias.
- Kiểm tra signal names có trong FINANCIAL_SIGNALS / SENTIMENT_SIGNALS / MACRO_SIGNALS registry.
- Tín hiệu không nhận dạng được → ghi vào `unknown_signals`, không gây lỗi.

### Bước 2 — Retrieve Evidence
- Hybrid retrieval với filters: `company`, `sector`, `year`, `source_type`.
- `top_k` = `settings.rag_top_k` (mặc định 5), rerank xuống `retrieval_rerank_top_n` (mặc định 4).
- Áp dụng blended score: semantic 0.50 · metadata 0.20 · source_trust 0.20 · recency 0.10.
- Enrichment từ yfinance / FRED nếu API keys có — gắn tag `source: market_data_enrichment`.

### Bước 3 — Evidence Quality Assessment (skill: `evidence-quality-assessment`)
- Gán trust tier cho từng chunk: HIGH / MEDIUM / LOW / EXCLUDED.
- Áp recency decay theo `evidence_max_chunk_age_days`.
- Đánh giá coverage: adequate / marginal / insufficient.
- Loại bỏ EXCLUDED chunks trước khi tiếp tục.
- Nếu coverage = insufficient → trả `INSUFFICIENT_DATA` ngay, dừng pipeline.

### Bước 4 — Signal Extraction (skill: `signal-extraction`)
- Map từng chunk sang signal registry — chỉ explicit statements, không infer.
- De-duplicate: nhiều chunks cùng signal → giữ highest-trust.
- Flag conflicts: cùng signal có polarity trái chiều → ghi `conflicts[]`.
- Coverage ratio = signals có evidence / tổng registry.
- Nếu coverage ratio < `signal_min_coverage` → thêm warning, không block.

### Bước 5 — Macro Overlay (skill: `macro-context-analysis`)
- Chỉ chạy khi có macro chunks trong retrieved evidence.
- Map macro signals → sector sensitivity (high / medium / low).
- Tính `macro_score` và `amplifier_effect`.
- Nếu macro mâu thuẫn tài chính → `conflicts[]`, giảm confidence.

### Bước 6 — Trend Scoring (skill: `trend-analysis` / TrendEngine)
- Tính weighted composite: financial × 0.50 + sentiment × 0.30 + macro × 0.20.
- Short-term trend: `_trend_with_band(composite, signal_neutral_band)`.
- Near-term trend: `_trend_with_band(composite × 0.7 + macro × 0.3, signal_neutral_band)`.
- Scenarios: bull / base / bear từng tập signals.

### Bước 7 — Confidence Calibration (skill: `confidence-calibration`)
- Base = avg(chunk quality) × retrieval relevance.
- Trừ penalties: low_source (−0.10–0.20), stale (−0.05–0.15), conflict (−0.15–0.25), sparse (−0.10–0.20).
- Band: HIGH ≥ `confidence_high_threshold` · MEDIUM · LOW ≥ `confidence_min_proceed` · INSUFFICIENT.
- Nếu INSUFFICIENT → dừng, không sinh trend/risk/opportunity.

### Bước 8 — Sector Comparison (skill: `sector-comparison`, nếu peer data có)
- Retrieve peer chunks cùng sector, khác company.
- Tính relative position: primary vs peer average.
- Gắn `relative_position` vào output nếu đủ dữ liệu.

### Bước 9 — Build Output
- Cắt `risks[:output_max_risks]`, `opportunities[:output_max_opportunities]`.
- Cắt `evidence_snapshot` text theo `output_evidence_preview_chars`.
- Gắn citations: `source_type | company | period | chunk_id`.
- Điền đầy đủ mandatory fields — dùng `[]` cho list rỗng, không dùng `null`.

### Bước 10 — Scope Check (rule: `agent-scope-rules.md`)
- Không có investment advice, price target, buy/sell recommendation.
- Nếu output có dấu hiệu vi phạm scope → rephrase trước khi trả về.

## Output Contract

```json
{
  "company": "string",
  "status": "OK | INSUFFICIENT_DATA",
  "score": 0.0,
  "trend": {
    "short_term": "bullish | bearish | neutral | INSUFFICIENT_DATA",
    "near_term":  "bullish | bearish | neutral | INSUFFICIENT_DATA"
  },
  "financial_score":  0.0,
  "sentiment_score":  0.0,
  "macro_score":      0.0,
  "scenarios":        {},
  "risks":            [],
  "opportunities":    [],
  "confidence": {
    "value":    0.0,
    "band":     "HIGH | MEDIUM | LOW | INSUFFICIENT",
    "reasoning": "string",
    "warnings": []
  },
  "assumptions":   [],
  "citations":     [],
  "unknown_signals": { "financial": [], "sentiment": [], "macro": [] },
  "retrieval_quality": { "status": "string", "chunk_count": 0, "warnings": [] }
}
```

## Configurable Parameters (từ .env)

| Tham số | Ảnh hưởng bước |
|---------|---------------|
| `CONFIDENCE_MIN_PROCEED` | Bước 7 — ngưỡng INSUFFICIENT |
| `CONFIDENCE_HIGH_THRESHOLD` | Bước 7 — ngưỡng HIGH band |
| `EVIDENCE_MIN_CHUNKS_STRATEGIC` | Bước 3 — coverage assessment |
| `EVIDENCE_MAX_CHUNK_AGE_DAYS` | Bước 3 — recency decay |
| `SIGNAL_CONFLICT_PENALTY` | Bước 7 — penalty per conflict |
| `SIGNAL_MIN_COVERAGE` | Bước 4 — coverage warning threshold |
| `SIGNAL_NEUTRAL_BAND` | Bước 6 — neutral zone |
| `RETRIEVAL_RERANK_TOP_N` | Bước 2 — chunks sau rerank |
| `OUTPUT_MAX_RISKS` | Bước 9 — cắt risks list |
| `OUTPUT_MAX_OPPORTUNITIES` | Bước 9 — cắt opportunities list |
