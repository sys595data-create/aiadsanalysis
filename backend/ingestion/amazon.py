import asyncio
import time
import math
from backend.ingestion.base import ContentItem
from backend.voc.categories import CATEGORIES


_DOMAINS = {"us": "amazon.com", "es": "amazon.es"}
_MAX_REVIEWS_PER_QUERY = 30
_SCROLL_PAGES = 3


async def _scrape_amazon_async(queries: list[str], domain: str, proxy_url: str = "") -> list[dict]:
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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US" if "amazon.com" in domain else "es-ES",
        )

        for query in queries[:4]:
            search_url = f"https://www.{domain}/s?k={query.replace(' ', '+')}&i=hpc"
            try:
                page = await ctx.new_page()
                await page.goto(search_url, timeout=20000, wait_until="domcontentloaded")
                await asyncio.sleep(2)

                product_links = await page.eval_on_selector_all(
                    'a[href*="/dp/"]',
                    "els => [...new Set(els.map(e => e.href))].slice(0, 5)"
                )
                for link in product_links[:3]:
                    try:
                        review_url = link.replace("/dp/", "/product-reviews/").split("?")[0] + "?reviewerType=all_reviews&sortBy=recent"
                        await page.goto(review_url, timeout=20000, wait_until="domcontentloaded")
                        await asyncio.sleep(2)

                        for _ in range(_SCROLL_PAGES):
                            reviews = await page.query_selector_all('[data-hook="review"]')
                            for rev in reviews:
                                try:
                                    body_el = await rev.query_selector('[data-hook="review-body"] span')
                                    body = await body_el.inner_text() if body_el else ""
                                    rating_el = await rev.query_selector('[data-hook="review-star-rating"] span, [data-hook="cmps-review-star-rating"] span')
                                    rating_text = await rating_el.inner_text() if rating_el else "0"
                                    rating = float(rating_text.split()[0].replace(",", ".")) if rating_text else 0.0
                                    helpful_el = await rev.query_selector('[data-hook="helpful-vote-statement"]')
                                    helpful_text = await helpful_el.inner_text() if helpful_el else ""
                                    helpful = int("".join(filter(str.isdigit, helpful_text.split()[0]))) if helpful_text and helpful_text[0].isdigit() else 0
                                    if body.strip():
                                        results.append({"text": body.strip(), "rating": rating, "helpful": helpful, "url": review_url})
                                except Exception:
                                    continue

                            next_btn = await page.query_selector('[data-action="pagnNextLink"] a, .a-last a')
                            if not next_btn:
                                break
                            await next_btn.click()
                            await asyncio.sleep(2)
                    except Exception:
                        continue
                await page.close()
            except Exception:
                continue

        await ctx.close()
        await browser.close()
    return results


def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "amazon" not in sources:
        return []
    proxy_url = config.get("proxy_url", "")
    items: list[ContentItem] = []

    for market in markets:
        domain = _DOMAINS.get(market, "amazon.com")
        for cat_key, cat in CATEGORIES.items():
            queries = cat.amazon_queries.get(market, [])
            raw_reviews = asyncio.run(_scrape_amazon_async(queries, domain, proxy_url))
            for i, rev in enumerate(raw_reviews[:_MAX_REVIEWS_PER_QUERY]):
                text = rev.get("text", "")
                if not text or len(text) < 15:
                    continue
                rating = rev.get("rating", 0.0)
                helpful = rev.get("helpful", 0)
                eng = (helpful * 0.5) + (abs(rating - 3) * 0.3)
                layer = "competitor" if any(b in text.lower() for b in cat.named_brands) else "field"
                items.append(ContentItem(
                    source="amazon",
                    content_id=f"amz_{cat_key}_{market}_{i}",
                    content_type="review",
                    text=text,
                    market=market,
                    layer=layer,
                    data_category="voc",
                    engagement_score=eng,
                    url=rev.get("url", ""),
                    rating=rating,
                    category=cat_key,
                    product=cat.product,
                    meta={"helpful_votes": helpful},
                ))
        time.sleep(3)
    return items
