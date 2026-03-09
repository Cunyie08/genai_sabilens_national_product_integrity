import os
import json

DATASET_FOLDER = "reference_dataset"
OUTPUT_FILE = "dataset_manifest.json"

def build_manifest():
    manifest = []

    for product in os.listdir(DATASET_FOLDER):
        product_path = os.path.join(DATASET_FOLDER, product)

        if not os.path.isdir(product_path):
            continue

        files = os.listdir(product_path)

        product_entry = {
            "product_id": product,
            "path": product_path,
            "views": {}
        }

        for file in files:
            if file.endswith(".jpg"):
                view_name = file.replace(".jpg", "")
                product_entry["views"][view_name] = os.path.join(product_path, file)

        manifest.append(product_entry)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    build_manifest()