# Hệ Thống Economic Agent

Dự án phân tích kinh tế độc lập theo phong cách ECC với:

* Agent `.claude` ở cấp project
* Skills, commands và rules riêng
* Backend Python FastAPI
* Hệ thống RAG sử dụng Chroma Vector Store
* Trend Engine xác định xu hướng 1-6 tháng
* Data ingestion từ PDF, URL tin tức và văn bản thô

## Cấu Trúc Dự Án

```text
economic-agent/
├── .claude/
│   ├── agents/
│   ├── skills/
│   ├── commands/
│   └── rules/
├── backend/
│   ├── main.py
│   ├── trend_engine.py
│   ├── rag/
│   ├── ingestion/
│   └── services/
├── data/
│   ├── raw/
│   ├── processed/
│   └── vector/
├── requirements.txt
└── README.md
```

## Tính Năng

1. Phân tích tài chính doanh nghiệp và bối cảnh vĩ mô.
2. Truy xuất dữ liệu bằng vector search.
3. Chạy hệ thống deterministic scoring:

   * Tài chính: 50%
   * Sentiment: 30%
   * Vĩ mô: 20%
4. Sinh kết quả bao gồm:

   * Tóm tắt
   * Signals
   * Điểm số
   * Xu hướng
   * Rủi ro
   * Cơ hội
   * Confidence score

## Cài Đặt

### 1. Tạo môi trường ảo

```bash
python -m venv .venv
```

### 2. Kích hoạt virtual environment

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 3. Cài dependencies

```bash
pip install -r requirements.txt
```

### 4. Thiết lập API key

Windows PowerShell:

```bash
$env:OPENAI_API_KEY="your_api_key"
```

Linux/macOS:

```bash
export OPENAI_API_KEY="your_api_key"
```

### 5. Chạy server

```bash
uvicorn backend.main:app --reload --port 8000
```

## API Endpoints

* `POST /upload`
  Upload PDF, URL hoặc raw text vào processed JSON và vector database.

* `POST /predict`
  Chạy phân tích xu hướng deterministic.

* `POST /ask`
  Hỏi đáp bằng RAG retrieval.

* `GET /health`
  Kiểm tra trạng thái hệ thống.

## Ví Dụ Request

### Upload dữ liệu văn bản

```bash
curl -X POST http://localhost:8000/upload \
  -F "source_type=text" \
  -F "company=Acme Corp" \
  -F "sector=Manufacturing" \
  -F "text=Revenue increased 12 percent, costs increased 8 percent, and policy support expanded."
```

### Phân tích xu hướng

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Acme Corp",
    "financial_signals": ["revenue_up", "cost_up"],
    "sentiment_signals": ["positive_news"],
    "macro_signals": ["policy_support", "interest_rate_down"]
  }'
```

### Đặt câu hỏi

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are key risks for Acme Corp in the next quarter?",
    "company": "Acme Corp",
    "sector": "Manufacturing"
  }'
```

## Ghi Chú

* Dự án này không chỉnh sửa các ECC core assets ở cấp repository.
* Toàn bộ cấu hình ECC được đặt riêng trong:

```text
economic-agent/.claude/
```
