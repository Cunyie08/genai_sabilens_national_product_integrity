from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from ultralytics import YOLO

import io
import json
import uuid
import os

from PIL import Image
import numpy as np
import cv2

from app.services.embedding_service import EmbeddingService
from app.services.similarity_service import SimilarityService


# -----------------------------
# Config
# -----------------------------
MODEL_PATH = "runs/detect/train9/weights/best.pt"
REFERENCE_STORE_PATH = "app/reference_store/embeddings.json"
STATIC_PREDICTIONS_DIR = "static/predictions"
BASE_URL = "http://127.0.0.1:8000"

# Detection filtering
MIN_CONFIDENCE = 0.50

# Expected classes by side
FRONT_EXPECTED = {
    "brand logo",
    "product logo",
    "product name",
    "product variant",
    "Brand designs",
    "Brand colors",
}

BACK_EXPECTED = {
    "brand logo",
    "product logo",
    "product name",
    "Barcodes",
    "NAFDAC number",
    "Expiry date",
}


# -----------------------------
# Load YOLO detection model
# -----------------------------
model = YOLO(MODEL_PATH)


# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI()


# -----------------------------
# Static file serving
# -----------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")


# -----------------------------
# Load reference embedding store
# -----------------------------
with open(REFERENCE_STORE_PATH, "r") as f:
    reference_store = json.load(f)


# -----------------------------
# Initialize embedding services
# -----------------------------
embedder = EmbeddingService()
similarity_service = SimilarityService()


# -----------------------------
# Utility: verdict from score
# -----------------------------
def get_verdict(score: float) -> str:
    if score >= 0.95:
        return "very likely authentic"
    elif score >= 0.88:
        return "likely authentic"
    elif score >= 0.78:
        return "suspicious"
    else:
        return "likely counterfeit or different product"


# -----------------------------
# Utility: save annotated image
# -----------------------------
def save_annotated_image(image_np, prefix="prediction"):
    os.makedirs(STATIC_PREDICTIONS_DIR, exist_ok=True)

    filename = f"{prefix}_{uuid.uuid4()}.jpg"
    output_path = os.path.join(STATIC_PREDICTIONS_DIR, filename)

    cv2.imwrite(output_path, cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR))

    return f"{BASE_URL}/static/predictions/{filename}"


# -----------------------------
# Utility: summarize detection quality
# -----------------------------
def summarize_detection_quality(detections, side="single"):
    labels_found = {d["label"] for d in detections}
    avg_conf = round(sum(d["confidence"] for d in detections) / len(detections), 4) if detections else 0.0

    expected = set()
    if side == "front":
        expected = FRONT_EXPECTED
    elif side == "back":
        expected = BACK_EXPECTED

    expected_found = sorted(list(labels_found & expected)) if expected else []
    expected_missing = sorted(list(expected - labels_found)) if expected else []

    quality = "strong"
    if len(detections) == 0:
        quality = "very weak"
    elif avg_conf < 0.60:
        quality = "weak"
    elif avg_conf < 0.75:
        quality = "moderate"

    return {
        "side": side,
        "num_detections": len(detections),
        "average_confidence": avg_conf,
        "quality": quality,
        "expected_found": expected_found,
        "expected_missing": expected_missing
    }


