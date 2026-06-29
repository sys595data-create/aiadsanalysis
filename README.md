# aiadsanalysis

AI-powered market intelligence pipeline for wellness hardware — US and ES markets. Ingests ad creatives, organic video, and voice-of-customer data from 9 sources, processes through NLP clustering and GPU-accelerated video analysis, and synthesises actionable creative recipes and customer pain maps via LLM.

---

## Architecture

```
Browser
  │  always available
  ▼
Gradio Frontend  ──────────────────────────────  Railway Pro
  │  REST calls
  ▼
FastAPI Backend  ──────────────────────────────  Railway Pro
  │   │
  │   └── Railway PostgreSQL  (run metadata, clusters, recipes)
  │
  │  triggered per user run
  ▼
RunPod Serverless GPU  (RTX 3090 / A5000)
  ├── pipispy API          → TikTok ad video_url → download
  ├── Minea Playwright     → Instagram ad XHR → CDN URL → download
  ├── yt-dlp               → YouTube + TikTok organic video → download
  ├── Playwright scrapers  → Amazon reviews, Walmart, Meta Ads text
  ├── Reddit PRAW          → posts + comments (60+ subreddits)
  ├── Trustpilot / Brand sites → review text
  ├── Whisper large-v3-turbo  → transcription
  ├── YOLOv11s             → per-frame visual analysis
  ├── BERTopic / NMF / LDA → NLP clustering
  └── Groq API             → VOC synthesis + creative recipes
        │
        └── results → Railway PostgreSQL + Cloudflare R2
  ▼
Frontend renders results, serves download links from R2
```

---

## Data Sources

### Ad Intelligence

| Source | Method | Markets | What we extract |
|--------|--------|---------|-----------------|
| TikTok ads | pipispy REST API | US / ES | ad copy, `video_url`, impressions tier, likes/shares/comments, date range, brand |
| Instagram / Meta ads | Minea Pro — Playwright XHR interception | US / ES | ad copy, CDN video URL, engagement, lifecycle dates |
| Meta Ads Library | Playwright | US / ES | ad copy text only (video download technically impossible) |
| YouTube organic | yt-dlp | US / ES | video, metadata, view/like counts |
| TikTok organic | yt-dlp | US / ES | video, hashtags, view/like/comment counts |

### Voice of Customer (VOC)

| Source | Method | Markets | What we extract |
|--------|--------|---------|-----------------|
| Reddit | PRAW (official API) + public JSON fallback | US / ES | posts + top 10 comments, upvote ratio, engagement score |
| Amazon | Playwright (JS rendering) | US (`amazon.com`) / ES (`amazon.es`) | star rating, review text, verified badge, helpful votes |
| Trustpilot | requests + BeautifulSoup (JSON-LD) | US / ES | review text, rating, date |
| Walmart | Playwright + JSON-LD fallback | US | review text, rating, helpful votes |
| Brand sites | requests + BeautifulSoup | US / ES | testimonials from competitor / brand pages |

> No Apify. No instagrapi. Reddit uses PRAW when credentials are set, public JSON endpoints otherwise — no account required.

---

## Pipeline

### Phase 0 — Ingestion (CPU, Railway backend → RunPod)

All sources queried across **3 layers × 2 markets**:

- `general` — trending wellness / biohacking influencer content
- `field` — direct device reviews, adjacent wellness (PEMF, cold plunge, red light)
- `competitor` — 8 specific brands: Ceragem, Migun, HealthyLine, HigherDOSE, Therabody, Renpho, Bob & Brad, Revitive

Items tagged with: `source`, `market` (us/es), `layer`, `data_category` (content / voc / ad), `engagement_score`.

### Phase 1 — NLP Clustering (CPU, RunPod)

