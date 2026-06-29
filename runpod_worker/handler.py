"""
RunPod Serverless handler — entry point for the GPU worker.
Runs the full pipeline: ingestion → Phase 1 NLP → Phase 2 video → Phase 3 synthesis → export → R2 upload.
"""
import os
import sys
import json
import tempfile
import traceback
from datetime import datetime

# Allow imports from the repo root
sys.path.insert(0, "/app")

import runpod
import boto3
from botocore.client import Config

# ─── Local imports ────────────────────────────────────────────────────────────
from runpod_worker.phase1_nlp import cluster_items, triage
from runpod_worker.phase2_video import process_videos
from runpod_worker.yolo_analysis import analyse_frames


def handler(job):
    inp = job.get("input", {})
    run_id = inp.get("run_id")
    if not run_id:
        return {"error": "Missing run_id"}

    try:
        return _run_pipeline(inp)
    except Exception as e:
        tb = traceback.format_exc()
        _db_log(inp, run_id, f"Fatal error: {e}\n{tb}", "error")
        _db_set_status(inp, run_id, "error", error_message=str(e))
        return {"error": str(e), "traceback": tb}


def _run_pipeline(cfg: dict) -> dict:
    run_id = cfg["run_id"]
    markets = cfg.get("markets", ["us"])
    sources = cfg.get("sources", [])
    query_config = cfg.get("query_config", {})
    r2_prefix = cfg.get("r2_prefix", f"runs/{run_id}")
    temp_dir = "/tmp/aiads"
    os.makedirs(temp_dir, exist_ok=True)

    _db_set_status(cfg, run_id, "ingesting")
    _db_log(cfg, run_id, "Phase 0: Ingestion starting")

    # ── Phase 0: Ingestion ────────────────────────────────────────────────────
    all_items = []
    ingestion_cfg = {**cfg, **query_config}

    source_map = {
        "youtube":     ("backend.ingestion.youtube",     "scrape"),
        "tiktok":      ("backend.ingestion.tiktok",      "scrape"),
        "minea":       ("backend.ingestion.minea",       "scrape"),
        "meta_ads":    ("backend.ingestion.meta_ads",    "scrape"),
        "reddit":      ("backend.ingestion.reddit",      "scrape"),
        "amazon":      ("backend.ingestion.amazon",      "scrape"),
        "trustpilot":  ("backend.ingestion.trustpilot",  "scrape"),
        "walmart":     ("backend.ingestion.walmart",     "scrape"),
        "brand_sites": ("backend.ingestion.brand_sites", "scrape"),
    }

    for src in sources:
        if src not in source_map:
            continue
        module_path, fn_name = source_map[src]
        try:
            import importlib
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name)
            result = fn(markets, sources, ingestion_cfg)
            count = len(result)
            all_items.extend([i.to_dict() for i in result])
            _db_log(cfg, run_id, f"  {src}: {count} items")
        except Exception as e:
            _db_log(cfg, run_id, f"  {src} failed: {e}", "warning")

    max_items = cfg.get("max_items_per_run", 2000)
    all_items = all_items[:max_items]
    _db_log(cfg, run_id, f"Phase 0 done: {len(all_items)} total items")

    _upload_r2(cfg, f"{r2_prefix}/01_raw_content.json", all_items)
    _db_set_status(cfg, run_id, "phase1", item_count=len(all_items))

    # ── Phase 1: NLP Clustering ───────────────────────────────────────────────
    _db_log(cfg, run_id, "Phase 1: NLP clustering")

    content_items = [i for i in all_items if i.get("data_category") == "content"]
    voc_items = [i for i in all_items if i.get("data_category") == "voc"]
    ad_items = [i for i in all_items if i.get("data_category") == "ad"]

    n_clusters = max(5, min(15, len(content_items) // 20))
    content_result = cluster_items(content_items, n_clusters)
    voc_result = cluster_items(voc_items, max(5, min(12, len(voc_items) // 15)))
    ad_result = cluster_items(ad_items, max(4, min(10, len(ad_items) // 10)))

    # Label cluster types
    for c in content_result.get("clusters", []):
        c["type"] = "content"
        c["layer_mix"] = _layer_mix(content_items, c.get("item_indices", []))
    for c in voc_result.get("clusters", []):
        c["type"] = "voc"
    for c in ad_result.get("clusters", []):
        c["type"] = "ad"

    all_clusters = {
        "content_clusters": content_result.get("clusters", []),
        "voc_clusters": voc_result.get("clusters", []),
        "ad_clusters": ad_result.get("clusters", []),
        "coherence_scores": {
            "content": content_result.get("coherence_scores", {}),
            "voc": voc_result.get("coherence_scores", {}),
            "ad": ad_result.get("coherence_scores", {}),
        },
    }
    _upload_r2(cfg, f"{r2_prefix}/02_clusters.json", all_clusters)
    cluster_count = len(all_clusters["content_clusters"]) + len(all_clusters["voc_clusters"]) + len(all_clusters["ad_clusters"])
    _db_log(cfg, run_id, f"Phase 1 done: {cluster_count} clusters")
    _db_set_status(cfg, run_id, "phase2", cluster_count=cluster_count)

    # ── Phase 1b: Triage ─────────────────────────────────────────────────────
    triaged = triage(content_items, content_result.get("clusters", []))
    _db_log(cfg, run_id, f"Triage: {len(triaged)} items selected for video processing")

    # ── Phase 2: Video + YOLO ─────────────────────────────────────────────────
    _db_log(cfg, run_id, "Phase 2: Video download + transcription + YOLO")
    processed = process_videos(triaged, temp_dir, cfg.get("yolo_model_path"))

    yolo_mode = cfg.get("yolo_mode", "yolo")
    for item in processed:
        frame_paths = item.pop("frame_paths", [])
        if frame_paths:
            visual = analyse_frames(frame_paths, cfg.get("yolo_model_path", "/models/best.pt"), yolo_mode)
            item.update(visual)

    video_count = len([i for i in processed if i.get("transcript")])
    _upload_r2(cfg, f"{r2_prefix}/03_triaged.json", processed)
    _db_log(cfg, run_id, f"Phase 2 done: {video_count} videos transcribed")
    _db_set_status(cfg, run_id, "phase3", video_count=video_count)

    # ── Phase 3: Synthesis ────────────────────────────────────────────────────
    _db_log(cfg, run_id, "Phase 3: Groq synthesis")
    from backend.pipeline.phase3_synthesis import (
        synthesise_voc, synthesise_recipes, synthesise_ad_analytics,
        synthesise_run_report, analyse_home_demo,
    )
    api_key = cfg.get("grok_api_key", "")
    base_url = cfg.get("grok_api_base", "https://api.groq.com/openai/v1")

    voc_analytics = synthesise_voc(all_clusters["voc_clusters"], api_key, base_url)
    recipes = synthesise_recipes(all_clusters["content_clusters"], processed, api_key, base_url)
    ad_analytics = synthesise_ad_analytics(all_clusters["ad_clusters"], api_key, base_url)
    home_demo = analyse_home_demo(processed)

    stats = {
        "run_id": run_id,
        "total_items": len(all_items),
        "by_source": _count_by(all_items, "source"),
        "by_market": _count_by(all_items, "market"),
        "by_category": _count_by(all_items, "data_category"),
        "cluster_count": cluster_count,
        "videos_transcribed": video_count,
        "generated_at": datetime.utcnow().isoformat(),
    }

    run_report = synthesise_run_report(stats, api_key, base_url)

    # Upload phase 3 outputs
    _upload_r2(cfg, f"{r2_prefix}/04_recipes.json", recipes)
    _upload_r2(cfg, f"{r2_prefix}/05_statistics.json", stats)
    _upload_r2(cfg, f"{r2_prefix}/07_run_report.md", run_report, text=True)
    _upload_r2(cfg, f"{r2_prefix}/08_home_demo_hypothesis.json", home_demo)
    _upload_r2(cfg, f"{r2_prefix}/09_customer_pain_analytics.json", voc_analytics)
    _upload_r2(cfg, f"{r2_prefix}/10_ad_analytics.json", ad_analytics)

    # Recipe templates markdown
    recipe_md = _build_recipe_md(recipes)
    _upload_r2(cfg, f"{r2_prefix}/06_recipe_templates.md", recipe_md, text=True)

    # Excel
    from backend.export.excel_export import build_excel
    xlsx_bytes = build_excel(all_items, all_clusters, processed, recipes, stats, voc_analytics, ad_analytics, run_id)
    _upload_r2_bytes(cfg, f"{r2_prefix}/11_market_intelligence.xlsx", xlsx_bytes,
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    _db_log(cfg, run_id, "All outputs uploaded to R2")
    _db_set_status(cfg, run_id, "done", completed_at=datetime.utcnow().isoformat(),
                   item_count=len(all_items), cluster_count=cluster_count, video_count=video_count)

    return {
        "status": "done",
        "item_count": len(all_items),
        "cluster_count": cluster_count,
        "video_count": video_count,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _r2_client(cfg: dict):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['r2_account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["r2_access_key_id"],
        aws_secret_access_key=cfg["r2_secret_access_key"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _upload_r2(cfg: dict, key: str, data, text: bool = False):
    client = _r2_client(cfg)
    if text:
        body = data.encode("utf-8") if isinstance(data, str) else data
        ct = "text/markdown"
    else:
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        ct = "application/json"
    client.put_object(Bucket=cfg["r2_bucket_name"], Key=key, Body=body, ContentType=ct)


def _upload_r2_bytes(cfg: dict, key: str, data: bytes, content_type: str):
    client = _r2_client(cfg)
    client.put_object(Bucket=cfg["r2_bucket_name"], Key=key, Body=data, ContentType=content_type)


def _db_set_status(cfg: dict, run_id: str, status: str, **kwargs):
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(cfg.get("db_url", ""))
        updates = {"status": status, **kwargs}
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        with engine.connect() as conn:
            conn.execute(text(f"UPDATE runs SET {set_clause} WHERE id = :run_id"), {**updates, "run_id": run_id})
            conn.commit()
    except Exception:
        pass


def _db_log(cfg: dict, run_id: str, message: str, level: str = "info"):
    import uuid
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(cfg.get("db_url", ""))
        with engine.connect() as conn:
            conn.execute(
                text("INSERT INTO run_logs (id, run_id, message, level) VALUES (:id, :run_id, :message, :level)"),
                {"id": str(uuid.uuid4()), "run_id": run_id, "message": message, "level": level},
            )
            conn.commit()
    except Exception:
        print(f"[{level.upper()}] {message}")


def _count_by(items: list[dict], key: str) -> dict:
    counts = {}
    for item in items:
        v = item.get(key, "unknown")
        counts[v] = counts.get(v, 0) + 1
    return counts


def _layer_mix(items: list[dict], indices: list[int]) -> dict:
    mix = {}
    for idx in indices:
        if idx < len(items):
            layer = items[idx].get("layer", "unknown")
            mix[layer] = mix.get(layer, 0) + 1
    return mix


def _build_recipe_md(recipes: list[dict]) -> str:
    lines = ["# Creative Recipe Templates\n"]
    for r in recipes:
        cid = r.get("cluster_id", "?")
        market = r.get("market", "us").upper()
        hook = r.get("hook_architecture", {})
        lines.append(f"## Cluster {cid} — {market}\n")
        lines.append(f"**Hook type**: {hook.get('hook_type', '')}")
        lines.append(f"**Opening line**: {hook.get('opening_line', '')}")
        setting = r.get("setting", {})
        lines.append(f"**Setting**: {setting.get('type', '')} — {setting.get('recommendation', '')}")
        gaps = r.get("competitor_gaps", [])
        if gaps:
            lines.append(f"**Competitor gaps**: {'; '.join(gaps)}")
        lines.append("")
    return "\n".join(lines)


runpod.serverless.start({"handler": handler})
