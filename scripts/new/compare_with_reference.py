import sys
import os
import json
from collections import defaultdict
from PIL import Image

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.services.embedding_service import EmbeddingService
from app.services.similarity_service import SimilarityService


REFERENCE_STORE = "app/reference_store/embeddings.json"
TEST_IMAGE_PATH = "reference_dataset/Dangote_sugar_refined_granulated_white_sugar_500g/front_st.jpg"  # change this to your test image path


embedder = EmbeddingService()
similarity_service = SimilarityService()


def load_reference_store():
    if not os.path.exists(REFERENCE_STORE):
        raise FileNotFoundError(f"Reference store not found: {REFERENCE_STORE}")

    with open(REFERENCE_STORE, "r") as f:
        return json.load(f)


def generate_test_embedding(image_path):
    image = Image.open(image_path).convert("RGB")
    return embedder.generate_embedding(image)


def compare_full_image_only(test_embedding, reference_store):
    results = []

    for product_id, product_data in reference_store.items():
        views = product_data.get("views", {})
        view_scores = []

        for view_name, view_data in views.items():
            ref_embedding = view_data.get("full_image_embedding")
            if not ref_embedding:
                continue

            score = similarity_service.cosine_similarity(test_embedding, ref_embedding)
            view_scores.append({
                "view": view_name,
                "similarity": score
            })

        if view_scores:
            best_view = max(view_scores, key=lambda x: x["similarity"])
            avg_score = sum(v["similarity"] for v in view_scores) / len(view_scores)

            results.append({
                "product_id": product_id,
                "best_view": best_view["view"],
                "best_similarity": round(best_view["similarity"], 4),
                "average_similarity": round(avg_score, 4),
                "all_view_scores": view_scores
            })

    results.sort(key=lambda x: x["best_similarity"], reverse=True)
    return results


def verdict_from_score(score: float) -> str:
    if score >= 0.95:
        return "very likely authentic"
    elif score >= 0.88:
        return "likely authentic"
    elif score >= 0.78:
        return "suspicious"
    else:
        return "likely different product or counterfeit"


def main():
    if not os.path.exists(TEST_IMAGE_PATH):
        raise FileNotFoundError(f"Test image not found: {TEST_IMAGE_PATH}")

    reference_store = load_reference_store()
    test_embedding = generate_test_embedding(TEST_IMAGE_PATH)
    ranked_results = compare_full_image_only(test_embedding, reference_store)

    if not ranked_results:
        print("No reference embeddings found to compare.")
        return

    best_match = ranked_results[0]
    verdict = verdict_from_score(best_match["best_similarity"])

    output = {
        "test_image": TEST_IMAGE_PATH,
        "matched_product": best_match["product_id"],
        "best_view": best_match["best_view"],
        "best_similarity": best_match["best_similarity"],
        "average_similarity": best_match["average_similarity"],
        "verdict": verdict,
        "top_matches": ranked_results[:5]
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()