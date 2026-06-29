"""
Phase 1 — NLP clustering: competes BERTopic vs NMF+KMeans vs LDA, picks winner by coherence.
Runs on CPU (RunPod pod has both GPU and CPU threads available).
"""
import numpy as np
from typing import Optional


def cluster_items(items: list[dict], n_clusters: int = 10) -> dict:
    """
    items: list of ContentItem.to_dict() filtered to a single data_category.
    Returns dict with keys: best_model, clusters, coherence_scores
    """
    texts = [i.get("text", "") for i in items if i.get("text")]
    if len(texts) < 5:
        return {"best_model": "none", "clusters": [], "coherence_scores": {}}

    results = {}

    # Try BERTopic
    try:
        results["bertopic"] = _run_bertopic(texts, n_clusters)
    except Exception as e:
        results["bertopic"] = {"error": str(e), "coherence": 0.0}

    # Try NMF + KMeans
    try:
        results["nmf"] = _run_nmf(texts, n_clusters)
    except Exception as e:
        results["nmf"] = {"error": str(e), "coherence": 0.0}

    # Try LDA
    try:
        results["lda"] = _run_lda(texts, n_clusters)
    except Exception as e:
        results["lda"] = {"error": str(e), "coherence": 0.0}

    # Pick winner by coherence
    best_model = max(results, key=lambda k: results[k].get("coherence", 0.0))
    clusters = results[best_model].get("clusters", [])

    # Add sentiment per cluster
    for cluster in clusters:
        cluster["sentiment"] = _avg_sentiment([
            items[idx].get("text", "")
            for idx in cluster.get("item_indices", [])
            if idx < len(items)
        ])

    return {
        "best_model": best_model,
        "clusters": clusters,
        "coherence_scores": {k: v.get("coherence", 0.0) for k, v in results.items()},
    }


def _run_bertopic(texts: list[str], n_clusters: int) -> dict:
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer

    embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    model = BERTopic(
        embedding_model=embedder,
        nr_topics=n_clusters,
        min_topic_size=3,
        verbose=False,
    )
    topics, probs = model.fit_transform(texts)
    topic_info = model.get_topic_info()
    clusters = []
    for _, row in topic_info.iterrows():
        tid = int(row["Topic"])
        if tid == -1:
            continue
        indices = [i for i, t in enumerate(topics) if t == tid]
        words = [w for w, _ in (model.get_topic(tid) or [])][:10]
        clusters.append({
            "id": tid,
            "type": "content",
            "keywords": words,
            "size": len(indices),
            "item_indices": indices,
            "sample_texts": [texts[i][:200] for i in indices[:3]],
            "layer_mix": {},
        })
    coherence = _compute_coherence(texts, [c["keywords"] for c in clusters])
    return {"clusters": clusters, "coherence": coherence}


def _run_nmf(texts: list[str], n_clusters: int) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import NMF
    from sklearn.cluster import KMeans

    vec = TfidfVectorizer(max_features=5000, min_df=2, ngram_range=(1, 2))
    tfidf = vec.fit_transform(texts)
    nmf = NMF(n_components=n_clusters, random_state=42, max_iter=300)
    W = nmf.fit_transform(tfidf)
    feature_names = vec.get_feature_names_out()
    labels = W.argmax(axis=1)

    clusters = []
    for tid in range(n_clusters):
        indices = [i for i, l in enumerate(labels) if l == tid]
        if not indices:
            continue
        top_words = [feature_names[i] for i in nmf.components_[tid].argsort()[-10:][::-1]]
        clusters.append({
            "id": tid,
            "type": "content",
            "keywords": top_words,
            "size": len(indices),
            "item_indices": indices,
            "sample_texts": [texts[i][:200] for i in indices[:3]],
            "layer_mix": {},
        })
    coherence = _compute_coherence(texts, [c["keywords"] for c in clusters])
    return {"clusters": clusters, "coherence": coherence}


def _run_lda(texts: list[str], n_clusters: int) -> dict:
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation

    vec = CountVectorizer(max_features=5000, min_df=2, stop_words="english")
    dtm = vec.fit_transform(texts)
    lda = LatentDirichletAllocation(n_components=n_clusters, random_state=42, max_iter=20)
    W = lda.fit_transform(dtm)
    feature_names = vec.get_feature_names_out()
    labels = W.argmax(axis=1)

    clusters = []
    for tid in range(n_clusters):
        indices = [i for i, l in enumerate(labels) if l == tid]
        if not indices:
            continue
        top_words = [feature_names[i] for i in lda.components_[tid].argsort()[-10:][::-1]]
        clusters.append({
            "id": tid,
            "type": "content",
            "keywords": top_words,
            "size": len(indices),
            "item_indices": indices,
            "sample_texts": [texts[i][:200] for i in indices[:3]],
            "layer_mix": {},
        })
    coherence = _compute_coherence(texts, [c["keywords"] for c in clusters])
    return {"clusters": clusters, "coherence": coherence}


def _compute_coherence(texts: list[str], keyword_sets: list[list[str]]) -> float:
    if not keyword_sets:
        return 0.0
    try:
        from gensim.models.coherencemodel import CoherenceModel
        from gensim.corpora import Dictionary
        tokenized = [t.lower().split() for t in texts]
        dictionary = Dictionary(tokenized)
        corpus = [dictionary.doc2bow(doc) for doc in tokenized]
        cm = CoherenceModel(
            topics=keyword_sets,
            texts=tokenized,
            dictionary=dictionary,
            coherence="c_v",
        )
        return float(cm.get_coherence())
    except Exception:
        return 0.3


def _avg_sentiment(texts: list[str]) -> float:
    if not texts:
        return 0.0
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()
        scores = [sia.polarity_scores(t)["compound"] for t in texts if t]
        return round(sum(scores) / len(scores), 4) if scores else 0.0
    except Exception:
        return 0.0


def triage(items: list[dict], clusters: list[dict], percentile: float = 0.15) -> list[dict]:
    """Select top percentile by engagement within each layer."""
    triaged = []
    for layer in ("general", "field", "competitor"):
        layer_items = [i for i in items if i.get("layer") == layer and i.get("data_category") == "content"]
        if not layer_items:
            continue
        scores = sorted([i.get("engagement_score", 0) for i in layer_items], reverse=True)
        threshold = scores[max(0, int(len(scores) * percentile) - 1)]
        for item in layer_items:
            if item.get("engagement_score", 0) >= threshold:
                item["is_triaged"] = True
                triaged.append(item)
    return triaged
