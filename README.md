# Economic Agent System

Standalone ECC-style economic intelligence project with:

- Project-level `.claude` agent, skills, commands, and rules
- Python FastAPI backend
- RAG retrieval using Chroma vector store
- Deterministic trend engine for 1-6 month outlooks
- Data ingestion from PDF, news URL, and raw text

## Project Structure

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

## Features

1. Analyze corporate financial and macro context.
2. Retrieve evidence through vector search.
3. Run deterministic scoring:
   - Financial: 50%
   - Sentiment: 30%
   - Macro: 20%
4. Produce:
   - Summary
   - Signals
   - Score
   - Trend
   - Risks
   - Opportunities
   - Confidence

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set API key:

```bash
export OPENAI_API_KEY="your_api_key"
```

4. Run server:

```bash
uvicorn backend.main:app --reload --port 8000
```

## API Endpoints

- `POST /upload` ingest PDF, URL, or raw text into processed JSON + vector DB
- `POST /predict` run deterministic trend analysis
- `POST /ask` run RAG-backed question answering
- `GET /health` health check

## Example Requests

### Upload text source

```bash
curl -X POST http://localhost:8000/upload \
  -F "source_type=text" \
  -F "company=Acme Corp" \
  -F "sector=Manufacturing" \
  -F "text=Revenue increased 12 percent, costs increased 8 percent, and policy support expanded."
```

### Predict trend

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

### Ask a question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are key risks for Acme Corp in the next quarter?",
    "company": "Acme Corp",
    "sector": "Manufacturing"
  }'
```

## Notes

- This project intentionally does not modify repository-wide ECC core assets.
- All ECC configuration is local to `economic-agent/.claude/`.
