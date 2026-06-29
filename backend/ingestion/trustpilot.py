import time
import requests
from bs4 import BeautifulSoup
import json
from backend.ingestion.base import ContentItem
from backend.voc.categories import CATEGORIES


_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
_MAX_REVIEWS = 40
_PAGES = 3


def _scrape_domain(domain: str, proxy_url: str = "") -> list[dict]:
    reviews = []
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    slug = domain.replace("https://", "").replace("http://", "").rstrip("/")

    for page in range(1, _PAGES + 1):
        url = f"https://www.trustpilot.com/review/{slug}?page={page}"
        try:
            resp = requests.get(url, headers=_HEADERS, proxies=proxies, timeout=15)
            if resp.status_code != 200:
                break
            soup = BeautifulSoup(resp.text, "lxml")

            # JSON-LD extraction (most reliable)
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, list):
                        for obj in data:
                            reviews.extend(_extract_jsonld(obj))
                    else:
                        reviews.extend(_extract_jsonld(data))
                except Exception:
                    continue

            if len(reviews) >= _MAX_REVIEWS:
                break
            time.sleep(1.5)
        except Exception:
            break
    return reviews[:_MAX_REVIEWS]


def _extract_jsonld(obj: dict) -> list[dict]:
    results = []
    if obj.get("@type") == "Review":
        body = obj.get("reviewBody") or obj.get("description") or ""
        rating_obj = obj.get("reviewRating") or {}
        rating = float(rating_obj.get("ratingValue") or 0)
        date = obj.get("datePublished") or ""
        if body:
            results.append({"text": body.strip(), "rating": rating, "date": date})
    for v in obj.values():
        if isinstance(v, dict):
            results.extend(_extract_jsonld(v))
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    results.extend(_extract_jsonld(item))
    return results


def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "trustpilot" not in sources:
        return []
    proxy_url = config.get("proxy_url", "")
    items: list[ContentItem] = []

    for cat_key, cat in CATEGORIES.items():
        for domain in cat.trustpilot_domains:
            raw_reviews = _scrape_domain(domain, proxy_url)
            for i, rev in enumerate(raw_reviews):
                text = rev.get("text", "")
                if not text or len(text) < 15:
                    continue
                rating = rev.get("rating", 0.0)
                eng = abs(rating - 3) * 0.5
                market = "us"
                layer = "competitor" if any(b in text.lower() for b in cat.named_brands) else "field"
                items.append(ContentItem(
                    source="trustpilot",
                    content_id=f"tp_{cat_key}_{abs(hash(domain + text[:30]))}",
                    content_type="review",
                    text=text,
                    market=market,
                    layer=layer,
                    data_category="voc",
                    engagement_score=eng,
                    url=f"https://www.trustpilot.com/review/{domain}",
                    rating=rating,
                    date_str=rev.get("date", ""),
                    brand=domain,
                    category=cat_key,
                    product=cat.product,
                ))
            time.sleep(2)
    return items
