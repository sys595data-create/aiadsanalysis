import os
import time
import requests
import gradio as gr

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

DEFAULT_SOURCES = [
    "youtube", "tiktok", "minea", "reddit",
    "amazon", "trustpilot", "walmart", "brand_sites", "meta_ads",
]

SOURCE_LABELS = {
    "youtube": "YouTube (organic)",
    "tiktok": "TikTok (organic + pipispy ads)",
    "minea": "Instagram Ads (Minea)",
    "reddit": "Reddit (VOC)",
    "amazon": "Amazon Reviews (VOC)",
    "trustpilot": "Trustpilot (VOC)",
    "walmart": "Walmart Reviews (VOC)",
    "brand_sites": "Brand Site Testimonials (VOC)",
    "meta_ads": "Meta Ads Library (text only)",
}

STATUS_ICONS = {
    "queued": "🕐",
    "ingesting": "🔄",
    "phase1": "🧠",
    "phase2": "🎬",
    "phase3": "✨",
    "done": "✅",
    "error": "❌",
}


# ─── API helpers ──────────────────────────────────────────────────────────────

def _post(path: str, data: dict):
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def _get(path: str):
    try:
        r = requests.get(f"{BACKEND_URL}{path}", timeout=15)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


# ─── Tab 1: New Run ───────────────────────────────────────────────────────────

def submit_run(markets, sources, min_views, date_from, date_to, max_items,
               q_eye, q_circ, q_spine, q_pemf):
    if not sources:
        return "❌ Select at least one source.", None

    query_config = {
        "eye_massager": {"extra_terms": q_eye.split("\n") if q_eye else []},
        "circulation_booster": {"extra_terms": q_circ.split("\n") if q_circ else []},
        "thermal_massage_bed": {"extra_terms": q_spine.split("\n") if q_spine else []},
        "pemf_infrared_mat": {"extra_terms": q_pemf.split("\n") if q_pemf else []},
    }

    payload = {
        "markets": markets,
        "sources": sources,
        "query_config": query_config,
        "min_views": int(min_views),
        "date_from": date_from or None,
        "date_to": date_to or None,
        "max_items": int(max_items),
    }

    result, err = _post("/api/runs", payload)
    if err:
        return f"❌ Error: {err}", None
    run_id = result["id"]
    return f"✅ Run started — ID: `{run_id}`\nStatus: {STATUS_ICONS.get(result['status'], '?')} {result['status']}", run_id


# ─── Tab 2: Monitor ───────────────────────────────────────────────────────────

def refresh_status(run_id: str):
    if not run_id or not run_id.strip():
        return "Enter a run ID above.", ""
    data, err = _get(f"/api/runs/{run_id.strip()}/status")
    if err:
        return f"Error: {err}", ""
    icon = STATUS_ICONS.get(data.get("status", ""), "?")
    status = data.get("status", "unknown")
    lines = [
        f"{icon} **{status.upper()}**",
        f"Items ingested: {data.get('item_count', 0)}",
        f"Clusters: {data.get('cluster_count', 0)}",
        f"Videos transcribed: {data.get('video_count', 0)}",
    ]
    if data.get("error_message"):
        lines.append(f"❌ Error: {data['error_message']}")
    return "\n".join(lines), status


def get_log(run_id: str, last_log_id: str = ""):
    if not run_id:
        return "", last_log_id
    params = f"?after_id={last_log_id}" if last_log_id else ""
    data, err = _get(f"/api/runs/{run_id.strip()}/log{params}")
    if err or not data:
        return "", last_log_id
    lines = [f"[{e['level'].upper()}] {e['ts'][:19]} — {e['message']}" for e in data]
    new_last = data[-1]["id"] if data else last_log_id
    return "\n".join(lines), new_last


# ─── Tab 3: Results ───────────────────────────────────────────────────────────

def load_runs():
    data, err = _get("/api/runs")
    if err or not data:
        return []
    rows = []
    for r in data:
        icon = STATUS_ICONS.get(r["status"], "?")
        rows.append([
            r["id"][:8] + "…",
            f"{icon} {r['status']}",
            r["started_at"][:16].replace("T", " "),
            r["item_count"],
            r["cluster_count"],
            r["video_count"],
            r["id"],
        ])
    return rows


def load_files(run_id_full: str):
    if not run_id_full:
        return "Select a run first.", []
    data, err = _get(f"/api/runs/{run_id_full}/files")
    if err:
        return f"Error: {err}", []
    files = data.get("files", [])
    if not files:
        msg = data.get("message", "No files available.")
        return msg, []
    links = []
    for f in files:
        links.append([f["label"], f["filename"], f["download_url"]])
    return f"✅ {len(files)} files ready for download", links


# ─── Build UI ─────────────────────────────────────────────────────────────────

