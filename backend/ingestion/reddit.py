"""
Reddit scraper — PRAW (official API) with public JSON fallback.
Merges 595's layer-based query structure with voc_scraper's 60+ subreddit list.
"""
import time
import math
import requests
from backend.ingestion.base import ContentItem, text_engagement
from backend.voc.categories import CATEGORIES, REDDIT_SUBREDDITS, GENERAL_SEARCH_TERMS


_PUBLIC_HEADERS = {"User-Agent": "aiadsanalysis/1.0"}
_MAX_POSTS_PER_QUERY = 25
_MAX_COMMENTS_PER_POST = 10
_REQUEST_DELAY = 2.0


def _praw_search(subreddit_name: str, query: str, client_id: str, client_secret: str, user_agent: str, limit: int = 25) -> list[dict]:
    try:
        import praw
        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)
        sub = reddit.subreddit(subreddit_name)
        posts = []
        for post in sub.search(query, sort="relevance", time_filter="year", limit=limit):
            posts.append({
                "id": post.id,
                "title": post.title,
                "selftext": post.selftext,
                "score": post.score,
                "num_comments": post.num_comments,
                "upvote_ratio": post.upvote_ratio,
                "url": f"https://reddit.com{post.permalink}",
                "created_utc": post.created_utc,
                "comments": _get_comments_praw(post, _MAX_COMMENTS_PER_POST),
            })
        return posts
    except Exception:
        return []


def _get_comments_praw(post, limit: int) -> list[dict]:
    try:
        post.comments.replace_more(limit=0)
        return [
            {"id": c.id, "body": c.body, "score": c.score}
            for c in list(post.comments)[:limit]
            if hasattr(c, "body") and c.body not in ("[removed]", "[deleted]")
        ]
    except Exception:
        return []


def _public_json_search(subreddit: str, query: str, limit: int = 25) -> list[dict]:
    url = f"https://old.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "restrict_sr": 1, "sort": "relevance", "t": "year", "limit": limit}
    try:
        resp = requests.get(url, params=params, headers=_PUBLIC_HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            selftext = p.get("selftext", "")
            if selftext in ("[removed]", "[deleted]"):
                selftext = ""
            posts.append({
                "id": p.get("id"),
                "title": p.get("title", ""),
                "selftext": selftext,
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "upvote_ratio": p.get("upvote_ratio", 1.0),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "created_utc": p.get("created_utc", 0),
                "comments": _public_json_comments(p.get("permalink", "")),
            })
        return posts
    except Exception:
        return []


def _public_json_comments(permalink: str) -> list[dict]:
    if not permalink:
        return []
    try:
        url = f"https://old.reddit.com{permalink}.json"
        resp = requests.get(url, headers=_PUBLIC_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if len(data) < 2:
            return []
        comments = []
        for child in data[1].get("data", {}).get("children", [])[:_MAX_COMMENTS_PER_POST]:
            c = child.get("data", {})
            body = c.get("body", "")
            if body and body not in ("[removed]", "[deleted]"):
                comments.append({"id": c.get("id", ""), "body": body, "score": c.get("score", 0)})
        return comments
    except Exception:
        return []


def _make_items(posts: list[dict], market: str, layer: str, category: str = "", product: str = "") -> list[ContentItem]:
    items = []
    for post in posts:
        pid = post.get("id")
        if not pid:
            continue
        title = post.get("title", "")
        selftext = post.get("selftext", "")
        text = f"{title}\n{selftext}".strip()
        score = post.get("score", 0)
        num_comments = post.get("num_comments", 0)
        eng = text_engagement(score, num_comments)
        item = ContentItem(
            source="reddit",
            content_id=f"r_{pid}",
            content_type="post",
            text=text,
            market=market,
            layer=layer,
            data_category="voc",
            engagement_score=eng,
            url=post.get("url", ""),
            category=category,
            product=product,
            meta={"score": score, "num_comments": num_comments, "upvote_ratio": post.get("upvote_ratio", 1.0)},
        )
        if item.is_meaningful:
            items.append(item)

        # Add comments as separate items
        for comment in post.get("comments", []):
            body = comment.get("body", "")
            if not body or len(body) < 15:
                continue
            c_item = ContentItem(
                source="reddit",
                content_id=f"r_c_{comment.get('id', abs(hash(body)))}",
                content_type="comment",
                text=body,
                market=market,
                layer=layer,
                data_category="voc",
                engagement_score=max(comment.get("score", 0), 0) * 0.1,
                url=post.get("url", ""),
                category=category,
                product=product,
            )
            if c_item.is_meaningful:
                items.append(c_item)
    return items


def scrape(markets: list[str], sources: list[str], config: dict) -> list[ContentItem]:
    if "reddit" not in sources:
        return []

    client_id = config.get("reddit_client_id", "")
    client_secret = config.get("reddit_client_secret", "")
    user_agent = config.get("reddit_user_agent", "aiadsanalysis/1.0")
    use_praw = bool(client_id and client_secret)

    def search(subreddit: str, query: str) -> list[dict]:
        if use_praw:
            return _praw_search(subreddit, query, client_id, client_secret, user_agent)
        time.sleep(_REQUEST_DELAY)
        return _public_json_search(subreddit, query)

    items: list[ContentItem] = []
    seen_ids: set[str] = set()

    for market in markets:
        subreddit_groups = REDDIT_SUBREDDITS.get(market, {})

        for layer, subreddits in subreddit_groups.items():
            # General terms across all subreddits
            for term in GENERAL_SEARCH_TERMS.get(market, [])[:3]:
                for sub in subreddits[:4]:
                    for post in search(sub, term):
                        for it in _make_items([post], market, "general"):
                            if it.content_id not in seen_ids:
                                seen_ids.add(it.content_id)
                                items.append(it)

            # Category-specific terms
            for cat_key, cat in CATEGORIES.items():
                for term in cat.reddit_terms.get(market, [])[:4]:
                    for sub in subreddits[:3]:
                        cat_layer = "competitor" if any(b in term.lower() for b in cat.named_brands) else layer
                        for post in search(sub, term):
                            for it in _make_items([post], market, cat_layer, cat_key, cat.product):
                                if it.content_id not in seen_ids:
                                    seen_ids.add(it.content_id)
                                    items.append(it)

    return items
