from __future__ import annotations

import os
from typing import Dict, List

from openai import OpenAI


SYSTEM_PROMPT = """You are a financial and economic analyst.

Retrieval governance (non-negotiable):
- Retrieval quality outweighs answer length; prefer short, grounded answers.
- Answer ONLY using provided context; never invent metrics, companies, or events.
- If data is insufficient, respond exactly: insufficient data
- Do not make unsupported financial claims.
- When context is low-trust or sparse, keep claims minimal and factual.
- Be concise and structured"""


def generate_llm_response(query: str, context: str) -> str:
    if not context.strip():
        return "insufficient data"

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return "insufficient data"

    client = OpenAI(api_key=api_key)
    user_prompt = f"""Context:
{context}

Question:
{query}"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        return content or "insufficient data"
    except Exception:
        return "insufficient data"


def build_rag_answer(
    question: str,
    contexts: List[Dict[str, str]],
    *,
    retrieval_assessment: Dict[str, object] | None = None,
) -> Dict[str, object]:
    assessment = retrieval_assessment or {}
    warnings = list(assessment.get("warnings") or [])
    band = str(assessment.get("band") or "INSUFFICIENT")
    status = str(assessment.get("status") or "INSUFFICIENT_DATA")
    conf_value = float(assessment.get("value") or 0.25)
    conf_reasoning = str(
        assessment.get("reasoning")
        or "No retrieved context available for answering the question."
    )

    if not contexts or status == "INSUFFICIENT_DATA":
        return {
            "summary": "insufficient data",
            "signals": {"financial": [], "sentiment": [], "macro": []},
            "score": {},
            "trend": "INSUFFICIENT_DATA",
            "risks": [],
            "opportunities": [],
            "confidence": {
                "value": conf_value,
                "band": "INSUFFICIENT",
                "reasoning": conf_reasoning,
                "warnings": warnings,
            },
            "retrieval_quality": {
                "status": "INSUFFICIENT_DATA",
                "chunk_count": int(assessment.get("chunk_count") or 0),
                "warnings": warnings,
            },
            "answer": "insufficient data",
            "evidence": [],
            "citations": [],
        }

    evidence = [
        {
            "text": c["text"][:400],
            "source_type": c.get("source_type", "unknown"),
            "company": c.get("company", "unknown"),
            "sector": c.get("sector", "unknown"),
        }
        for c in contexts
    ]
    retrieved_context = "\n\n".join(
        f"[{idx}] source_type={row.get('source_type', 'unknown')}, "
        f"company={row.get('company', 'unknown')}, sector={row.get('sector', 'unknown')}\n"
        f"{row.get('text', '')[:1000]}"
        for idx, row in enumerate(contexts, start=1)
    )
    llm_answer = generate_llm_response(query=question, context=retrieved_context)

    if llm_answer == "insufficient data":
        conf_value = min(conf_value, 0.35)
        band = "INSUFFICIENT"

    citations = [
        f"{e.get('source_type', 'unknown')} | {e.get('company', 'unknown')} | {e.get('sector', 'unknown')}"
        for e in evidence
    ]

    return {
        "summary": (
            "RAG-based answer generated from governed retrieval."
            if llm_answer != "insufficient data"
            else "insufficient data"
        ),
        "signals": {"financial": [], "sentiment": [], "macro": []},
        "score": {},
        "trend": "NEUTRAL" if llm_answer != "insufficient data" else "INSUFFICIENT_DATA",
        "risks": [],
        "opportunities": [],
        "confidence": {
            "value": conf_value if llm_answer != "insufficient data" else min(conf_value, 0.35),
            "band": band,
            "reasoning": conf_reasoning,
            "warnings": warnings,
        },
        "retrieval_quality": {
            "status": status,
            "chunk_count": int(assessment.get("chunk_count") or len(contexts)),
            "trusted_chunk_count": int(assessment.get("trusted_chunk_count") or 0),
            "warnings": warnings,
        },
        "answer": llm_answer if question else "insufficient data",
        "evidence": evidence,
        "citations": citations,
    }
