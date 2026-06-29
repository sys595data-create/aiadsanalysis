import re
import math
from dataclasses import dataclass, field
from typing import Optional


_PII_PATTERNS = [
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    re.compile(r'order\s*#?\s*\d{5,}', re.IGNORECASE),
]


def mask_pii(text: str) -> str:
    if not text:
        return text
    for pattern in _PII_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


@dataclass
class ContentItem:
    source: str
    content_id: str
    content_type: str        # video | post | comment | review | ad | product_listing
    text: str
    market: str              # us | es
    layer: str               # general | field | competitor
    data_category: str       # content | voc | ad
    engagement_score: float = 0.0
    url: str = ""
    video_url: str = ""
    brand: str = ""
    product: str = ""
    category: str = ""
    language: str = ""
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    rating: float = 0.0
    date_str: str = ""
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.text = mask_pii(self.text or "")

    @property
    def is_meaningful(self) -> bool:
        if not self.text or len(self.text.strip()) < 15:
            return False
        stripped = self.text.strip().lower()
        noise = {"[removed]", "[deleted]", "see more", "lol", "lmao", "ok", "okay"}
        if stripped in noise:
            return False
        words = stripped.split()
        if len(words) < 4:
            return False
        alpha_chars = sum(c.isalpha() for c in stripped)
        if len(stripped) > 0 and alpha_chars / len(stripped) < 0.4:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "content_id": self.content_id,
            "content_type": self.content_type,
            "text": self.text,
            "market": self.market,
            "layer": self.layer,
            "data_category": self.data_category,
            "engagement_score": self.engagement_score,
            "url": self.url,
            "video_url": self.video_url,
            "brand": self.brand,
            "product": self.product,
            "category": self.category,
            "language": self.language,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "share_count": self.share_count,
            "rating": self.rating,
            "date_str": self.date_str,
            "meta": self.meta,
        }


def video_engagement(views: int, likes: int, comments: int) -> float:
    if views <= 0:
        return math.log(max(likes + comments * 3, 1) + 1)
    return (likes + comments * 3) / views


def text_engagement(score: int, num_comments: int) -> float:
    return max(score, 0) * math.log(num_comments + 2)


BRAND_TO_PRODUCT = {
    "ceragem": "SpineSystem",
    "migun": "SpineSystem",
    "healthyline": "SleepSystem",
    "higher dose": "SleepSystem",
    "higherdose": "SleepSystem",
    "biomat": "SleepSystem",
    "pranamat": "Moxi",
    "therabody": "EyeSystem",
    "smartgoggles": "EyeSystem",
    "renpho": "EyeSystem",
    "eyeris": "EyeSystem",
    "bob brad": "EyeSystem",
    "bob & brad": "EyeSystem",
    "eyeoasis": "EyeSystem",
    "naipo": "EyeSystem",
    "revitive": "BodyHealth",
    "nooro": "BodyHealth",
    "auvon": "BodyHealth",
}


def detect_brand_product(text: str) -> tuple[str, str]:
    low = text.lower()
    for brand, product in BRAND_TO_PRODUCT.items():
        if brand in low:
            return brand, product
    return "", "Moxi"
