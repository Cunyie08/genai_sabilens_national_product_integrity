"""
generate_embeddings.py  –  SabiLens Visual Module v2
=====================================================
WHAT CHANGED FROM v1 AND WHY
------------------------------
v1 stored all view embeddings as a flat list per product.
The SimilarityEngine then took max(similarities) across all views.

Problem: max() lets a fake "win" on ANY one view.  A fake that
looks like the back panel of another product gets a free pass.

v2 stores embeddings in a STRUCTURED dict per product:
  {
      "Product_Name": {
          "front":  [emb],           # always exactly 1 embedding
          "others": [emb, emb, ...]  # back, left, right, top, bottom
      }
  }

The SimilarityEngine v2 then weights front at 0.6 and others at 0.4.

BACKWARDS COMPATIBILITY:
  v2 .pkl files are NOT compatible with v1 SimilarityEngine.
  v1 SimilarityEngine IS forward-compatible: it will use embeddings[0]
  (front) and embeddings[1:] (others) via the isinstance(embeddings, list)
  branch in SimilarityEngine v2.  So the v2 SimilarityEngine can read
  BOTH v1 and v2 .pkl files.

USAGE:
    cd Visual/
    python vision_engine/embeddings/generate_embeddings.py

OUTPUT:
    vision_engine/embeddings/reference_embeddings.pkl  (v2 format)
"""

import os
import sys

# Ensure 'visual/' is on the path regardless of where the script is run from
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import pickle
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from vision_engine.models.feature_extractor import FeatureExtractor

DATASET_PATH = "reference_dataset"
OUTPUT_PATH  = "vision_engine/embeddings/reference_embeddings.pkl"
PRIMARY_VIEW = "front.jpg"

# Sanity check: a product's own front.jpg should score >= this against itself
SELF_SIM_WARN_THRESHOLD = 0.85


def main():
    extractor       = FeatureExtractor()
    embedding_store = {}
    missing_fronts  = []

    print(f"\nBuilding v2 embeddings from: {DATASET_PATH}\n")
    print("Format: {product: {front: [emb], others: [emb, ...]}}\n")

    for product in sorted(os.listdir(DATASET_PATH)):
        product_path = os.path.join(DATASET_PATH, product)
        if not os.path.isdir(product_path):
            continue

        images = sorted(os.listdir(product_path))
        embedding_store[product] = {"front": [], "others": []}

        # ── Front view (primary) ──────────────────────────────────────────
        front_path = os.path.join(product_path, PRIMARY_VIEW)
        if os.path.exists(front_path):
            emb = extractor.extract(front_path)   # already L2-normalised
            embedding_store[product]["front"].append(emb)
            print(f"  ✓ {product}  →  front extracted")
        else:
            missing_fronts.append(product)
            print(f"  ✗ {product}  →  no front.jpg, using all views as 'others'")

        # ── Other views (secondary) ───────────────────────────────────────
        for image_file in images:
            if image_file == PRIMARY_VIEW:
                continue
            if not image_file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            image_path = os.path.join(product_path, image_file)
            emb = extractor.extract(image_path)
            embedding_store[product]["others"].append(emb)

        front_count  = len(embedding_store[product]["front"])
        others_count = len(embedding_store[product]["others"])
        print(f"    front={front_count}  others={others_count}")

    # ── Save ──────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "wb") as f:
        pickle.dump(embedding_store, f)

    total_embs = sum(
        len(v["front"]) + len(v["others"])
        for v in embedding_store.values()
    )
    print(f"\nEmbeddings saved → {OUTPUT_PATH}")
    print(f"  Products : {len(embedding_store)}")
    print(f"  Embeddings: {total_embs}")

    if missing_fronts:
        print(f"\n⚠ Products missing front.jpg:")
        for p in missing_fronts:
            print(f"    {p}")
        print("  Add front.jpg to these folders for best matching accuracy.")

    # ── Self-similarity sanity check ──────────────────────────────────────
    print(f"\nSelf-similarity sanity check (should all be ≥ {SELF_SIM_WARN_THRESHOLD}):")
    low_scores = []

    for product in sorted(embedding_store.keys()):
        front_path = os.path.join(DATASET_PATH, product, PRIMARY_VIEW)
        if not os.path.exists(front_path):
            continue

        query      = extractor.extract(front_path)
        front_embs = embedding_store[product]["front"]
        if not front_embs:
            continue

        scores = [
            cosine_similarity(query.reshape(1, -1), emb.reshape(1, -1))[0][0]
            for emb in front_embs
        ]
        best   = max(scores)
        status = "OK " if best >= SELF_SIM_WARN_THRESHOLD else "⚠ LOW"
        print(f"  {status}  {product}: {best:.4f}")

        if best < SELF_SIM_WARN_THRESHOLD:
            low_scores.append((product, best))

    if low_scores:
        print(f"\nLow self-similarity products: {low_scores}")
        print("  Consider adding more/better reference images for these.")
    else:
        print("\nAll products pass self-similarity check ✓")


if __name__ == "__main__":
    main()
