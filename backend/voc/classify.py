import re
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI
from backend.config import settings

THEMES = ["Pain/Symptom", "Fear/Objection", "Positive", "Competitor Mention"]

_KEYWORDS = {
    "Pain/Symptom": [
        "pain", "hurt", "ache", "suffer", "chronic", "inflammation", "sore",
        "fatigue", "tired", "tension", "stiff", "numb", "tingling", "swollen",
        "discomfort", "relief", "struggle", "condition", "symptoms", "diagnosis",
        "dolor", "cansancio", "tensión", "inflamación", "molestia",
    ],
    "Fear/Objection": [
        "skeptical", "doubt", "scam", "waste", "expensive", "overpriced",
        "doesn't work", "placebo", "gimmick", "cheap", "broke", "refund",
        "return", "disappointed", "misleading", "fake", "overrated",
        "caro", "no funciona", "estafa", "decepción",
    ],
    "Positive": [
        "love", "amazing", "great", "excellent", "recommend", "works",
        "effective", "helped", "better", "improved", "worth", "life-changing",
        "fantastic", "best", "perfect", "happy", "satisfied", "relief",
        "genial", "excelente", "recomiendo", "funciona", "me ayudó",
    ],
    "Competitor Mention": [
        "ceragem", "migun", "healthyline", "higherdose", "higher dose",
        "biomat", "therabody", "renpho", "bob brad", "revitive",
        "nooro", "auvon", "pranamat",
    ],
}


@dataclass
class ClassificationResult:
    theme: str
    subtheme: str
    quote: str
    paraphrase: str = ""
    confidence: float = 1.0


def _keyword_classify(text: str) -> ClassificationResult:
    low = text.lower()
    scores = {theme: 0 for theme in THEMES}
    for theme, words in _KEYWORDS.items():
        for word in words:
            if word in low:
                scores[theme] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "Pain/Symptom"
    words = text.split()
    quote = " ".join(words[:15]) + ("…" if len(words) > 15 else "")
    return ClassificationResult(theme=best, subtheme="", quote=quote)


def _llm_classify(text: str) -> ClassificationResult:
    client = OpenAI(api_key=settings.grok_api_key, base_url=settings.grok_api_base)
    prompt = f"""Classify this customer review/post into exactly one theme and provide a subtheme.

Themes: Pain/Symptom | Fear/Objection | Positive | Competitor Mention

Text: {text[:500]}

Respond as JSON:
{{"theme": "...", "subtheme": "...", "quote": "exact quote max 15 words", "paraphrase": "neutral 1-sentence summary"}}"""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
        )
        import json
        data = json.loads(resp.choices[0].message.content)
        return ClassificationResult(
            theme=data.get("theme", "Pain/Symptom"),
            subtheme=data.get("subtheme", ""),
            quote=data.get("quote", ""),
            paraphrase=data.get("paraphrase", ""),
        )
    except Exception:
        return _keyword_classify(text)


def classify(text: str, use_llm: bool = False) -> ClassificationResult:
    if use_llm and settings.grok_api_key:
        return _llm_classify(text)
    return _keyword_classify(text)


def classify_batch(texts: list[str], use_llm: bool = False) -> list[ClassificationResult]:
    return [classify(t, use_llm) for t in texts]
