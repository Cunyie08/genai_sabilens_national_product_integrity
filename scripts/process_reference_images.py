# import os
# import json
# import torch
# import numpy as np
# import cv2
# from PIL import Image
# from transformers import CLIPProcessor, CLIPModel
# from ultralytics import YOLO

# # ----------------------------
# # Paths
# # ----------------------------
# REFERENCE_FOLDER = "reference_dataset"
# OUTPUT_FILE = "dataset_manifest.json"
# INDEX_FILE = "product_index.json"

# # ----------------------------
# # Device Setup
# # ----------------------------
# if torch.backends.mps.is_available():
#     device = "mps"  # Apple Silicon GPU
# elif torch.cuda.is_available():
#     device = "cuda"
# else:
#     device = "cpu"

# print(f"Using device: {device}")

# # ----------------------------
# # Load CLIP
# # ----------------------------
# model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
# processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# # ----------------------------
# # Load YOLOv8
# # ----------------------------
# yolo_model = YOLO("yolov8n.pt")  # lightweight + stable

# # ----------------------------
# # Embedding Function
# # ----------------------------
# def extract_embedding(image: Image.Image):
#     inputs = processor(images=image, return_tensors="pt").to(device)

#     with torch.no_grad():
#         features = model.get_image_features(**inputs)

#     vec = features.cpu().numpy()[0]
#     vec = vec / np.linalg.norm(vec)  # normalize
#     return vec


# # ----------------------------
# # YOLO Detection
# # ----------------------------
# def detect_regions_with_yolo(image_path):
#     img = cv2.imread(image_path)
#     results = yolo_model(img)

#     detected_regions = []

#     for r in results:
#         if r.boxes is None:
#             continue

#         boxes = r.boxes.xyxy.cpu().numpy()
#         classes = r.boxes.cls.cpu().numpy()

#         for box, cls in zip(boxes, classes):
#             x1, y1, x2, y2 = box
#             cropped_region = img[int(y1):int(y2), int(x1):int(x2)]

#             if cropped_region.size == 0:
#                 continue

#             label = int(cls)
#             detected_regions.append((cropped_region, label))

#     return detected_regions


# # ----------------------------
# # Main Processing
# # ----------------------------
# def process_reference_dataset():

#     dataset_manifest = []
#     product_index = []

#     for product in os.listdir(REFERENCE_FOLDER):
#         product_path = os.path.join(REFERENCE_FOLDER, product)

#         if not os.path.isdir(product_path):
#             continue

#         print(f"\nProcessing: {product}")

#         product_entry = {
#             "product_id": product,
#             "views": {}
#         }

#         view_embeddings = []

#         for file in os.listdir(product_path):
#             if not file.endswith(".jpg"):
#                 continue

#             view_name = file.replace(".jpg", "")
#             image_path = os.path.join(product_path, file)

#             # ---- Full Image Embedding ----
#             full_image = Image.open(image_path).convert("RGB")
#             full_embedding = extract_embedding(full_image)

#             product_entry["views"][view_name] = {
#                 "full_image_embedding": full_embedding.tolist()
#             }

#             view_embeddings.append(full_embedding)

#             # ---- YOLO Region Detection ----
#             detected_regions = detect_regions_with_yolo(image_path)

#             for idx, (cropped_region, label) in enumerate(detected_regions):
#                 cropped_pil = Image.fromarray(cv2.cvtColor(cropped_region, cv2.COLOR_BGR2RGB))
#                 cropped_embedding = extract_embedding(cropped_pil)

#                 region_key = f"{view_name}_region_{idx}"

#                 product_entry["views"][region_key] = {
#                     "cropped_image_embedding": cropped_embedding.tolist()
#                 }

#         # ---- Multi-view Average Embedding ----
#         if view_embeddings:
#             avg_embedding = np.mean(view_embeddings, axis=0)
#             avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

#             product_entry["average_embedding"] = avg_embedding.tolist()

#         dataset_manifest.append(product_entry)
#         product_index.append(product)

#     # ---- Save Files ----
#     with open(OUTPUT_FILE, "w") as f:
#         json.dump(dataset_manifest, f, indent=2)

#     with open(INDEX_FILE, "w") as f:
#         json.dump(product_index, f, indent=2)

#     print("\n Dataset manifest and product index saved.")


# if __name__ == "__main__":
#     process_reference_dataset()

import os
import json
import torch
import numpy as np
import cv2
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from ultralytics import YOLO
import pytesseract
from pyzbar.pyzbar import decode

