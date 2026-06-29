"""
Meta Ads Library — Playwright scraper for ad copy text only.
Video download is technically impossible (session-bound CDN URLs, JS-lazy rendering).
We extract ad text, advertiser name, and filter for VIDEO media_type.
"""
import asyncio
import time
from backend.ingestion.base import ContentItem, video_engagement
from backend.voc.categories import CATEGORIES


_META_ADS_URL = "https://www.facebook.com/ads/library/"


async def _scrape_meta_async(keywords: list[str], country: str, max_ads: int = 40) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    ads = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page()

        for keyword in keywords[:3]:
            url = (
                f"{_META_ADS_URL}"
                f"?active_status=all&ad_type=all&country={country}"
                f"&q={keyword.replace(' ', '+')}&media_type=video&search_type=keyword_unordered"
            )
            try:
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                await asyncio.sleep(3)

                # Scroll to load more results
                for _ in range(5):
                    await page.keyboard.press("End")
                    await asyncio.sleep(1.5)

                cards = await page.query_selector_all('[class*="x8t9es0"]')
                for card in cards[:max_ads]:
                    try:
                        text_el = await card.query_selector('[data-ad-preview="message"], [class*="xdj266r"]')
                        text = await text_el.inner_text() if text_el else ""
                        name_el = await card.query_selector('[class*="x1heor9g"] span, [class*="x8k8oae"]')
                        advertiser = await name_el.inner_text() if name_el else ""
                        if text.strip():
                            ads.append({"text": text.strip(), "advertiser": advertiser.strip()})
                    except Exception:
                        continue
            except Exception:
                continue

        await browser.close()
    return ads


def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "meta_ads" not in sources:
        return []
    items: list[ContentItem] = []
    for market in markets:
        country = "US" if market == "us" else "ES"
        for cat_key, cat in CATEGORIES.items():
            keywords = cat.named_brands[:3] + cat.generic_terms[:2]
            raw_ads = asyncio.run(_scrape_meta_async(keywords, country))
            for i, raw in enumerate(raw_ads):
                text = raw.get("text", "").strip()
                if not text or len(text) < 10:
                    continue
                layer = "competitor" if any(b in text.lower() for b in cat.named_brands) else "field"
                items.append(ContentItem(
                    source="meta_ads",
                    content_id=f"meta_{cat_key}_{market}_{i}",
                    content_type="ad",
                    text=text,
                    market=market,
                    layer=layer,
                    data_category="ad",
                    engagement_score=0.0,
                    brand=raw.get("advertiser", ""),
                    category=cat_key,
                    product=cat.product,
                ))
            time.sleep(2)
    return items
