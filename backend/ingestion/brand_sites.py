import time
import requests
from bs4 import BeautifulSoup
from backend.ingestion.base import ContentItem
from backend.voc.categories import CATEGORIES


_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
_TESTIMONIAL_SELECTORS = [
    '[class*="testimonial"]', '[class*="review"]', '[class*="quote"]',
    '[class*="customer"]', '[itemprop="review"]', '[itemprop="reviewBody"]',
    "blockquote", ".testimonial-text", ".review-text",
]
_MIN_TEXT_LEN = 40


def _scrape_brand_url(url: str, proxy_url: str = "") -> list[str]:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    try:
        resp = requests.get(url, headers=_HEADERS, proxies=proxies, timeout=15)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        texts = []
        for sel in _TESTIMONIAL_SELECTORS:
            for el in soup.select(sel):
                text = el.get_text(separator=" ", strip=True)
                if len(text) >= _MIN_TEXT_LEN and text not in texts:
                    texts.append(text)
        return texts[:20]
    except Exception:
        return []


def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "brand_sites" not in sources:
        return []
    proxy_url = config.get("proxy_url", "")
    items: list[ContentItem] = []

    for cat_key, cat in CATEGORIES.items():
        for url in cat.brand_urls[:3]:
            texts = _scrape_brand_url(url, proxy_url)
            for i, text in enumerate(texts):
                market = "es" if ".es" in url or "es." in url else "us"
                layer = "competitor" if any(b in text.lower() for b in cat.named_brands) else "field"
                items.append(ContentItem(
                    source="brand_site",
                    content_id=f"bs_{cat_key}_{abs(hash(url + str(i)))}",
                    content_type="review",
                    text=text,
                    market=market,
                    layer=layer,
                    data_category="voc",
                    engagement_score=0.1,
                    url=url,
                    brand=url.split("/")[2].replace("www.", ""),
                    category=cat_key,
                    product=cat.product,
                ))
            time.sleep(2)
    return items
