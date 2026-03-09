import json
import torch
import numpy as np
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

MANIFEST_FILE = "dataset_manifest.json"
EMBEDDINGS_FILE = "embeddings.npy"
INDEX_FILE = "product_index.json"

device = "cuda" if torch.cuda.is_available() else "cpu"

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

def generate():
    with open(MANIFEST_FILE, "r") as f:
        manifest = json.load(f)

    embeddings = []
    index = []

    for product in manifest:
        front_path = product["views"].get("front")

        if not front_path:
            continue

        image = Image.open(front_path).convert("RGB")

        # Preprocess the image for CLIP model
        inputs = processor(images=image, return_tensors="pt").to(device)

        with torch.no_grad():
            # Get the image features from the model
            outputs = model.get_image_features(**inputs)
            image_features = outputs.pooler_output  # Use pooler_output for the final features

        # Normalize the image features
        image_features = image_features.cpu().numpy()[0]
        image_features = image_features / np.linalg.norm(image_features)

        embeddings.append(image_features)
        index.append(product["product_id"])

        print(f"Embedded: {product['product_id']}")

    embeddings = np.array(embeddings)

    # Save embeddings and product index to files
    np.save(EMBEDDINGS_FILE, embeddings)

    with open(INDEX_FILE, "w") as f:
        json.dump(index, f)

    print("Embeddings saved.")

if __name__ == "__main__":
    generate()