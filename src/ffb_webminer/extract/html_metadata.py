"""HTML metadata extraction."""

from __future__ import annotations

import json
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class HtmlMetadata:
    document_title: str | None
    meta_description: str | None
    meta_keywords: str | None
    html_lang: str | None
    canonical_url: str | None
    og_title: str | None
    og_description: str | None
    og_site_name: str | None
    h1_text: str | None
    h2_text: str | None
    headings_json: str | None


def _text_join(elements) -> str | None:
    texts = [e.get_text(" ", strip=True) for e in elements if e.get_text(strip=True)]
    return " | ".join(texts) if texts else None


def extract_metadata(html: bytes) -> HtmlMetadata:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    headings = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            t = h.get_text(" ", strip=True)
            if t:
                headings.append({"level": level, "text": t})
    return HtmlMetadata(
        document_title=title_tag.get_text(strip=True) if title_tag else None,
        meta_description=_meta(soup, "description"),
        meta_keywords=_meta(soup, "keywords"),
        html_lang=soup.html.get("lang") if soup.html else None,
        canonical_url=_canonical(soup),
        og_title=_og(soup, "title"),
        og_description=_og(soup, "description"),
        og_site_name=_og(soup, "site_name"),
        h1_text=_text_join(soup.find_all("h1")),
        h2_text=_text_join(soup.find_all("h2")),
        headings_json=json.dumps(headings, ensure_ascii=False) if headings else None,
    )


def _meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    return tag.get("content") if tag and tag.get("content") else None


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", property=f"og:{prop}")
    return tag.get("content") if tag and tag.get("content") else None


def _canonical(soup: BeautifulSoup) -> str | None:
    tag = soup.find("link", rel="canonical")
    return tag.get("href") if tag and tag.get("href") else None
