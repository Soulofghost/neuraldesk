from app.engine.embeddings import VectorEngine

def test_embedding_dimension_and_norm():
    engine = VectorEngine(dimensions=64)
    v = engine.embed("Artificial intelligence and machine learning pipelines")
    assert len(v) == 64
    # Check L2 normalization (sum of squares approx 1.0)
    norm = sum(x * x for x in v)
    assert abs(norm - 1.0) < 1e-4

def test_cosine_similarity_identical_and_orthogonal():
    engine = VectorEngine(dimensions=64)
    v1 = engine.embed("knowledge graph representation learning")
    v2 = engine.embed("knowledge graph representation learning")
    sim_identical = engine.cosine_similarity(v1, v2)
    assert abs(sim_identical - 1.0) < 1e-4

    v3 = engine.embed("completely unrelated cooking recipe for pizza baking")
    sim_diff = engine.cosine_similarity(v1, v3)
    assert sim_identical > sim_diff