# ----------------------------
# Paths
# ----------------------------
REFERENCE_FOLDER = "reference_dataset"
OUTPUT_FILE = "dataset_manifest.json"
INDEX_FILE = "product_index.json"

# ----------------------------
# Device Setup
# ----------------------------
if torch.backends.mps.is_available():
    device = "mps"  # Apple Silicon GPU
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"

print(f"Using device: {device}")

# ----------------------------
# Load CLIP
# ----------------------------
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# ----------------------------
# Load YOLOv8
# ----------------------------
yolo_model = YOLO("yolov8n.pt")  # lightweight + stable

# ----------------------------
# Embedding Function
# ----------------------------
def extract_embedding(image: Image.Image):
    inputs = processor(images=image, return_tensors="pt").to(device)

    with torch.no_grad():
        features = model.get_image_features(**inputs)

    vec = features.cpu().numpy()[0]
    vec = vec / np.linalg.norm(vec)  # normalize
    return vec

# ----------------------------
# Barcode Detection using Pyzbar
# ----------------------------
def detect_barcode(cropped_region):
    barcodes = decode(cropped_region)
    barcode_data = []
    for barcode in barcodes:
        barcode_data.append(barcode.data.decode("utf-8"))
    return barcode_data

# ----------------------------
# OCR (NAFDAC Text Recognition)
# ----------------------------
def extract_text_from_image(cropped_region):
    text = pytesseract.image_to_string(cropped_region, config='--psm 6')
    return text.strip()

# ----------------------------
# YOLO Detection
# ----------------------------
def detect_regions_with_yolo(image_path):
    img = cv2.imread(image_path)
    results = yolo_model(img)

    detected_regions = []

    for r in results:
        if r.boxes is None:
            continue

        boxes = r.boxes.xyxy.cpu().numpy()
        classes = r.boxes.cls.cpu().numpy()

        for box, cls in zip(boxes, classes):
            x1, y1, x2, y2 = box
            cropped_region = img[int(y1):int(y2), int(x1):int(x2)]

            if cropped_region.size == 0:
                continue

            label = int(cls)
            detected_regions.append((cropped_region, label))

    return detected_regions

# ----------------------------
# Main Processing
# ----------------------------
def process_reference_dataset():

    dataset_manifest = []
    product_index = []

    for product in os.listdir(REFERENCE_FOLDER):
        product_path = os.path.join(REFERENCE_FOLDER, product)

        if not os.path.isdir(product_path):
            continue

        print(f"\nProcessing: {product}")

        product_entry = {
            "product_id": product,
            "views": {}
        }

        view_embeddings = []

        for file in os.listdir(product_path):
            if not file.endswith(".jpg"):
                continue

            view_name = file.replace(".jpg", "")
            image_path = os.path.join(product_path, file)

            # ---- Full Image Embedding ----
            full_image = Image.open(image_path).convert("RGB")
            full_embedding = extract_embedding(full_image)

            product_entry["views"][view_name] = {
                "full_image_embedding": full_embedding.tolist()
            }

            view_embeddings.append(full_embedding)

            # ---- YOLO Region Detection ----
            detected_regions = detect_regions_with_yolo(image_path)

            for idx, (cropped_region, label) in enumerate(detected_regions):
                cropped_pil = Image.fromarray(cv2.cvtColor(cropped_region, cv2.COLOR_BGR2RGB))
                cropped_embedding = extract_embedding(cropped_pil)

                region_key = f"{view_name}_region_{idx}"

                # Add Embedding for Cropped Region
                product_entry["views"][region_key] = {
                    "cropped_image_embedding": cropped_embedding.tolist()
                }

                # Check for Barcode in Detected Region
                barcode_data = detect_barcode(cropped_region)
                if barcode_data:
                    product_entry["views"][region_key]["barcodes"] = barcode_data

                # Check for NAFDAC or Other Text in Detected Region
                text_data = extract_text_from_image(cropped_region)
                if text_data:
                    product_entry["views"][region_key]["text"] = text_data

        # ---- Multi-view Average Embedding ----
        if view_embeddings:
            avg_embedding = np.mean(view_embeddings, axis=0)
            avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

            product_entry["average_embedding"] = avg_embedding.tolist()

        dataset_manifest.append(product_entry)
        product_index.append(product)

    # ---- Save Files ----
    with open(OUTPUT_FILE, "w") as f:
        json.dump(dataset_manifest, f, indent=2)

    with open(INDEX_FILE, "w") as f:
        json.dump(product_index, f, indent=2)

    print("\n Dataset manifest and product index saved.")


if __name__ == "__main__":
    process_reference_dataset()