- **Models competed**: BERTopic vs NMF+KMeans vs LDA — winner selected by Gensim coherence (C_v)
- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` (multilingual EN + ES)
- **Sentiment**: VADER per item
- **Triage**: top 15% by engagement within each layer (proportional, not dominated by viral outliers)
- Separate cluster sets for `content`, `voc`, and `ad` data categories

### Phase 2 — GPU Processing (RunPod, triggered by backend)

- **Video download**: yt-dlp → 360p MP4 → ffmpeg → MP3 + keyframes (1 frame / 2.5 s), 80 MB cap
- **Whisper large-v3-turbo** (809 MB): multilingual transcription (EN for US, ES for ES)
- **YOLOv11s** (22 MB, custom-trained on wellness products): per-frame object detection — bounding boxes, class, confidence, timeline
  - Detects: eye massager, PEMF mat, red light panel, cervical device, heating pad, circulation booster, person, home setting vs studio
  - Replaces ImageBind (2 GB) — faster, more interpretable, smaller memory footprint
- **Phase 1b re-cluster**: if ≥ 8 transcripts, re-run clustering on Whisper speech text

### Phase 3 — Synthesis (RunPod → Groq API)

- **VOC map**: cluster text → Niche → Symptom → Competitor Objection → Counter-Hook
- **Creative recipes**: per cluster → hook architecture (first 3 s), setting evaluation, script outline, competitor gaps
- **Pain analytics**: primary pain, intensity (1–10), failed solutions, emotional state, opportunity
- **Ad analytics**: primary hook, target audience, USP, missing opportunities, success signals
- **Home Demo Hypothesis**: do home-demo videos outperform studio content? Engagement lift analysis
- Models: `llama-3.3-70b-versatile` (VOC + pain), `llama-3.2-11b-vision-preview` (recipes)

---

## Output Files (per run, stored in Cloudflare R2)

| File | Description |
|------|-------------|
| `01_raw_content.json` | All ingested items with engagement scores |
| `02_clusters.json` | Phase 1 cluster results (content, voc, ad) |
| `03_triaged.json` | Top 15% items with transcripts and YOLO visual concepts |
| `04_recipes.json` | Creative recipes per cluster |
| `05_statistics.json` | Aggregated stats by source, layer, market |
| `06_recipe_templates.md` | Human-readable production briefs |
| `07_run_report.md` | LLM-narrated executive summary |
| `08_home_demo_hypothesis.json` | Home demo vs studio engagement analysis |
| `09_customer_pain_analytics.json` | VOC synthesis — pain map, word cloud |
| `10_ad_analytics.json` | Ad cluster intelligence |
| `11_market_intelligence.xlsx` | 9-sheet workbook (all of the above in Excel) |

All files downloadable from the Gradio UI via R2 signed URLs.

---

## Infrastructure

| Service | Purpose | Cost |
|---------|---------|------|
| Railway Pro | FastAPI backend + Gradio frontend (one project) | ~$20/mo |
| Railway PostgreSQL | Run metadata, clusters, recipes | ~$5–10/mo (usage-based) |
| RunPod Serverless | GPU compute — spins up per run, shuts down when done | ~$1–2.50/run |
| Cloudflare R2 | Output file storage, zero egress cost | ~$1–3/mo |
| pipispy (PiPiADS) | TikTok ad intelligence API | $77–155/mo |
| Minea Pro | Instagram / Meta ad intelligence | $99/mo |
| Groq API | LLM synthesis (Phase 3) | pay-per-token |

**Total estimated**: $120–300/mo depending on pipispy tier and run frequency.

GPU is **never idle** — RunPod pod spins up only when user clicks "Run Analysis" in the UI, executes the full pipeline, writes results to PostgreSQL + R2, shuts down. Payment is per-second.

---

## Repository Structure

```
aiadsanalysis/
├── backend/
│   ├── main.py                    FastAPI app, CORS, startup
│   ├── config.py                  Pydantic settings (all env vars)
│   ├── db.py                      SQLAlchemy models → Railway PostgreSQL
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── routes/
│   │   ├── runs.py                POST /runs, GET /runs, GET /runs/{id}/status
│   │   └── files.py               GET /runs/{id}/files → R2 signed URLs
│   ├── ingestion/
│   │   ├── base.py                ContentItem dataclass
│   │   ├── youtube.py             yt-dlp organic
│   │   ├── tiktok.py              yt-dlp organic + pipispy ads API
│   │   ├── minea.py               Playwright XHR interception → Instagram ad video
│   │   ├── meta_ads.py            Playwright → Meta Ads Library text
│   │   ├── reddit.py              PRAW + public JSON, 60+ subreddits
│   │   ├── amazon.py              Playwright, amazon.com + amazon.es
│   │   ├── trustpilot.py          requests + BS4, JSON-LD
│   │   ├── walmart.py             Playwright + JSON-LD fallback
│   │   └── brand_sites.py         requests + BS4, testimonial pages
│   ├── pipeline/
│   │   ├── orchestrator.py        Async phase coordination, triggers RunPod
│   │   ├── runpod_client.py       RunPod serverless API client
│   │   └── phase3_synthesis.py    Groq API synthesis
│   ├── voc/
│   │   ├── categories.py          Product categories, brands, query terms
│   │   └── classify.py            VOC theme classifier (LLM or keyword fallback)
│   ├── storage/
│   │   └── r2.py                  Cloudflare R2 via boto3
│   └── export/
│       └── excel_export.py        9-sheet XLSX workbook builder
│
├── runpod_worker/
│   ├── handler.py                 RunPod serverless entry point
│   ├── phase1_nlp.py              BERTopic / NMF / LDA clustering
│   ├── phase2_video.py            Whisper transcription + frame extraction
│   ├── yolo_analysis.py           YOLOv11s inference on keyframes
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── app.py                     Gradio UI
│   ├── Dockerfile
│   └── requirements.txt
│
├── .github/workflows/
│   ├── deploy-backend.yml         Auto-deploy backend to Railway on push
│   ├── deploy-frontend.yml        Auto-deploy frontend to Railway on push
│   └── build-runpod.yml           Build + push RunPod Docker image to Docker Hub
│
├── .env.example
└── railway.toml
```

---

## Gradio UI

**Tab 1 — New Run**
- Editable query rows per product category (pre-populated with default search terms)
- Source toggles: YouTube / TikTok / Instagram Ads / Reddit / Amazon / Trustpilot / Walmart / Brand Sites / Meta Ads
- Market selector: US / ES / Both
- Sliders: minimum views, date range start/end, max items per run
- "Run Analysis" button → POST `/runs` → returns `run_id`

**Tab 2 — Results**
- Dropdown of all past runs with status badge (queued / ingesting / phase1 / phase2 / phase3 / done / error)
- Auto-refreshes every 10 s while a run is active
- Per-file download buttons (served from R2 signed URLs, 24 h expiry)
- Run summary card: item counts by source, cluster count, runtime

**Tab 3 — Live Log**
- Polling stream of run log lines (GET `/runs/{id}/log`)

---

## Setup

### 1. Cloudflare R2

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → R2 → Create bucket → name: `aiadsanalysis`
2. R2 → Manage R2 API tokens → Create token (read + write)
3. Note: `Account ID`, `Access Key ID`, `Secret Access Key`

### 2. Railway

1. Create new project → Add service → GitHub repo → select `aiadsanalysis`, root path `backend/`
2. Add second service → same repo, root path `frontend/`
3. Add Railway PostgreSQL plugin to the backend service (auto-sets `DATABASE_URL`)
4. Set environment variables (see section below)

### 3. RunPod

1. Build and push the worker image:
   ```bash
   cd runpod_worker
   docker build -t yourdockerhub/aiadsanalysis-worker:latest .
   docker push yourdockerhub/aiadsanalysis-worker:latest
   ```
2. RunPod dashboard → Serverless → New Endpoint → select your image
3. GPU: RTX 3090 or A5000 (24 GB VRAM)
4. Note: `Endpoint ID`

### 4. YOLO Model (one-time)

1. Collect ~2 000 keyframe screenshots from TikTok/Instagram/Amazon product pages
2. Upload to [Roboflow](https://roboflow.com) (free tier) — use AI-assisted labelling (SAM) to annotate bounding boxes for each product class
3. Export dataset → upload ZIP to [Ultralytics HUB](https://hub.ultralytics.com) → train YOLOv11s on T4 GPU (~3–5 hours, covered by free $25 credits)
4. Download `best.pt` → upload to RunPod volume or include in Docker image

Alternatively, use **Grounding DINO** (zero-shot, no training): set `YOLO_MODE=grounding_dino` in env vars. Slower (300–800 ms/frame vs 80–200 ms) but requires no dataset.

### 5. Minea Session (one-time)

Run the setup script once to save a Playwright browser session:
```bash
python backend/ingestion/minea_setup.py
```
A browser window opens — log in to Minea manually. Session is saved to `.minea_profile/` and reused on every subsequent run.

---

## Environment Variables

### Backend (Railway)

```env
# Database — auto-set by Railway PostgreSQL plugin
DATABASE_URL=postgresql://...

