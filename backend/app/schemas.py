from pydantic import BaseModel, Field
from typing import List, Optional

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: Optional[str] = "General"
    tags: Optional[List[str]] = []

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    category: str
    tags: List[str]
    created_at: str
    updated_at: str
    chunk_count: Optional[int] = 0

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    limit: Optional[int] = 5
    category: Optional[str] = None

class SearchResultItem(BaseModel):
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    score: float
    category: str

class GraphNode(BaseModel):
    id: str
    label: str
    category: str
    size: int

class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float
    relation: str

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
