import time
import requests
from backend.config import settings

_BASE = "https://api.runpod.io/v2"


def _headers():
    return {"Authorization": f"Bearer {settings.runpod_api_key}"}


def submit_job(payload: dict) -> str:
    url = f"{_BASE}/{settings.runpod_endpoint_id}/run"
    resp = requests.post(url, json={"input": payload}, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()["id"]


def get_job_status(job_id: str) -> dict:
    url = f"{_BASE}/{settings.runpod_endpoint_id}/status/{job_id}"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def cancel_job(job_id: str):
    url = f"{_BASE}/{settings.runpod_endpoint_id}/cancel/{job_id}"
    requests.post(url, headers=_headers(), timeout=30)


def wait_for_job(job_id: str, poll_interval: int = 30, timeout: int = 21600) -> dict:
    """Poll until job completes or times out (default 6h)."""
    start = time.time()
    while time.time() - start < timeout:
        status = get_job_status(job_id)
        state = status.get("status", "")
        if state in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
            return status
        time.sleep(poll_interval)
    raise TimeoutError(f"RunPod job {job_id} did not complete within {timeout}s")
