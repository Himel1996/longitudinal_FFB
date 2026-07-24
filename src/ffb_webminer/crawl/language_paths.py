"""Path-language heuristics for crawl prioritization and corpus language handling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from ffb_webminer.archive.wayback_url import unwrap_wayback_url

GERMAN_PATH_MARKERS = (
    "/de/",
    "/de-de/",
    "/deutsch/",
    "/ger/",
    "/de.",
)
FOREIGN_PATH_MARKERS = (
    "/en/",
    "/en-us/",
    "/en-gb/",
    "/english/",
    "/fr/",
    "/es/",
    "/it/",
    "/pl/",
    "/ru/",
    "/zh/",
    "/cn/",
    "/nl/",
    "/pt/",
)
FOREIGN_QUERY_LANGS = frozenset({"en", "fr", "es", "it", "pl", "ru", "zh", "cn", "nl", "pt", "english"})
GERMAN_QUERY_LANGS = frozenset({"de", "ger", "deutsch", "german"})


@dataclass
class PathLanguageHint:
    path_language_hint: str
    path_language_priority: str
    language_path_reason: str


def infer_path_language(url: str | None) -> PathLanguageHint:
    raw = unwrap_wayback_url(str(url or ""))
    parsed = urlparse(raw)
    path = (parsed.path or "/").lower()
    if not path.startswith("/"):
        path = "/" + path
    # ensure trailing slash form for marker checks
    path_check = path if path.endswith("/") else path + "/"

    query = parse_qs(parsed.query)
    lang_vals = []
    for key in ("lang", "language", "locale"):
        lang_vals.extend(v.lower() for v in query.get(key, []))

    for marker in GERMAN_PATH_MARKERS:
        if marker in path_check or path_check.startswith(marker.rstrip("/") + ".") or path_check == marker:
            return PathLanguageHint("de", "preferred_german", f"path:{marker.strip('/')}")
    if any(v in GERMAN_QUERY_LANGS for v in lang_vals):
        return PathLanguageHint("de", "preferred_german", "query:lang_de")

    for marker in FOREIGN_PATH_MARKERS:
        if marker in path_check:
            code = marker.strip("/").split("-")[0]
            return PathLanguageHint(code, "foreign_language_deprioritized", f"path:{marker.strip('/')}")
    if any(v in FOREIGN_QUERY_LANGS for v in lang_vals):
        code = next(v for v in lang_vals if v in FOREIGN_QUERY_LANGS)
        return PathLanguageHint(code[:2], "foreign_language_deprioritized", f"query:lang_{code}")

    # root / unmarked German-primary sites
    if path in {"/", ""} or re.fullmatch(r"/index\.(html?|php)", path):
        return PathLanguageHint("unknown", "preferred_german", "root_or_index")

    return PathLanguageHint("unknown", "neutral_or_unknown", "unmarked_path")
