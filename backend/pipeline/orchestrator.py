import json
from datetime import datetime
from sqlalchemy.orm import Session
from backend.db import SessionLocal, Run, RunLog
from backend.pipeline import runpod_client
from backend.config import settings


def _log(db: Session, run_id: str, message: str, level: str = "info"):
    entry = RunLog(run_id=run_id, message=message, level=level)
    db.add(entry)
    db.commit()
    print(f"[{run_id[:8]}] [{level.upper()}] {message}")


def _set_status(db: Session, run: Run, status: str, **kwargs):
    run.status = status
    for k, v in kwargs.items():
        setattr(run, k, v)
    db.commit()


def launch_run(run_id: str):
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return

        _set_status(db, run, "queued")
        _log(db, run_id, "Run queued — submitting to RunPod")

        payload = {
            "run_id": run_id,
            "markets": run.markets,
            "sources": run.sources,
            "query_config": run.query_config,
            "r2_prefix": run.r2_prefix,
            "db_url": settings.database_url,
            "r2_account_id": settings.r2_account_id,
            "r2_access_key_id": settings.r2_access_key_id,
            "r2_secret_access_key": settings.r2_secret_access_key,
            "r2_bucket_name": settings.r2_bucket_name,
            "pipispy_api_key": settings.pipispy_api_key,
            "pipispy_base_url": settings.pipispy_base_url,
            "minea_email": settings.minea_email,
            "minea_password": settings.minea_password,
            "reddit_client_id": settings.reddit_client_id,
            "reddit_client_secret": settings.reddit_client_secret,
            "reddit_user_agent": settings.reddit_user_agent,
            "youtube_api_key": settings.youtube_api_key,
            "grok_api_key": settings.grok_api_key,
            "grok_api_base": settings.grok_api_base,
            "proxy_url": settings.proxy_url,
            "yolo_model_path": settings.yolo_model_path,
            "yolo_mode": settings.yolo_mode,
            "max_items_per_run": run.query_config.get("max_items", settings.max_items_per_run),
        }

        if not settings.runpod_api_key or not settings.runpod_endpoint_id:
            _log(db, run_id, "RunPod not configured — stub mode", "warning")
            _set_status(db, run, "error", error_message="RunPod API key or endpoint ID not set")
            return

        job_id = runpod_client.submit_job(payload)
        _set_status(db, run, "ingesting", runpod_job_id=job_id)
        _log(db, run_id, f"RunPod job submitted: {job_id} — waiting for completion")

        result = runpod_client.wait_for_job(job_id)
        state = result.get("status", "FAILED")

        if state == "COMPLETED":
            output = result.get("output", {})
            _set_status(
                db, run, "done",
                completed_at=datetime.utcnow(),
                item_count=output.get("item_count", 0),
                cluster_count=output.get("cluster_count", 0),
                video_count=output.get("video_count", 0),
            )
            _log(db, run_id, f"Run completed — {output.get('item_count', 0)} items, {output.get('cluster_count', 0)} clusters")
        else:
            error = result.get("error", state)
            _set_status(db, run, "error", error_message=error, completed_at=datetime.utcnow())
            _log(db, run_id, f"Run failed: {error}", "error")

    except Exception as e:
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                _set_status(db, run, "error", error_message=str(e), completed_at=datetime.utcnow())
            _log(db, run_id, f"Orchestrator exception: {e}", "error")
        except Exception:
            pass
    finally:
        db.close()
