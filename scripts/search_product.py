import json
import numpy as np
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

EMBEDDINGS_FILE = "embeddings.npy"
INDEX_FILE = "product_index.json"

device = "cuda" if torch.cuda.is_available() else "cpu"

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

embeddings = np.load(EMBEDDINGS_FILE)
with open(INDEX_FILE, "r") as f:
    index = json.load(f)

def search(image_path, top_k=3):
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)

    with torch.no_grad():
        query_features = model.get_image_features(**inputs)

    query_features = query_features.cpu().numpy()[0]
    query_features = query_features / np.linalg.norm(query_features)

    similarities = embeddings @ query_features
    top_indices = similarities.argsort()[-top_k:][::-1]

    print("\nTop Matches:\n")
    for i in top_indices:
        print(f"{index[i]}  | score: {similarities[i]:.4f}")

if __name__ == "__main__":
    search("test_image.jpg")