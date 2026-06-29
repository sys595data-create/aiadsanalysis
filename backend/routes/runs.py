import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.db import get_db, Run, RunLog
from backend.pipeline.orchestrator import launch_run

router = APIRouter()


class RunRequest(BaseModel):
    markets: list[str] = ["us"]
    sources: list[str] = ["youtube", "tiktok", "minea", "reddit", "amazon", "trustpilot", "walmart", "brand_sites", "meta_ads"]
    query_config: dict = {}
    min_views: int = 0
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    max_items: int = 2000


class RunResponse(BaseModel):
    id: str
    status: str
    markets: list
    sources: list
    item_count: int
    cluster_count: int
    video_count: int
    started_at: str
    completed_at: Optional[str]
    error_message: Optional[str]


def _to_response(run: Run) -> RunResponse:
    return RunResponse(
        id=run.id,
        status=run.status,
        markets=run.markets or [],
        sources=run.sources or [],
        item_count=run.item_count or 0,
        cluster_count=run.cluster_count or 0,
        video_count=run.video_count or 0,
        started_at=run.started_at.isoformat() if run.started_at else "",
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        error_message=run.error_message,
    )


@router.post("/runs", response_model=RunResponse)
def create_run(req: RunRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    run = Run(
        id=str(uuid.uuid4()),
        status="queued",
        markets=req.markets,
        sources=req.sources,
        query_config={
            **req.query_config,
            "min_views": req.min_views,
            "date_from": req.date_from,
            "date_to": req.date_to,
            "max_items": req.max_items,
        },
        r2_prefix=f"runs/{str(uuid.uuid4())}",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(launch_run, run.id)
    return _to_response(run)


@router.get("/runs", response_model=list[RunResponse])
def list_runs(db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.started_at.desc()).limit(50).all()
    return [_to_response(r) for r in runs]


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _to_response(run)


@router.get("/runs/{run_id}/status")
def get_status(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "status": run.status,
        "item_count": run.item_count,
        "cluster_count": run.cluster_count,
        "video_count": run.video_count,
        "error_message": run.error_message,
    }


@router.get("/runs/{run_id}/log")
def get_log(run_id: str, after_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(RunLog).filter(RunLog.run_id == run_id)
    if after_id:
        q = q.filter(RunLog.id > after_id)
    logs = q.order_by(RunLog.created_at).limit(200).all()
    return [{"id": l.id, "message": l.message, "level": l.level, "ts": l.created_at.isoformat()} for l in logs]
