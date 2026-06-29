import subprocess
import json
import re
from backend.ingestion.base import ContentItem, video_engagement
from backend.voc.categories import CATEGORIES, GENERAL_SEARCH_TERMS


_MAX_PER_QUERY = 15
_MIN_VIEWS = 10_000


def _yt_search(query: str, max_results: int = 15, min_views: int = 0) -> list[dict]:
    cmd = [
        "yt-dlp",
        f"ytsearch{max_results * 3}:{query}",
        "--dump-json", "--no-download", "--no-warnings",
        "--extractor-args", "youtube:skip=dash,hls",
        "--match-filter", f"view_count>={max(min_views, _MIN_VIEWS)}",
        "--flat-playlist",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        items = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items[:max_results]
    except Exception:
        return []


def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "youtube" not in sources:
        return []
    items: list[ContentItem] = []
    min_views = config.get("min_views", _MIN_VIEWS)
    date_from = config.get("date_from")

    for market in markets:
        # General layer — influencer / biohacking content
        for term in GENERAL_SEARCH_TERMS.get(market, [])[:5]:
            for raw in _yt_search(term, _MAX_PER_QUERY, min_views):
                item = _parse(raw, market, "general", "content")
                if item:
                    items.append(item)

        # Field + competitor per category
        for cat_key, cat in CATEGORIES.items():
            queries = cat.youtube_queries.get(market, [])
            for q in queries[:4]:
                layer = "competitor" if any(b in q.lower() for b in cat.named_brands) else "field"
                for raw in _yt_search(q, _MAX_PER_QUERY, min_views):
                    item = _parse(raw, market, layer, "content", category=cat_key, product=cat.product)
                    if item:
                        items.append(item)

    # deduplicate by content_id
    seen = set()
    unique = []
    for item in items:
        if item.content_id not in seen:
            seen.add(item.content_id)
            unique.append(item)
    return unique


def _parse(raw: dict, market: str, layer: str, data_category: str, category: str = "", product: str = "") -> ContentItem | None:
    vid_id = raw.get("id") or raw.get("video_id")
    if not vid_id:
        return None
    views = raw.get("view_count") or 0
    likes = raw.get("like_count") or 0
    comments = raw.get("comment_count") or 0
    title = raw.get("title") or ""
    desc = raw.get("description") or ""
    text = f"{title}\n{desc}".strip()
    if not text:
        return None
    eng = video_engagement(views, likes, comments)
    return ContentItem(
        source="youtube",
        content_id=vid_id,
        content_type="video",
        text=text,
        market=market,
        layer=layer,
        data_category=data_category,
        engagement_score=eng,
        url=f"https://www.youtube.com/watch?v={vid_id}",
        video_url=f"https://www.youtube.com/watch?v={vid_id}",
        view_count=views,
        like_count=likes,
        comment_count=comments,
        date_str=str(raw.get("upload_date") or ""),
        category=category,
        product=product,
        meta={"duration": raw.get("duration"), "channel": raw.get("channel")},
    )
