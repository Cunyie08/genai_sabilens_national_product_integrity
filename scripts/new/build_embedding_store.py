import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import json
from PIL import Image
from app.services.embedding_service import EmbeddingService

DATASET_DIR = "new_annotated_images"
OUTPUT_FILE = "app/reference_store/embeddings.json"

CLASS_NAMES = {
    0: "brand logo",
    1: "product logo",
    2: "NAFDAC number",
    3: "Barcodes",
    4: "Brand designs",
    5: "Brand colors",
    6: "Expiry date",
    7: "product name",
    8: "product variant",
}

embedder = EmbeddingService()


def load_yolo_labels(label_path, img_width, img_height):
    regions = []

    if not os.path.exists(label_path):
        return regions

    with open(label_path, "r") as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split()
        if len(parts) != 5:
            continue

        class_id = int(parts[0])
        x_center = float(parts[1]) * img_width
        y_center = float(parts[2]) * img_height
        width = float(parts[3]) * img_width
        height = float(parts[4]) * img_height

        x1 = max(0, int(x_center - width / 2))
        y1 = max(0, int(y_center - height / 2))
        x2 = min(img_width, int(x_center + width / 2))
        y2 = min(img_height, int(y_center + height / 2))

        regions.append({
            "class_id": class_id,
            "label": CLASS_NAMES.get(class_id, f"class_{class_id}"),
            "bbox": [x1, y1, x2, y2]
        })

    return regions


def build_store():
    store = {}

    for root, _, files in os.walk(DATASET_DIR):
        image_files = [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png"))]

        for image_file in image_files:
            image_path = os.path.join(root, image_file)
            label_path = os.path.splitext(image_path)[0] + ".txt"

            product_id = os.path.basename(os.path.dirname(image_path))
            view_name = os.path.splitext(image_file)[0]

            image = Image.open(image_path).convert("RGB")
            img_width, img_height = image.size

            full_embedding = embedder.generate_embedding(image)

            regions = load_yolo_labels(label_path, img_width, img_height)
            region_embeddings = []

            for region in regions:
                x1, y1, x2, y2 = region["bbox"]
                cropped = image.crop((x1, y1, x2, y2))
                embedding = embedder.generate_embedding(cropped)

                region_embeddings.append({
                    "label": region["label"],
                    "bbox": region["bbox"],
                    "embedding": embedding
                })

            if product_id not in store:
                store[product_id] = {"views": {}}

            store[product_id]["views"][view_name] = {
                "full_image_embedding": full_embedding,
                "regions": region_embeddings
            }

            print(f"Embedded: {product_id} / {view_name}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(store, f)

    print(f"\nSaved embedding store to {OUTPUT_FILE}")


if __name__ == "__main__":
    build_store()