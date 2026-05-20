from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Optional
from urllib.parse import urlparse

import requests

from .constants import SOCIAL_MAX_CHARS

_DATE_META_RE = re.compile(
    r'(?:published|date|time)[\"\']?\s*(?:content|datetime)=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class ExtractedArticle:
    title: str
    body: str
    publisher: str
    publication_date: str
    url: str
    content_type: str


def _strip_html(html: str) -> str:
    text = unescape(_TAG_RE.sub(" ", html))
    return _WS_RE.sub(" ", text).strip()


def _publisher_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or "unknown"


def _parse_publication_date(html: str) -> str:
    match = _DATE_META_RE.search(html)
    if match:
        return match.group(1).strip()[:32]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return _strip_html(m.group(1))[:300]
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return _strip_html(m.group(1))[:300]
    return ""


def _extract_body(html: str) -> str:
    try:
        from bs4 import BeautifulSoup  # noqa: PLC0415

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        article = soup.find("article")
        if article:
            text = article.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text[:12000]
        paragraphs = [
            p.get_text(strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) > 40
        ]
        if paragraphs:
            return "\n\n".join(paragraphs)[:12000]
        text = soup.get_text(separator="\n", strip=True)
        return text[:12000]
    except ImportError:
        pass

    blocks = re.findall(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
    if blocks:
        joined = "\n\n".join(_strip_html(b) for b in blocks if _strip_html(b))
        if len(joined) > 200:
            return joined[:12000]
    return _strip_html(html)[:12000]


def extract_from_url(url: str) -> ExtractedArticle:
    response = requests.get(
        url,
        timeout=15,
        headers={"User-Agent": "economic-agent/1.0"},
    )
    response.raise_for_status()
    html = response.text
    title = _extract_title(html)
    body = _extract_body(html)
    publisher = _publisher_from_url(url)
    og_site = re.search(
        r'property=["\']og:site_name["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if og_site:
        publisher = og_site.group(1).strip() or publisher
    return ExtractedArticle(
        title=title,
        body=body,
        publisher=publisher,
        publication_date=_parse_publication_date(html),
        url=url,
        content_type="news_article",
    )


def extract_from_text(
    text: str,
    *,
    title: str = "",
    publisher: str = "social",
    publication_date: Optional[str] = None,
) -> ExtractedArticle:
    normalized = text.replace("\r\n", "\n").strip()
    content_type = "social_post" if len(normalized) <= SOCIAL_MAX_CHARS else "news_article"
    return ExtractedArticle(
        title=title or normalized[:120],
        body=normalized,
        publisher=publisher,
        publication_date=publication_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        url="",
        content_type=content_type,
    )
