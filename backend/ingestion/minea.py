"""
Minea Pro — Playwright XHR interception for Instagram/Meta ad video URLs.
Logs in once (saves persistent browser profile), then searches by keyword,
intercepts the JSON responses from Minea's internal API that contain CDN video URLs.
"""
import asyncio
import json
import os
import re
import time
from typing import Callable
from backend.ingestion.base import ContentItem, video_engagement
from backend.voc.categories import CATEGORIES


_MINEA_INSTAGRAM_URL = "https://app.minea.com/en/instagram-ads"
_MINEA_FACEBOOK_URL = "https://app.minea.com/en/facebook-ads"
_CDN_PATTERN = re.compile(r'https?://[^\s"\']+\.(mp4|mov|webm)[^\s"\']*', re.IGNORECASE)


def _extract_ads_from_json(data) -> list[dict]:
    """Recursively extract ad objects from any JSON structure."""
    ads = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                video_url = (
                    item.get("video_url") or item.get("videoUrl") or
                    item.get("media_url") or item.get("mediaUrl") or
                    item.get("cdn_url") or item.get("url") or ""
                )
                text = (
                    item.get("ad_text") or item.get("adText") or
                    item.get("text") or item.get("caption") or
                    item.get("title") or item.get("body") or ""
                )
                if video_url or text:
                    ads.append({
                        "video_url": video_url,
                        "text": text,
                        "likes": item.get("likes") or item.get("like_count") or 0,
                        "comments": item.get("comments") or item.get("comment_count") or 0,
                        "shares": item.get("shares") or item.get("share_count") or 0,
                        "start_date": item.get("start_date") or item.get("startDate") or item.get("created_at") or "",
                        "end_date": item.get("end_date") or item.get("endDate") or "",
                        "advertiser": item.get("advertiser") or item.get("page_name") or item.get("brand") or "",
                        "country": item.get("country") or item.get("countries") or "",
                    })
                else:
                    ads.extend(_extract_ads_from_json(item))
            elif isinstance(item, list):
                ads.extend(_extract_ads_from_json(item))
    elif isinstance(data, dict):
        for key in ("ads", "data", "items", "results", "records", "list"):
            if key in data:
                ads.extend(_extract_ads_from_json(data[key]))
    return ads


async def _search_minea_async(
    keyword: str,
    platform_url: str,
    profile_dir: str,
    email: str = "",
    password: str = "",
    max_ads: int = 30,
    market: str = "us",
) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    captured: list[dict] = []

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await ctx.new_page()

        # Intercept XHR / fetch responses from Minea's API
        async def handle_response(response):
            url = response.url
            if "minea" not in url and "cdn" not in url.lower():
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                body = await response.body()
                data = json.loads(body)
                ads = _extract_ads_from_json(data)
                captured.extend(ads)
            except Exception:
                pass

        page.on("response", handle_response)

        # Check if already logged in
        await page.goto(platform_url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # If login page appears, log in
        if email and "login" in page.url.lower():
            try:
                await page.fill("input[type='email'], input[name='email']", email)
                await page.fill("input[type='password'], input[name='password']", password)
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle", timeout=20000)
                await asyncio.sleep(3)
            except Exception:
                pass

        # Perform search
        try:
            search_sel = "input[placeholder*='search' i], input[placeholder*='keyword' i], input[type='search']"
            await page.wait_for_selector(search_sel, timeout=10000)
            await page.fill(search_sel, keyword)
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(3)

            # Scroll to load more ads
            for _ in range(4):
                await page.keyboard.press("End")
                await asyncio.sleep(2)
                if len(captured) >= max_ads:
                    break
        except Exception:
            pass

        await ctx.close()

    return captured[:max_ads]


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except Exception:
        return asyncio.run(coro)


def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "minea" not in sources:
        return []

    profile_dir = config.get("minea_profile_dir", ".minea_profile")
    email = config.get("minea_email", "")
    password = config.get("minea_password", "")

    if not email and not os.path.exists(profile_dir):
        return []

    items: list[ContentItem] = []

    for market in markets:
        for cat_key, cat in CATEGORIES.items():
            for kw in cat.minea_keywords.get(market, [])[:2]:
                layer = "competitor" if any(b in kw.lower() for b in cat.named_brands) else "field"
                raw_ads = _run_async(_search_minea_async(
                    keyword=kw,
                    platform_url=_MINEA_INSTAGRAM_URL,
                    profile_dir=profile_dir,
                    email=email,
                    password=password,
                    max_ads=25,
                    market=market,
                ))
                for raw in raw_ads:
                    item = _parse(raw, market, layer, cat_key, cat.product)
                    if item:
                        items.append(item)
                time.sleep(2)

    seen = set()
    unique = []
    for item in items:
        if item.content_id not in seen:
            seen.add(item.content_id)
            unique.append(item)
    return unique


def _parse(raw: dict, market: str, layer: str, category: str, product: str) -> ContentItem | None:
    text = raw.get("text") or ""
    video_url = raw.get("video_url") or ""
    if not text and not video_url:
        return None
    content_id = f"minea_{abs(hash(video_url or text))}"
    likes = int(raw.get("likes") or 0)
    comments = int(raw.get("comments") or 0)
    shares = int(raw.get("shares") or 0)
    return ContentItem(
        source="minea",
        content_id=content_id,
        content_type="ad",
        text=text or video_url,
        market=market,
        layer=layer,
        data_category="ad",
        engagement_score=video_engagement(0, likes, comments + shares),
        url="",
        video_url=video_url,
        like_count=likes,
        comment_count=comments,
        share_count=shares,
        date_str=str(raw.get("start_date") or ""),
        brand=raw.get("advertiser") or "",
        category=category,
        product=product,
        meta={"end_date": raw.get("end_date"), "country": raw.get("country")},
    )


# ─── One-time setup script ────────────────────────────────────────────────────

def setup_profile(profile_dir: str, email: str, password: str):
    """Run once interactively to save Minea login session."""
    async def _setup():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                profile_dir, headless=False,
                args=["--no-sandbox"],
            )
            page = await ctx.new_page()
            await page.goto(_MINEA_INSTAGRAM_URL)
            print("Log into Minea in the browser window, then press Enter here...")
            input()
            await ctx.close()
        print(f"Session saved to {profile_dir}")
    asyncio.run(_setup())


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        setup_profile(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("Usage: python minea.py <profile_dir> <email> <password>")
