import subprocess
import json
import requests
import time
from backend.ingestion.base import ContentItem, video_engagement
from backend.voc.categories import CATEGORIES, GENERAL_SEARCH_TERMS


_MAX_PER_QUERY = 20


# ─── pipispy (PiPiADS) API ────────────────────────────────────────────────────

def _pipispy_search(keyword: str, country: str, api_key: str, base_url: str,
                     date_from: str = None, date_to: str = None, page_size: int = 20) -> list[dict]:
    params = {
        "access_key": api_key,
        "country": country.upper(),
        "keyword": keyword,
        "page": 1,
        "page_size": page_size,
    }
    if date_from:
        params["start_time"] = date_from
    if date_to:
        params["end_time"] = date_to
    try:
        resp = requests.get(f"{base_url}/ad/list", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("ads", []) or data.get("data", []) or []
    except Exception:
        return []


def _parse_pipispy_ad(raw: dict, market: str, layer: str, category: str = "", product: str = "") -> ContentItem | None:
    ad_id = str(raw.get("ad_id") or raw.get("id") or "")
    if not ad_id:
        return None
    title = raw.get("title") or raw.get("ad_title") or ""
    text = title or raw.get("description") or ""
    if not text:
        return None
    likes = int(raw.get("like_count") or raw.get("digg_count") or 0)
    comments = int(raw.get("comment_count") or 0)
    shares = int(raw.get("share_count") or 0)
    eng = video_engagement(0, likes, comments + shares)
    return ContentItem(
        source="tiktok_ads",
        content_id=f"pip_{ad_id}",
        content_type="ad",
        text=text,
        market=market,
        layer=layer,
        data_category="ad",
        engagement_score=eng,
        url=raw.get("detail_url") or "",
        video_url=raw.get("video_url") or "",
        like_count=likes,
        comment_count=comments,
        share_count=shares,
        date_str=str(raw.get("create_time") or raw.get("start_time") or ""),
        brand=raw.get("advertiser_name") or "",
        category=category,
        product=product,
        meta={
            "advertiser_id": raw.get("advertiser_id"),
            "end_time": raw.get("end_time"),
            "impression_tier": raw.get("impression_tier") or raw.get("cost_tier"),
        },
    )


# ─── yt-dlp organic TikTok ────────────────────────────────────────────────────

def _ytdlp_tiktok(query: str, max_results: int = 20) -> list[dict]:
    cmd = [
        "yt-dlp",
        f"tiktoksearch{max_results}:{query}",
        "--dump-json", "--no-download", "--no-warnings", "--flat-playlist",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        items = []
        for line in result.stdout.strip().splitlines():
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return items
    except Exception:
        return []


def _parse_organic(raw: dict, market: str, layer: str, category: str = "", product: str = "") -> ContentItem | None:
    vid_id = raw.get("id") or raw.get("video_id")
    if not vid_id:
        return None
    views = int(raw.get("view_count") or 0)
    likes = int(raw.get("like_count") or 0)
    comments = int(raw.get("comment_count") or 0)
    text = (raw.get("title") or raw.get("description") or "").strip()
    if not text:
        return None
    return ContentItem(
        source="tiktok",
        content_id=f"tt_{vid_id}",
        content_type="video",
        text=text,
        market=market,
        layer=layer,
        data_category="content",
        engagement_score=video_engagement(views, likes, comments),
        url=raw.get("webpage_url") or f"https://www.tiktok.com/video/{vid_id}",
        video_url=raw.get("webpage_url") or "",
        view_count=views,
        like_count=likes,
        comment_count=comments,
        date_str=str(raw.get("upload_date") or ""),
        category=category,
        product=product,
    )


# ─── Main scraper ─────────────────────────────────────────────────────────────

def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "tiktok" not in sources:
        return []
    api_key = config.get("pipispy_api_key", "")
    base_url = config.get("pipispy_base_url", "https://api.pipiads.com/api/v1")
    date_from = config.get("date_from")
    date_to = config.get("date_to")

    items: list[ContentItem] = []

    for market in markets:
        country = "US" if market == "us" else "ES"

        # pipispy ads
        if api_key:
            for cat_key, cat in CATEGORIES.items():
                for kw in cat.pipispy_keywords.get(market, [])[:3]:
                    layer = "competitor" if any(b in kw.lower() for b in cat.named_brands) else "field"
                    for raw in _pipispy_search(kw, country, api_key, base_url, date_from, date_to):
                        item = _parse_pipispy_ad(raw, market, layer, cat_key, cat.product)
                        if item:
                            items.append(item)
                    time.sleep(0.5)

        # organic yt-dlp
        for term in GENERAL_SEARCH_TERMS.get(market, [])[:3]:
            for raw in _ytdlp_tiktok(term, _MAX_PER_QUERY):
                item = _parse_organic(raw, market, "general")
                if item:
                    items.append(item)
        for cat_key, cat in CATEGORIES.items():
            for tag in cat.tiktok_hashtags.get(market, [])[:3]:
                for raw in _ytdlp_tiktok(f"#{tag}", _MAX_PER_QUERY):
                    layer = "competitor" if any(b in tag.lower() for b in cat.named_brands) else "field"
                    item = _parse_organic(raw, market, layer, cat_key, cat.product)
                    if item:
                        items.append(item)

    seen = set()
    unique = []
    for item in items:
        if item.content_id not in seen:
            seen.add(item.content_id)
            unique.append(item)
    return unique
