from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Title of the document")
    content: str = Field(..., min_length=1, max_length=1000000, description="Markdown or text content")
    category: Optional[str] = Field("General", max_length=50, description="Document category")
    tags: Optional[List[str]] = Field(default=[], description="List of keyword tags")

class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=1000000)
    category: Optional[str] = Field(None, max_length=50)
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

class DocumentDetailResponse(BaseModel):
    id: str
    title: str
    content: str
    category: str
    tags: List[str]
    created_at: str
    updated_at: str
    chunks: List[Dict[str, Any]]
    related: List[Dict[str, Any]]

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural language or keyword query")
    limit: Optional[int] = Field(6, ge=1, le=50, description="Maximum results to return")
    category: Optional[str] = Field(None, description="Optional category filter")

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

class SystemStats(BaseModel):
    total_documents: int
    total_chunks: int
    total_edges: int
    database_engine: str
    version: str
    status: str
