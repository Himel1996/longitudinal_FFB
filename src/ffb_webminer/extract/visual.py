"""Optional Playwright-based homepage visual extraction."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VisualExtraction:
    rendered_success: bool
    viewport_width: int
    viewport_height: int
    screenshot_path: str | None
    body_background_color: str | None
    header_background_color: str | None
    hero_background_color: str | None
    h1_text: str | None
    h1_font_family: str | None
    h1_font_size_px: float | None
    h1_font_weight: str | None
    h1_color: str | None
    computed_style_source: str | None
    css_stylesheet_count: int | None
    missing_asset_count: int | None
    visual_extraction_confidence: float | None
    visual_extraction_error: str | None
    dominant_colors_json: str | None


def extract_homepage_visuals(
    replay_url: str,
    screenshot_dir: str | Path,
    viewport_width: int = 1280,
    viewport_height: int = 800,
    cache_key: str | None = None,
) -> VisualExtraction:
    screenshot_dir = Path(screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return VisualExtraction(
            rendered_success=False,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            screenshot_path=None,
            body_background_color=None,
            header_background_color=None,
            hero_background_color=None,
            h1_text=None,
            h1_font_family=None,
            h1_font_size_px=None,
            h1_font_weight=None,
            h1_color=None,
            computed_style_source=None,
            css_stylesheet_count=None,
            missing_asset_count=None,
            visual_extraction_confidence=0.0,
            visual_extraction_error="playwright_not_installed",
            dominant_colors_json=None,
        )

    shot_path = screenshot_dir / f"{cache_key or 'page'}.png"
    missing_assets = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": viewport_width, "height": viewport_height})
            page.on("requestfailed", lambda req: None)
            page.goto(replay_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(shot_path), full_page=False)

            styles = page.evaluate(
                """() => {
                    const pickHeading = () => {
                        const h1 = document.querySelector('h1');
                        if (h1 && h1.innerText.trim()) return h1;
                        const candidates = [...document.querySelectorAll('h1,h2')].filter(
                            el => el.innerText.trim()
                        );
                        if (!candidates.length) return null;
                        return candidates.sort((a,b) => {
                            const sa = window.getComputedStyle(a).fontSize;
                            const sb = window.getComputedStyle(b).fontSize;
                            return parseFloat(sb) - parseFloat(sa);
                        })[0];
                    };
                    const heading = pickHeading();
                    const bodyStyle = window.getComputedStyle(document.body);
                    const header = document.querySelector('header');
                    const headerStyle = header ? window.getComputedStyle(header) : null;
                    const hero = document.querySelector('[class*="hero"], main section, .banner');
                    const heroStyle = hero ? window.getComputedStyle(hero) : null;
                    const headingStyle = heading ? window.getComputedStyle(heading) : null;
                    return {
                        bodyBg: bodyStyle.backgroundColor,
                        headerBg: headerStyle ? headerStyle.backgroundColor : null,
                        heroBg: heroStyle ? heroStyle.backgroundColor : null,
                        h1Text: heading ? heading.innerText.trim() : null,
                        h1Font: headingStyle ? headingStyle.fontFamily : null,
                        h1Size: headingStyle ? parseFloat(headingStyle.fontSize) : null,
                        h1Weight: headingStyle ? headingStyle.fontWeight : null,
                        h1Color: headingStyle ? headingStyle.color : null,
                        stylesheetCount: document.styleSheets.length,
                    };
                }"""
            )
            browser.close()

        confidence = 0.7 if styles.get("h1Text") else 0.4
        return VisualExtraction(
            rendered_success=True,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            screenshot_path=str(shot_path),
            body_background_color=styles.get("bodyBg"),
            header_background_color=styles.get("headerBg"),
            hero_background_color=styles.get("heroBg"),
            h1_text=styles.get("h1Text"),
            h1_font_family=styles.get("h1Font"),
            h1_font_size_px=styles.get("h1Size"),
            h1_font_weight=styles.get("h1Weight"),
            h1_color=styles.get("h1Color"),
            computed_style_source="playwright_getComputedStyle",
            css_stylesheet_count=styles.get("stylesheetCount"),
            missing_asset_count=missing_assets,
            visual_extraction_confidence=confidence,
            visual_extraction_error=None,
            dominant_colors_json=None,
        )
    except Exception as exc:
        logger.warning("Visual extraction failed for %s: %s", replay_url, exc)
        return VisualExtraction(
            rendered_success=False,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            screenshot_path=None,
            body_background_color=None,
            header_background_color=None,
            hero_background_color=None,
            h1_text=None,
            h1_font_family=None,
            h1_font_size_px=None,
            h1_font_weight=None,
            h1_color=None,
            computed_style_source=None,
            css_stylesheet_count=None,
            missing_asset_count=None,
            visual_extraction_confidence=0.0,
            visual_extraction_error=str(exc),
            dominant_colors_json=None,
        )
