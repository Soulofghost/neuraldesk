import math
import re
from typing import List, Dict

class VectorEngine:
    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        tokens = [t for t in cleaned.split() if len(t) > 2]
        # Generate unigrams and character 3-grams for subword capture
        subwords = []
        for t in tokens:
            subwords.append(t)
            if len(t) >= 4:
                for i in range(len(t) - 2):
                    subwords.append(t[i:i+3])
        return subwords

    def embed(self, text: str) -> List[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimensions

        vector = [0.0] * self.dimensions
        token_freq: Dict[str, int] = {}
        for token in tokens:
            token_freq[token] = token_freq.get(token, 0) + 1

        for token, count in token_freq.items():
            # Murmur-like deterministic hash to bucket index
            h = abs(hash(token)) % self.dimensions
            tf = 1.0 + math.log(count)
            vector[h] += tf

        # L2 Normalization
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0.0:
            vector = [v / norm for v in vector]

        return vector

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        return max(0.0, min(1.0, float(dot_product)))

vector_engine = VectorEngine()
