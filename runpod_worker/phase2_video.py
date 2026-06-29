"""
Phase 2 — Video processing: download → extract frames → Whisper transcription.
Runs on RunPod GPU pod. Audio/frames deleted immediately after processing.
"""
import os
import subprocess
import tempfile
import json
import math
from pathlib import Path


_MAX_SIZE_MB = 80
_FRAME_INTERVAL = 2.5  # seconds between keyframes
_WHISPER_MODEL = "large-v3-turbo"


def process_videos(triaged_items: list[dict], temp_dir: str, whisper_model_path: str = None) -> list[dict]:
    """Download, transcribe, and extract frames for each triaged video item."""
    os.makedirs(temp_dir, exist_ok=True)
    results = []
    for item in triaged_items:
        if item.get("content_type") not in ("video", "ad"):
            continue
        video_url = item.get("video_url") or item.get("url") or ""
        if not video_url:
            continue
        try:
            result = _process_single(item, video_url, temp_dir, whisper_model_path)
            if result:
                results.append({**item, **result})
        except Exception as e:
            results.append({**item, "transcript_error": str(e)})
    return results


def _process_single(item: dict, url: str, temp_dir: str, whisper_model_path: str = None) -> dict | None:
    with tempfile.TemporaryDirectory(dir=temp_dir) as workdir:
        # Download video
        mp4_path = os.path.join(workdir, "video.mp4")
        success = _download_video(url, mp4_path)
        if not success:
            return None

        # Extract audio
        mp3_path = os.path.join(workdir, "audio.mp3")
        _extract_audio(mp4_path, mp3_path)

        # Transcribe
        transcript = ""
        if os.path.exists(mp3_path):
            lang = "es" if item.get("market") == "es" else "en"
            transcript = _whisper_transcribe(mp3_path, lang, whisper_model_path)

        # Extract keyframes
        frames_dir = os.path.join(workdir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        frame_paths = _extract_frames(mp4_path, frames_dir)

        duration = _get_duration(mp4_path)

        return {
            "transcript": transcript,
            "frame_paths": frame_paths,
            "duration": duration,
            "frame_count": len(frame_paths),
        }


def _download_video(url: str, output_path: str) -> bool:
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=360][filesize<?80M]+bestaudio/best[height<=360]",
        "--merge-output-format", "mp4",
        "--max-filesize", f"{_MAX_SIZE_MB}M",
        "-o", output_path,
        "--no-warnings",
        "--no-playlist",
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
        # Try direct download for CDN URLs (Minea, pipispy)
        if url.endswith((".mp4", ".mov", ".webm")):
            import requests
            r = requests.get(url, stream=True, timeout=30)
            if r.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                return os.path.getsize(output_path) > 1000
        return False
    except Exception:
        return False


def _extract_audio(mp4_path: str, mp3_path: str):
    cmd = [
        "ffmpeg", "-i", mp4_path,
        "-vn", "-ar", "16000", "-ac", "1", "-q:a", "2",
        mp3_path, "-y", "-loglevel", "quiet",
    ]
    try:
        subprocess.run(cmd, timeout=60, capture_output=True)
    except Exception:
        pass


def _whisper_transcribe(mp3_path: str, language: str, model_path: str = None) -> str:
    try:
        import whisper
        model_name = _WHISPER_MODEL
        if model_path and os.path.exists(model_path):
            model = whisper.load_model(model_path)
        else:
            model = whisper.load_model(model_name)
        result = model.transcribe(mp3_path, language=language, fp16=True, task="transcribe")
        return result.get("text", "").strip()
    except Exception as e:
        return f"[transcription error: {e}]"


def _extract_frames(mp4_path: str, frames_dir: str) -> list[str]:
    cmd = [
        "ffmpeg", "-i", mp4_path,
        "-vf", f"fps=1/{_FRAME_INTERVAL}",
        "-q:v", "2",
        os.path.join(frames_dir, "frame_%04d.jpg"),
        "-loglevel", "quiet",
    ]
    try:
        subprocess.run(cmd, timeout=60, capture_output=True)
        return sorted([
            os.path.join(frames_dir, f)
            for f in os.listdir(frames_dir)
            if f.endswith(".jpg")
        ])
    except Exception:
        return []


def _get_duration(mp4_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", mp4_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration") or 0)
    except Exception:
        return 0.0
