from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://localhost/aiadsanalysis"

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "aiadsanalysis"

    # RunPod
    runpod_api_key: str = ""
    runpod_endpoint_id: str = ""

    # pipispy (PiPiADS API)
    pipispy_api_key: str = ""
    pipispy_base_url: str = "https://api.pipiads.com/api/v1"

    # Minea
    minea_email: str = ""
    minea_password: str = ""
    minea_profile_dir: str = ".minea_profile"

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "aiadsanalysis/1.0 by research_bot"

    # YouTube
    youtube_api_key: str = ""

    # Groq
    grok_api_key: str = ""
    grok_api_base: str = "https://api.groq.com/openai/v1"

    # Proxy (for Amazon/Walmart anti-bot)
    proxy_url: str = ""

    # YOLO
    yolo_model_path: str = "/models/best.pt"
    yolo_mode: str = "yolo"  # or "grounding_dino"

    # App
    output_dir: str = "output"
    temp_dir: str = "tmp"
    frontend_url: str = "*"
    max_items_per_run: int = 2000
    triage_percentile: float = 0.15
    request_delay: float = 1.5

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
