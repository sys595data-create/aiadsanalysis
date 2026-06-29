import asyncio
import time
import json
from backend.ingestion.base import ContentItem
from backend.voc.categories import CATEGORIES


_MAX_REVIEWS = 30


async def _scrape_walmart_async(queries: list[str], proxy_url: str = "") -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []
    results = []
    async with async_playwright() as p:
        launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if proxy_url:
            launch_args["proxy"] = {"server": proxy_url}
        browser = await p.chromium.launch(**launch_args)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        )

        for query in queries[:3]:
            search_url = f"https://www.walmart.com/search?q={query.replace(' ', '+')}"
            try:
                page = await ctx.new_page()
                await page.goto(search_url, timeout=20000, wait_until="domcontentloaded")
                await asyncio.sleep(2)

                product_links = await page.eval_on_selector_all(
                    'a[link-identifier]',
                    "els => [...new Set(els.map(e => e.href))].filter(h => h.includes('/ip/')).slice(0, 4)"
                )

                for link in product_links[:3]:
                    try:
                        await page.goto(link, timeout=20000, wait_until="domcontentloaded")
                        await asyncio.sleep(2)

                        # Try JSON-LD first
                        for script in await page.query_selector_all('script[type="application/ld+json"]'):
                            try:
                                content = await script.inner_html()
                                data = json.loads(content)
                                reviews = _extract_walmart_jsonld(data)
                                results.extend(reviews)
                            except Exception:
                                continue

                        # DOM fallback
                        review_els = await page.query_selector_all('[data-testid="review-text"], [itemprop="reviewBody"]')
                        for el in review_els[:15]:
                            try:
                                text = await el.inner_text()
                                if text.strip():
                                    rating_el = await el.query_selector('[aria-label*="stars"], [aria-label*="estrellas"]')
                                    rating_text = await rating_el.get_attribute("aria-label") if rating_el else ""
                                    rating = float(rating_text.split()[0]) if rating_text else 0.0
                                    results.append({"text": text.strip(), "rating": rating, "url": link})
                            except Exception:
                                continue
                        await page.close()
                    except Exception:
                        continue
            except Exception:
                continue

        await ctx.close()
        await browser.close()
    return results


def _extract_walmart_jsonld(data) -> list[dict]:
    results = []
    if isinstance(data, dict):
        if data.get("@type") == "Review":
            body = data.get("reviewBody") or data.get("description") or ""
            rating = float((data.get("reviewRating") or {}).get("ratingValue") or 0)
            if body:
                results.append({"text": body, "rating": rating})
        for v in data.values():
            if isinstance(v, (dict, list)):
                results.extend(_extract_walmart_jsonld(v))
    elif isinstance(data, list):
        for item in data:
            results.extend(_extract_walmart_jsonld(item))
    return results


def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "walmart" not in sources or "us" not in markets:
        return []
    proxy_url = config.get("proxy_url", "")
    items: list[ContentItem] = []

    for cat_key, cat in CATEGORIES.items():
        queries = cat.walmart_queries[:3]
        if not queries:
            continue
        raw_reviews = asyncio.run(_scrape_walmart_async(queries, proxy_url))
        for i, rev in enumerate(raw_reviews[:_MAX_REVIEWS]):
            text = rev.get("text", "")
            if not text or len(text) < 15:
                continue
            rating = rev.get("rating", 0.0)
            layer = "competitor" if any(b in text.lower() for b in cat.named_brands) else "field"
            items.append(ContentItem(
                source="walmart",
                content_id=f"wmt_{cat_key}_{i}",
                content_type="review",
                text=text,
                market="us",
                layer=layer,
                data_category="voc",
                engagement_score=abs(rating - 3) * 0.4,
                url=rev.get("url", ""),
                rating=rating,
                category=cat_key,
                product=cat.product,
            ))
        time.sleep(3)
    return items
