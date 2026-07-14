"""Prepare archived HTML for extraction (Wayback strip, redirects, frames)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ffb_webminer.archive.wayback_url import build_replay_url, parse_wayback_url, unwrap_wayback_url

if TYPE_CHECKING:
    from ffb_webminer.crawl.fetcher import PageFetcher

logger = logging.getLogger(__name__)

WAYBACK_SCRIPT_RE = re.compile(
    r"<script[^>]*(?:web-static\.archive\.org|__wm\.|wombat\.js|ruffle)[^>]*>.*?</script>",
    re.IGNORECASE | re.DOTALL,
)
JS_REDIRECT_RE = re.compile(
    r"""window\.location\s*=\s*['"]([^'"]+)['"]"""
    r"""|MM_checkPlugin\([^,]+,[^,]+,['"]([^'"]+)['"]"""
    r"""|location\.href\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
META_REFRESH_RE = re.compile(
    r"""content\s*=\s*['"]\s*\d+\s*;\s*(?:url\s*=\s*)?([^'"]+)""",
    re.IGNORECASE,
)
MAX_FRAME_FETCHES = 8
MAX_REDIRECT_HOPS = 3


@dataclass
class PreprocessResult:
    html: bytes
    expanded_frames: bool = False
    followed_redirect: bool = False
    redirect_targets: list[str] = field(default_factory=list)
    frame_sources: list[str] = field(default_factory=list)


def strip_wayback_dom(html: bytes) -> bytes:
    """Remove Wayback toolbar scripts/styles from HTML before extraction."""
    text = html.decode("utf-8", errors="replace")
    text = WAYBACK_SCRIPT_RE.sub("", text)
    soup = BeautifulSoup(text, "lxml")
    for tag in soup.find_all(["script", "link", "style"]):
        src = tag.get("src") or tag.get("href") or ""
        if any(
            marker in str(src).lower()
            for marker in ("web-static.archive.org", "banner-styles", "iconochive")
        ):
            tag.decompose()
    for tag in soup.find_all(id=re.compile(r"^wm-", re.I)):
        tag.decompose()
    return soup.encode("utf-8")


def detect_redirect_targets(html: bytes) -> list[str]:
    """Find JS or meta-refresh redirect targets in archived HTML."""
    text = html.decode("utf-8", errors="replace")
    targets: list[str] = []
    for m in JS_REDIRECT_RE.finditer(text):
        for g in m.groups():
            if g and g not in targets:
                targets.append(g)
    for tag in BeautifulSoup(text, "lxml").find_all("meta", attrs={"http-equiv": re.compile("refresh", re.I)}):
        content = tag.get("content") or ""
        rm = META_REFRESH_RE.search(content)
        if rm and rm.group(1) not in targets:
            targets.append(rm.group(1).strip())
    onload = re.search(r'onload\s*=\s*"([^"]+)"', text, re.I)
    if onload:
        for m in JS_REDIRECT_RE.finditer(onload.group(1)):
            for g in m.groups():
                if g and g not in targets:
                    targets.append(g)
    return targets


def resolve_archived_child_url(replay_url: str, child_path: str) -> str:
    """Resolve a frame/redirect path against a Wayback replay URL."""
    parsed = parse_wayback_url(replay_url)
    if not parsed:
        return child_path
    ts, modifier, original = parsed
    if child_path.startswith("/web/"):
        return f"https://web.archive.org{child_path}"
    if child_path.startswith(("http://", "https://")):
        original_child = unwrap_wayback_url(child_path)
        return build_replay_url(original_child, ts, modifier or "id_")
    base = original if original.endswith("/") else original.rsplit("/", 1)[0] + "/"
    joined = urljoin(base, child_path)
    return build_replay_url(joined, ts, modifier or "id_")


def _frame_replay_urls(html: bytes, replay_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    for tag in soup.find_all(["frame", "iframe"]):
        src = (tag.get("src") or "").strip()
        if not src or src.startswith("javascript:"):
            continue
        resolved = resolve_archived_child_url(replay_url, src)
        if resolved not in urls:
            urls.append(resolved)
    return urls[:MAX_FRAME_FETCHES]


def _fetch_archived(fetcher: PageFetcher, archived_url: str):
    """Fetch using PageFetcher whether URL is replay or original."""
    parsed = parse_wayback_url(archived_url)
    if parsed:
        ts, _, original = parsed
        return fetcher.fetch(original, archive_timestamp=ts, use_cache=True)
    return fetcher.fetch(archived_url, use_cache=True)


def expand_archived_html(
    html: bytes,
    replay_url: str,
    fetcher: PageFetcher | None = None,
) -> PreprocessResult:
    """
    Strip Wayback chrome, follow JS/meta redirects, and inline frame content.

    When a fetcher is provided, child frames and redirect targets are fetched
    and merged into a synthetic document for downstream extractors.
    """
    cleaned = strip_wayback_dom(html)
    result = PreprocessResult(html=cleaned)

    if not fetcher or not replay_url:
        return result

    # Follow redirect chain (e.g. MSF intro -> entry.html)
    current_html = cleaned
    current_replay = replay_url
    for _ in range(MAX_REDIRECT_HOPS):
        targets = detect_redirect_targets(current_html)
        if not targets:
            break
        # Prefer non-flash HTML targets
        target = next((t for t in targets if not t.endswith(".swf")), targets[0])
        child_url = resolve_archived_child_url(current_replay, target)
        fetch = _fetch_archived(fetcher, child_url)
        if not fetch.content:
            break
        result.followed_redirect = True
        result.redirect_targets.append(target)
        current_html = strip_wayback_dom(fetch.content)
        current_replay = fetch.wayback_replay_url or child_url

    # Expand framesets
    frame_urls = _frame_replay_urls(current_html, current_replay)
    if not frame_urls:
        result.html = current_html
        return result

    merged_parts: list[str] = []
    for frame_url in frame_urls:
        fetch = _fetch_archived(fetcher, frame_url)
        if not fetch.content:
            continue
        frame_html = strip_wayback_dom(fetch.content)
        soup = BeautifulSoup(frame_html, "lxml")
        body = soup.body.get_text("\n", strip=True) if soup.body else ""
        if body:
            merged_parts.append(body)
        result.frame_sources.append(frame_url)

    if merged_parts:
        wrapper = BeautifulSoup(
            "<html><head></head><body></body></html>",
            "lxml",
        )
        wrapper.body.append(
            BeautifulSoup(
                "".join(f"<div class='frame-content'>{p}</div>" for p in merged_parts),
                "lxml",
            )
        )
        result.html = wrapper.encode("utf-8")
        result.expanded_frames = True
    else:
        result.html = current_html

    return result
