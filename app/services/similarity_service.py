import numpy as np


class SimilarityService:
    @staticmethod
    def cosine_similarity(vec1, vec2):
        a = np.array(vec1, dtype=np.float32)
        b = np.array(vec2, dtype=np.float32)

        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0

        return float(np.dot(a, b) / denom)