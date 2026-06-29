import json
from openai import OpenAI


def _client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def synthesise_voc(clusters: list[dict], api_key: str, base_url: str) -> dict:
    if not api_key:
        return _stub_voc(clusters)
    client = _client(api_key, base_url)
    cluster_text = json.dumps([
        {"id": c["id"], "keywords": c["keywords"][:10], "samples": c["sample_texts"][:3]}
        for c in clusters[:20]
    ], ensure_ascii=False)

    prompt = f"""You are a market research analyst for wellness hardware (US/ES markets).
Analyse these VOC clusters and produce a customer pain intelligence report.

Clusters:
{cluster_text}

Respond as JSON with this structure:
{{
  "primary_pains": [{{"pain": "...", "intensity": 7, "cluster_ids": [1,2]}}],
  "emotional_states": ["frustrated", "hopeful", ...],
  "failed_solutions": ["tried X but...", ...],
  "language_patterns": ["they say '...'" , ...],
  "opportunities": [{{"gap": "...", "hook": "..."}}],
  "word_cloud_terms": {{"term": frequency, ...}}
}}"""

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        return {**_stub_voc(clusters), "error": str(e)}


def synthesise_recipes(clusters: list[dict], transcripts: list[dict], api_key: str, base_url: str) -> list[dict]:
    if not api_key:
        return _stub_recipes(clusters)
    client = _client(api_key, base_url)
    recipes = []
    for cluster in clusters[:10]:
        sample_transcripts = [t["transcript"] for t in transcripts if t.get("cluster_id") == cluster["id"]][:3]
        prompt = f"""You are a direct response video strategist for wellness hardware.
Create a creative recipe for this content cluster.

Cluster keywords: {cluster['keywords'][:10]}
Sample transcripts: {json.dumps(sample_transcripts[:2], ensure_ascii=False)}

Respond as JSON:
{{
  "hook_architecture": {{"first_3s": "...", "hook_type": "pain|curiosity|social_proof|demo", "opening_line": "..."}},
  "setting": {{"type": "home|studio|outdoor", "lighting": "...", "recommendation": "..."}},
  "script_outline": [{{"second": 0, "action": "..."}}],
  "competitor_gaps": ["gap 1", "gap 2"],
  "visual_signals": ["signal 1", ...],
  "engagement_prediction": "high|medium|low",
  "market": "{cluster.get('market', 'us')}"
}}"""
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=1000,
            )
            recipe = json.loads(resp.choices[0].message.content)
            recipe["cluster_id"] = cluster["id"]
            recipe["cluster_keywords"] = cluster["keywords"]
            recipes.append(recipe)
        except Exception as e:
            recipes.append({"cluster_id": cluster["id"], "error": str(e)})
    return recipes


def synthesise_ad_analytics(clusters: list[dict], api_key: str, base_url: str) -> dict:
    if not api_key:
        return _stub_ads()
    client = _client(api_key, base_url)
    cluster_text = json.dumps([
        {"id": c["id"], "keywords": c["keywords"][:8], "samples": c["sample_texts"][:2]}
        for c in clusters[:15]
    ], ensure_ascii=False)
    prompt = f"""Analyse these ad copy clusters from competitor TikTok/Instagram ads.

Clusters:
{cluster_text}

Respond as JSON:
{{
  "top_hooks": [{{"hook": "...", "cluster_id": 1, "why_it_works": "..."}}],
  "audience_segments": [{{"segment": "...", "signals": ["..."]}}],
  "usp_positions": [{{"usp": "...", "frequency": "high|medium|low"}}],
  "missing_angles": ["angle not covered by competitors"],
  "creative_patterns": [{{"pattern": "...", "performance": "high|medium"}}]
}}"""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        return {**_stub_ads(), "error": str(e)}


def synthesise_run_report(stats: dict, api_key: str, base_url: str) -> str:
    if not api_key:
        return "Run completed. Synthesis not available (no Groq API key set)."
    client = _client(api_key, base_url)
    prompt = f"""Write a 300-word executive summary of this market intelligence run.
Stats: {json.dumps(stats, ensure_ascii=False)[:2000]}
Focus on: key pain signals found, strongest ad hooks observed, market gaps, recommended next actions."""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=600,
        )
        return resp.choices[0].message.content
    except Exception:
        return "Run completed. Report generation failed."


def analyse_home_demo(triaged: list[dict]) -> dict:
    home_items = [i for i in triaged if "home" in str(i.get("visual_concepts", [])).lower()]
    studio_items = [i for i in triaged if i not in home_items and i.get("engagement_score")]
    home_eng = sum(i.get("engagement_score", 0) for i in home_items) / max(len(home_items), 1)
    studio_eng = sum(i.get("engagement_score", 0) for i in studio_items) / max(len(studio_items), 1)
    lift = (home_eng / studio_eng - 1) if studio_eng > 0 else 0
    return {
        "home_demo_count": len(home_items),
        "studio_count": len(studio_items),
        "home_avg_engagement": round(home_eng, 4),
        "studio_avg_engagement": round(studio_eng, 4),
        "lift": round(lift, 4),
        "recommendation": "Prioritise home-demo format" if lift > 0.1 else "No clear home-demo advantage",
    }


def _stub_voc(clusters):
    return {"primary_pains": [], "emotional_states": [], "failed_solutions": [], "opportunities": [], "word_cloud_terms": {}, "note": "stub"}

def _stub_recipes(clusters):
    return [{"cluster_id": c["id"], "note": "stub"} for c in clusters]

def _stub_ads():
    return {"top_hooks": [], "audience_segments": [], "usp_positions": [], "missing_angles": [], "note": "stub"}
