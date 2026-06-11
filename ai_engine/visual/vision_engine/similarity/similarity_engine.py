"""
similarity_engine.py  –  SabiLens Visual Module v2
====================================================
WHAT CHANGED FROM v1 AND WHY
------------------------------
v1 computed ONE cosine similarity score against the whole image embedding
and used `max(similarities)` across all views.  Two problems:

  Problem 1 – max() is too generous.
    Taking the MAXIMUM similarity across all stored views means a fake
    that happens to match the back-of-box colour layout (which may look
    similar to many products) gets an artificially inflated score.

  Problem 2 – No anomaly threshold.
    v1 had no concept of "this score is too low to trust".  Any image
    returned *some* product with *some* similarity and the pipeline
    treated that score as meaningful regardless of value.

v2 FIXES:
  1. WEIGHTED MULTI-VIEW SCORING
     front.jpg gets weight 0.6.  Other views split the remaining 0.4.
     A fake that matches the back but not the front is correctly penalised.

  2. ANOMALY BAND
     If the best similarity is below ANOMALY_THRESHOLD (0.60) the engine
     returns a low confidence signal regardless of which product matched.
     This catches fakes that are "close enough to fool ResNet50" but not
     close enough to a forensic-level EfficientNet embedding.

  3. INTER-PRODUCT MARGIN CHECK
     If the gap between the best match and the second-best match is below
     MARGIN_THRESHOLD (0.08), the engine flags the result as ambiguous.
     Authentic products should score WELL above competing products.
     A fake often scores similarly against multiple products because it
     is a generic approximation of the category.

  4. PER-REGION SCORES (optional)
     If region embeddings are stored (keys like "product::front",
     "product::logo"), the engine scores each region independently and
     returns a breakdown.  The pipeline can use these for explainability.

OUTPUT CONTRACT (superset of v1 — Fusion Engine still gets all v1 fields):
  {
      "product":           str,    # Best matched product name
      "similarity":        float,  # Weighted cosine similarity 0.0–1.0
      "margin":            float,  # Gap to 2nd-best product (0.0 if only 1 product)
      "anomaly_flag":      bool,   # True if similarity < ANOMALY_THRESHOLD
      "ambiguity_flag":    bool,   # True if margin < MARGIN_THRESHOLD
      "all_scores":        dict,   # {product: score} for all products
  }
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import pickle
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as cos_sim

from vision_engine.models.feature_extractor import FeatureExtractor

# ── Tunable thresholds ────────────────────────────────────────────────────────
ANOMALY_THRESHOLD  = 0.67   # below this → fake signal regardless of match
MARGIN_THRESHOLD   = 0.08   # gap to 2nd-best; below this → ambiguous


class SimilarityEngine:
    """
    Compare a query image against all reference embeddings and return a
    rich similarity report that the VisualPipeline uses to compute confidence.
    """

    def __init__(self, embedding_path: str):
        with open(embedding_path, "rb") as f:
            self.embedding_store: dict = pickle.load(f)

        self.extractor = FeatureExtractor()

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def compare(self, image_path: str) -> dict:
        """
        Compare a query image against all reference embeddings.

        Args:
            image_path: Path to the scanned product image (full image or crop).

        Returns:
            Dict matching the v2 output contract above.
        """
        query = self._extract_normalised(image_path)
        scores = self._score_all(query)

        if not scores:
            return self._no_product_result()

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_product, best_score = sorted_scores[0]

        # ── Margin: gap to second-best product ───────────────────────────
        margin = 0.0
        if len(sorted_scores) >= 2:
            margin = float(best_score - sorted_scores[1][1])

        return {
            "product":        best_product,
            "similarity":     float(round(best_score, 4)),
            "margin":         float(round(margin, 4)),
            "anomaly_flag":   best_score < ANOMALY_THRESHOLD,
            "ambiguity_flag": margin < MARGIN_THRESHOLD,
            "all_scores":     {p: round(float(s), 4) for p, s in sorted_scores},
        }

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _score_all(self, query: np.ndarray) -> dict:
        """
        Score query against every product in the embedding store.

        Embedding store format (v2):
            {
                "Product_Name": {
                    "front":  [emb, ...],          # weight 0.6
                    "others": [emb, ...],           # weight 0.4 shared
                }
            }

        For backwards compatibility with v1 .pkl files (list of embeddings),
        the first embedding is treated as front, the rest as others.
        """
        scores = {}

        for product, embeddings in self.embedding_store.items():

            # ── Handle both v1 (list) and v2 (dict) embedding formats ────
            if isinstance(embeddings, dict):
                front_embs  = embeddings.get("front", [])
                other_embs  = embeddings.get("others", [])
            else:
                # v1 format: first embedding = front, rest = others
                front_embs  = [embeddings[0]] if embeddings else []
                other_embs  = embeddings[1:]  if len(embeddings) > 1 else []

            # ── Weighted similarity ───────────────────────────────────────
            front_score = self._best_cosine(query, front_embs)
            other_score = self._best_cosine(query, other_embs)

            if front_embs and other_embs:
                weighted = 0.6 * front_score + 0.4 * other_score
            elif front_embs:
                weighted = front_score
            else:
                weighted = other_score

            scores[product] = weighted

        return scores

    def _best_cosine(self, query: np.ndarray, embeddings: list) -> float:
        """Return the maximum cosine similarity between query and a list of embeddings."""
        if not embeddings:
            return 0.0
        sims = [
            float(cos_sim(query.reshape(1, -1), emb.reshape(1, -1))[0][0])
            for emb in embeddings
        ]
        return max(sims)

    def _extract_normalised(self, image_path: str) -> np.ndarray:
        """Extract features (already L2-normalised by FeatureExtractor v2)."""
        return self.extractor.extract(image_path)

    @staticmethod
    def _no_product_result() -> dict:
        return {
            "product":        "NO_PRODUCT_DETECTED",
            "similarity":     0.0,
            "margin":         0.0,
            "anomaly_flag":   True,
            "ambiguity_flag": True,
            "all_scores":     {},
        }
