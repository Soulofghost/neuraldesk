from app.engine.chunker import chunk_text

def test_chunk_empty_text():
    chunks = chunk_text("")
    assert chunks == []

def test_chunk_short_text():
    text = "NeuralDesk is a semantic knowledge engine."
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) == 1
    assert chunks[0]["index"] == 0
    assert chunks[0]["content"] == text

def test_chunk_sliding_window_overlap():
    words = [f"word{i}" for i in range(100)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=30, overlap=10)
    assert len(chunks) > 1
    # Ensure chunks overlap
    first_chunk_words = chunks[0]["content"].split()
    second_chunk_words = chunks[1]["content"].split()
    assert first_chunk_words[-10:] == second_chunk_words[:10]
