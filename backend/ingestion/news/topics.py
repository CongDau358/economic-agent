from __future__ import annotations

from typing import List

from .constants import TOPIC_KEYWORDS


def detect_topics(text: str, industry: str = "") -> List[str]:
    haystack = f"{text}\n{industry}".lower()
    found: List[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            found.append(topic)
    if industry.strip() and "industry" not in found:
        found.append("industry")
    return found or ["general"]
