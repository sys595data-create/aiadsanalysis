from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.db import get_db, Run
from backend.storage import r2

router = APIRouter()

_FILE_LABELS = {
    "01_raw_content.json": "Raw Content",
    "02_clusters.json": "NLP Clusters",
    "03_triaged.json": "Triaged Items",
    "04_recipes.json": "Creative Recipes",
    "05_statistics.json": "Statistics",
    "06_recipe_templates.md": "Recipe Templates",
    "07_run_report.md": "Run Report",
    "08_home_demo_hypothesis.json": "Home Demo Analysis",
    "09_customer_pain_analytics.json": "VOC Pain Analytics",
    "10_ad_analytics.json": "Ad Analytics",
    "11_market_intelligence.xlsx": "Market Intelligence (Excel)",
}


@router.get("/runs/{run_id}/files")
def list_files(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "done":
        return {"files": [], "message": f"Run status: {run.status}"}

    prefix = run.r2_prefix or f"runs/{run_id}"
    keys = r2.list_keys(prefix)

    files = []
    for key in sorted(keys):
        filename = key.split("/")[-1]
        label = _FILE_LABELS.get(filename, filename)
        url = r2.presigned_url(key, expires_in=86400)
        files.append({
            "filename": filename,
            "label": label,
            "key": key,
            "download_url": url,
        })
    return {"files": files}
