"""Tests for multi-stage text extraction."""

from __future__ import annotations

from pathlib import Path

from ffb_webminer.extract.html_preprocess import detect_redirect_targets, strip_wayback_dom
from ffb_webminer.extract.text import extract_text

HTML_DIR = Path(__file__).resolve().parents[1] / "data" / "interim" / "html"


def test_strip_wayback_removes_scripts():
    html = b"""<html><head>
    <script src="https://web-static.archive.org/_static/js/wombat.js"></script>
    </head><body><p>Company content here with enough words to extract.</p></body></html>"""
    cleaned = strip_wayback_dom(html)
    assert b"wombat.js" not in cleaned
    assert b"Company content" in cleaned


def test_peter_lacke_visible_dom_extracts_content():
    path = HTML_DIR / "48d958fac7cee47cacf011e6156c6f85d1ecc004f65ab9369a0c38fad12dde7c.html"
    if not path.exists():
        return
    html = path.read_bytes()
    result = extract_text(html)
    assert result.main_text
    assert result.word_count > 25
    assert "Lack" in result.main_text or "Losungen" in result.main_text or "Lösungen" in result.main_text


def test_msf_intro_detects_redirect():
    path = HTML_DIR / "b0597544833bcdcb292083362db92f41453292ee880d4b65d3b7d482f19588e2.html"
    if not path.exists():
        return
    targets = detect_redirect_targets(path.read_bytes())
    assert any("entry.html" in t for t in targets)
