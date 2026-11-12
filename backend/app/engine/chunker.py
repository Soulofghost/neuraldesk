from typing import List, Dict
import re

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[Dict[str, any]]:
    """
    Splits text into overlapping chunks while preserving sentence/word boundaries.
    """
    clean_text = re.sub(r'\s+', ' ', text).strip()
    if not clean_text:
        return []

    words = clean_text.split(' ')
    if len(words) <= chunk_size:
        return [{"index": 0, "content": clean_text}]

    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)
    chunk_idx = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_content = ' '.join(chunk_words)
        chunks.append({
            "index": chunk_idx,
            "content": chunk_content
        })
        chunk_idx += 1
        if end >= len(words):
            break
        start += step

    return chunks
