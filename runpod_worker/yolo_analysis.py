"""
YOLO visual analysis — YOLOv11s per-frame object detection.
Falls back to Grounding DINO (zero-shot, no training required) if YOLO_MODE=grounding_dino.
"""
import os
from collections import Counter


# Mapping from COCO class names to wellness concepts
_COCO_TO_CONCEPT = {
    "person": "person_present",
    "bed": "bed_present",
    "couch": "home_setting",
    "chair": "home_setting",
    "tv": "home_setting",
    "laptop": "tech_device",
    "cell phone": "tech_device",
    "bottle": "product_prop",
    "sports ball": "fitness_context",
    "keyboard": "tech_device",
}

# Custom wellness class names (from fine-tuned model)
_WELLNESS_CLASSES = [
    "eye_massager", "circulation_booster", "pemf_mat", "infrared_mat",
    "jade_mat", "neck_massager", "heating_pad", "massage_device",
    "red_light_panel", "sauna_blanket",
]

# Grounding DINO text prompts
_DINO_PROMPTS = (
    "eye massager . eye mask device . "
    "PEMF mat . infrared mat . jade massage mat . "
    "circulation booster . EMS foot device . "
    "red light panel . sauna blanket . neck massager . "
    "heating pad . massage device . person . home room . studio"
)


def analyse_frames(frame_paths: list[str], model_path: str = "/models/best.pt", mode: str = "yolo") -> dict:
    if not frame_paths:
        return _empty_result()
    if mode == "grounding_dino":
        return _analyse_grounding_dino(frame_paths)
    return _analyse_yolo(frame_paths, model_path)


def _analyse_yolo(frame_paths: list[str], model_path: str) -> dict:
    try:
        from ultralytics import YOLO
        # Use custom model if available, else fall back to pretrained yolo11s
        if os.path.exists(model_path):
            model = YOLO(model_path)
        else:
            model = YOLO("yolo11s.pt")

        all_detections = []
        concept_timeline = []

        for i, frame_path in enumerate(frame_paths):
            if not os.path.exists(frame_path):
                continue
            results = model(frame_path, verbose=False, conf=0.35)
            frame_concepts = []
            for result in results:
                for box in result.boxes:
                    cls_name = result.names[int(box.cls)]
                    conf = float(box.conf)
                    # Map to wellness concept
                    concept = _COCO_TO_CONCEPT.get(cls_name, cls_name if cls_name in _WELLNESS_CLASSES else None)
                    if concept:
                        frame_concepts.append(concept)
                        all_detections.append(concept)
            concept_timeline.append({
                "frame": i,
                "time_s": round(i * 2.5, 1),
                "concepts": list(set(frame_concepts)),
            })

        concept_counts = Counter(all_detections)
        top_concepts = [k for k, _ in concept_counts.most_common(8)]
        setting = _infer_setting(top_concepts)

        return {
            "visual_concepts": top_concepts,
            "concept_counts": dict(concept_counts),
            "concept_timeline": concept_timeline,
            "video_structure": {
                "setting": setting,
                "person_present": "person_present" in top_concepts,
                "product_detected": any(c in _WELLNESS_CLASSES for c in top_concepts),
            },
        }
    except Exception as e:
        return {**_empty_result(), "error": str(e)}


def _analyse_grounding_dino(frame_paths: list[str]) -> dict:
    try:
        from groundingdino.util.inference import load_model, load_image, predict
        import torch
        model = load_model(
            "groundingdino/config/GroundingDINO_SwinT_OGC.py",
            "weights/groundingdino_swint_ogc.pth",
        )
        all_detections = []
        for frame_path in frame_paths[:20]:  # limit for speed
            image_source, image = load_image(frame_path)
            boxes, logits, phrases = predict(
                model=model, image=image,
                caption=_DINO_PROMPTS,
                box_threshold=0.3, text_threshold=0.25,
            )
            all_detections.extend(phrases)
        counts = Counter(all_detections)
        top = [k for k, _ in counts.most_common(8)]
        return {
            "visual_concepts": top,
            "concept_counts": dict(counts),
            "concept_timeline": [],
            "video_structure": {
                "setting": _infer_setting(top),
                "person_present": any("person" in c for c in top),
                "product_detected": True,
            },
        }
    except Exception as e:
        return {**_empty_result(), "error": str(e)}


def _infer_setting(concepts: list[str]) -> str:
    if "home_setting" in concepts or "bed_present" in concepts:
        return "home"
    if "studio" in " ".join(concepts):
        return "studio"
    return "unknown"


def _empty_result() -> dict:
    return {
        "visual_concepts": [],
        "concept_counts": {},
        "concept_timeline": [],
        "video_structure": {"setting": "unknown", "person_present": False, "product_detected": False},
    }