with gr.Blocks(title="aiadsanalysis", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# aiadsanalysis — Market Intelligence Pipeline")
    gr.Markdown("Wellness hardware ad intelligence for US and ES markets.")

    with gr.Tabs():

        # ── Tab 1: New Run ────────────────────────────────────────────────────
        with gr.Tab("🚀 New Run"):
            with gr.Row():
                with gr.Column(scale=1):
                    markets_cb = gr.CheckboxGroup(
                        choices=["us", "es"],
                        value=["us"],
                        label="Markets",
                    )
                    sources_cb = gr.CheckboxGroup(
                        choices=list(SOURCE_LABELS.keys()),
                        value=DEFAULT_SOURCES,
                        label="Data Sources",
                        info="Uncheck sources to skip. Minea requires active session setup.",
                    )
                    min_views = gr.Slider(0, 500_000, value=10_000, step=1000, label="Min Views (video sources)")
                    max_items = gr.Slider(100, 2000, value=1000, step=100, label="Max Items per Run")
                    with gr.Row():
                        date_from = gr.Textbox(label="Date From (YYYY-MM-DD)", placeholder="2024-01-01")
                        date_to = gr.Textbox(label="Date To (YYYY-MM-DD)", placeholder="2025-01-01")

                with gr.Column(scale=1):
                    gr.Markdown("### Query Terms (one per line, optional — adds to defaults)")
                    q_eye = gr.Textbox(label="Eye Massager", lines=3, placeholder="eye massager review\ntherabody alternatives")
                    q_circ = gr.Textbox(label="Circulation Booster", lines=3, placeholder="revitive review\nleg circulation device")
                    q_spine = gr.Textbox(label="Thermal Massage Bed", lines=3, placeholder="ceragem review\njada massage bed")
                    q_pemf = gr.Textbox(label="PEMF / Infrared Mat", lines=3, placeholder="PEMF mat review\nhigherdose mat")

            run_btn = gr.Button("▶ Run Analysis", variant="primary", size="lg")
            run_status = gr.Markdown("Ready.")
            current_run_id = gr.State(None)

            run_btn.click(
                fn=submit_run,
                inputs=[markets_cb, sources_cb, min_views, date_from, date_to, max_items, q_eye, q_circ, q_spine, q_pemf],
                outputs=[run_status, current_run_id],
            )

        # ── Tab 2: Monitor ────────────────────────────────────────────────────
        with gr.Tab("📡 Monitor"):
            with gr.Row():
                monitor_run_id = gr.Textbox(label="Run ID", placeholder="paste run ID here")
                refresh_btn = gr.Button("Refresh", variant="secondary")

            status_md = gr.Markdown("Enter a run ID to monitor.")
            current_status_state = gr.State("")
            log_last_id = gr.State("")

            log_box = gr.Textbox(
                label="Live Log",
                lines=20,
                max_lines=30,
                interactive=False,
                show_copy_button=True,
            )

            def refresh_all(run_id, last_id):
                status_text, status_val = refresh_status(run_id)
                new_logs, new_last = get_log(run_id, last_id)
                return status_text, status_val, new_logs, new_last

            refresh_btn.click(
                fn=refresh_all,
                inputs=[monitor_run_id, log_last_id],
                outputs=[status_md, current_status_state, log_box, log_last_id],
            )

            # Auto-populate from new run tab
            current_run_id.change(
                fn=lambda rid: rid or "",
                inputs=[current_run_id],
                outputs=[monitor_run_id],
            )

        # ── Tab 3: Results ────────────────────────────────────────────────────
        with gr.Tab("📦 Results"):
            refresh_runs_btn = gr.Button("Refresh Run List", variant="secondary")

            runs_table = gr.Dataframe(
                headers=["ID", "Status", "Started", "Items", "Clusters", "Videos", "Full ID"],
                datatype=["str", "str", "str", "number", "number", "number", "str"],
                label="All Runs",
                interactive=False,
            )

            selected_run_id = gr.Textbox(label="Selected Run ID (paste from table)", placeholder="full run UUID")
            load_files_btn = gr.Button("Load Files", variant="primary")

            files_status = gr.Markdown("")
            files_table = gr.Dataframe(
                headers=["File", "Filename", "Download URL"],
                datatype=["str", "str", "str"],
                label="Output Files",
                interactive=False,
            )

            refresh_runs_btn.click(fn=load_runs, outputs=[runs_table])
            load_files_btn.click(fn=load_files, inputs=[selected_run_id], outputs=[files_status, files_table])

        # ── Tab 4: Help ────────────────────────────────────────────────────────
        with gr.Tab("ℹ Help"):
            gr.Markdown("""
## Quick Start

1. **New Run** tab → select markets and sources → click **Run Analysis**
2. Copy the Run ID → paste into **Monitor** tab → click Refresh to watch progress
3. When status shows ✅ **done** → go to **Results** tab → paste Run ID → **Load Files**
4. Download output files (Excel, JSON, Markdown)

## Run Duration

A full run (all sources, US+ES) typically takes **3–4 hours** on RunPod GPU.
- Phase 0 (ingestion): 20–60 min depending on sources
- Phase 1 (NLP): 10–20 min
- Phase 2 (Whisper + YOLO): 2–3 hours
- Phase 3 (Groq synthesis): 5–10 min

## Output Files

| File | Contents |
|------|----------|
| `11_market_intelligence.xlsx` | All data in 9 Excel sheets |
| `09_customer_pain_analytics.json` | VOC pain map + word cloud |
| `04_recipes.json` | Creative video recipes per cluster |
| `10_ad_analytics.json` | Competitor ad hook analysis |
| `07_run_report.md` | Executive summary (LLM-written) |
| `08_home_demo_hypothesis.json` | Home vs studio engagement analysis |

## Sources

| Source | What it scrapes |
|--------|----------------|
| YouTube | Organic videos — titles, descriptions, engagement |
| TikTok | Organic + pipispy ad API (direct video URL) |
| Instagram Ads | Minea Playwright XHR (requires active Minea session) |
| Reddit | Posts + comments from 60+ subreddits |
| Amazon | Product reviews (US + ES) |
| Trustpilot | Brand reviews |
| Walmart | Product reviews (US only) |
| Brand Sites | Competitor testimonial pages |
| Meta Ads Library | Ad copy text only (video not downloadable) |
""")

demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)), share=False)