# Cloudflare R2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=aiadsanalysis

# RunPod
RUNPOD_API_KEY=
RUNPOD_ENDPOINT_ID=

# TikTok Ads
PIPISPY_API_KEY=
PIPISPY_BASE_URL=https://api.pipiads.com/api/v1

# Minea
MINEA_EMAIL=
MINEA_PASSWORD=
MINEA_PROFILE_DIR=.minea_profile

# Reddit (optional — falls back to public JSON if not set)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=aiadsanalysis/1.0

# YouTube (optional — yt-dlp works without)
YOUTUBE_API_KEY=

# Groq synthesis
GROK_API_KEY=
GROK_API_BASE=https://api.groq.com/openai/v1

# Proxy (optional — for Amazon/Walmart anti-bot)
PROXY_URL=

# YOLO
YOLO_MODEL_PATH=/models/best.pt
YOLO_MODE=yolo  # or grounding_dino

# App
OUTPUT_DIR=output
TEMP_DIR=tmp
FRONTEND_URL=https://your-frontend.railway.app
```

### Frontend (Railway)

```env
BACKEND_URL=https://your-backend.railway.app
```

---

## Product Categories

Four research categories (defined in `backend/voc/categories.py`):

| Category | Competitor brands | Our product |
|----------|------------------|-------------|
| Eye massagers | Therabody SmartGoggles, Renpho Eyeris, Bob & Brad, Naipo, EyeOasis | EyeSystem |
| Circulation boosters | Revitive, Nooro, Auvon | BodyHealth |
| Thermal massage beds | Ceragem, Migun | SpineSystem |
| Infrared / PEMF mats | HealthyLine, HigherDOSE, Biomat | SleepSystem |

General wellness adjacencies tracked: PEMF, cold plunge, red light therapy, biohacking, sleep tech, longevity, home recovery, Huberman-adjacent content.

---

## Reddit Coverage

60+ subreddits across US and ES markets, including:

**US — General wellness**: r/biohacking, r/longevity, r/selfcare, r/wellness, r/holistic  
**US — Field (pain / recovery)**: r/ChronicPain, r/backpain, r/Fibromyalgia, r/sleep, r/insomnia, r/massage, r/physicaltherapy, r/scoliosis, r/PEMF  
**US — Competitor**: r/Therabody, r/recoverytech, r/infraredsauna, r/coldplunge  
**ES — General**: r/es, r/spain, r/AskSpain  
**ES — Field**: r/Salud, r/Fisioterapia, r/bienestares  

Search terms per category include both English and Spanish variants. PRAW used when `REDDIT_CLIENT_ID` is set; falls back to `old.reddit.com` JSON endpoints otherwise.

---

## VOC Classification

Each review / post / comment is classified into one of four themes:

| Theme | Description |
|-------|-------------|
| Pain / Symptom | Customer describes a problem they have |
| Fear / Objection | Doubt, scepticism, concern about the product |
| Positive | Satisfied experience, outcome, recommendation |
| Competitor mention | References a named competing brand |

Classification uses Claude API (structured output) when `ANTHROPIC_API_KEY` is set; falls back to keyword matching otherwise.

---

## Cost Scenarios

**Recommended stack** (~$300–311/mo):

| Line item | Service | Cost/mo |
|-----------|---------|---------|
| Frontend + Backend | Railway Pro | $20 |
| Database | Railway PostgreSQL | $5–10 |
| GPU compute | RunPod Serverless | $1–2.50/run |
| File storage | Cloudflare R2 | $1–3 |
| TikTok ads | pipispy Pro | $155 |
| Instagram ads | Minea Pro | $99 |
| YOLO training | Ultralytics HUB | $0–2 one-time |

**Budget stack** (~$120/mo): use pipispy Basic ($77), skip Minea (Meta Ads text only — no Instagram video), Railway PostgreSQL stays.

---

## Subscriptions You Need

- [railway.com](https://railway.com) — Pro plan
- [runpod.io](https://www.runpod.io) — Serverless, pay-per-second
- [dash.cloudflare.com](https://dash.cloudflare.com) — R2 object storage
- [pipispy.com](https://www.pipispy.com) — TikTok ad API (Basic or Pro)
- [app.minea.com](https://app.minea.com) — Instagram/Meta ad intelligence (Pro)
- [groq.com](https://console.groq.com) — LLM synthesis

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
