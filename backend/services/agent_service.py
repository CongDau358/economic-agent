from __future__ import annotations

import os
from typing import Dict, List

from openai import OpenAI


SYSTEM_PROMPT = """You are a financial and economic analyst.

Rules:
- Answer ONLY using provided context
- If data is insufficient, say "insufficient data"
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


def build_rag_answer(question: str, contexts: List[Dict[str, str]]) -> Dict[str, object]:
    if not contexts:
        return {
            "summary": "insufficient data",
            "signals": {"financial": [], "sentiment": [], "macro": []},
            "score": {},
            "trend": "INSUFFICIENT_DATA",
            "risks": [],
            "opportunities": [],
            "confidence": {
                "value": 0.25,
                "reasoning": "No retrieved context available for answering the question.",
            },
            "answer": "insufficient data",
            "evidence": [],
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

    return {
        "summary": "RAG-based answer generated from retrieved context and LLM reasoning.",
        "signals": {"financial": [], "sentiment": [], "macro": []},
        "score": {},
        "trend": "NEUTRAL",
        "risks": [],
        "opportunities": [],
        "confidence": {
            "value": 0.7 if llm_answer != "insufficient data" else 0.35,
            "reasoning": (
                "LLM response grounded by retrieved context."
                if llm_answer != "insufficient data"
                else "LLM could not produce grounded output from available context."
            ),
        },
        "answer": llm_answer if question else "insufficient data",
        "evidence": evidence,
    }