# -----------------------------
# Utility: run YOLO on image
# -----------------------------
def run_detection_on_image(image: Image.Image):
    image_np = np.array(image).copy()

    results = model(image)
    result = results[0]
    boxes = result.boxes
    names = result.names

    detections = []

    if boxes is not None:
        for box in boxes:
            class_id = int(box.cls.item())
            label = names[class_id]
            confidence = float(box.conf.item())

            # Filter weak detections
            if confidence < MIN_CONFIDENCE:
                continue

            coords = box.xyxy[0].tolist()
            x1, y1, x2, y2 = map(int, coords)

            cv2.rectangle(
                image_np,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            cv2.putText(
                image_np,
                f"{label} {confidence:.2f}",
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )

            detections.append({
                "label": label,
                "confidence": round(confidence, 4),
                "coordinates": coords
            })

    return detections, image_np


# -----------------------------
# Utility: allowed views by side
# -----------------------------
def get_allowed_views(side="single"):
    if side == "front":
        return {"front", "front_st"}
    elif side == "back":
        return {"back", "back_st"}
    return None  # no restriction for single


# -----------------------------
# Compare one image to reference store
# -----------------------------
def compare_with_reference(image: Image.Image, side="single"):
    test_embedding = embedder.generate_embedding(image)

    best_product = None
    best_score = 0.0
    best_view = None

    allowed_views = get_allowed_views(side)

    for product_id, product_data in reference_store.items():
        views = product_data.get("views", {})

        for view_name, view_data in views.items():
            if allowed_views is not None and view_name not in allowed_views:
                continue

            ref_embedding = view_data.get("full_image_embedding")
            if ref_embedding is None:
                continue

            score = similarity_service.cosine_similarity(
                test_embedding,
                ref_embedding
            )

            if score > best_score:
                best_score = score
                best_product = product_id
                best_view = view_name

    return {
        "matched_product": best_product,
        "best_view": best_view,
        "similarity": round(best_score, 4),
        "verdict": get_verdict(best_score)
    }


# -----------------------------
# Safer multi-view comparison
# -----------------------------
def compare_multi_view(front_image: Image.Image, back_image: Image.Image,
                       front_detections, back_detections):
    front_result = compare_with_reference(front_image, side="front")
    back_result = compare_with_reference(back_image, side="back")

    front_score = front_result["similarity"]
    back_score = back_result["similarity"]

    # Base weighted combination:
    # back slightly stronger because barcode / NAFDAC / expiry usually live there
    base_score = (0.45 * front_score) + (0.55 * back_score)

    # Detection quality penalty
    front_summary = summarize_detection_quality(front_detections, side="front")
    back_summary = summarize_detection_quality(back_detections, side="back")

    penalty = 0.0

    if front_summary["quality"] == "very weak":
        penalty += 0.08
    elif front_summary["quality"] == "weak":
        penalty += 0.04

    if back_summary["quality"] == "very weak":
        penalty += 0.08
    elif back_summary["quality"] == "weak":
        penalty += 0.04

    final_score = round(max(base_score - penalty, 0.0), 4)

    # Decide final product
    if front_result["matched_product"] == back_result["matched_product"]:
        final_product = front_result["matched_product"]
        agreement = True
    else:
        agreement = False
        final_product = back_result["matched_product"] if back_score >= front_score else front_result["matched_product"]

    warnings = []
    if not agreement:
        warnings.append("front and back images matched different products")
    if front_summary["quality"] in {"very weak", "weak"}:
        warnings.append("front image evidence is weak")
    if back_summary["quality"] in {"very weak", "weak"}:
        warnings.append("back image evidence is weak")
    if len(front_summary["expected_missing"]) > 0:
        warnings.append("front image is missing some expected signals")
    if len(back_summary["expected_missing"]) > 0:
        warnings.append("back image is missing some expected signals")

    return {
        "matched_product": final_product,
        "front_match": front_result,
        "back_match": back_result,
        "front_detection_summary": front_summary,
        "back_detection_summary": back_summary,
        "combined_similarity": final_score,
        "verdict": get_verdict(final_score),
        "warnings": warnings
    }


# -----------------------------
# Single-image prediction endpoint
# -----------------------------
@app.post("/predict/")
async def predict(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    detections, annotated_image = run_detection_on_image(image)
    comparison_result = compare_with_reference(image, side="single")
    detection_summary = summarize_detection_quality(detections, side="single")
    image_url = save_annotated_image(annotated_image, prefix="single")

    return JSONResponse(content={
        "mode": "single",
        "detections": detections,
        "detection_summary": detection_summary,
        "product_match": comparison_result,
        "image_url": image_url
    })


# -----------------------------
# Multi-image prediction endpoint
# -----------------------------
@app.post("/predict-multi/")
async def predict_multi(
    front_file: UploadFile = File(...),
    back_file: UploadFile = File(...)
):
    front_bytes = await front_file.read()
    back_bytes = await back_file.read()

    front_image = Image.open(io.BytesIO(front_bytes)).convert("RGB")
    back_image = Image.open(io.BytesIO(back_bytes)).convert("RGB")

    front_detections, front_annotated = run_detection_on_image(front_image)
    back_detections, back_annotated = run_detection_on_image(back_image)

    comparison_result = compare_multi_view(
        front_image,
        back_image,
        front_detections,
        back_detections
    )

    front_image_url = save_annotated_image(front_annotated, prefix="front")
    back_image_url = save_annotated_image(back_annotated, prefix="back")

    return JSONResponse(content={
        "mode": "multi",
        "front_analysis": {
            "detections": front_detections,
            "summary": summarize_detection_quality(front_detections, side="front"),
            "image_url": front_image_url
        },
        "back_analysis": {
            "detections": back_detections,
            "summary": summarize_detection_quality(back_detections, side="back"),
            "image_url": back_image_url
        },
        "product_match": comparison_result
    })