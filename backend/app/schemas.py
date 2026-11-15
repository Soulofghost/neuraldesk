from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any

# ================= AUTH SCHEMAS =================
class UserRegister(BaseModel):
    email: str = Field(..., min_length=4, max_length=120)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    plan: str
    avatar_url: Optional[str] = ""
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

# ================= WORKSPACE SCHEMAS =================
class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = ""

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str
    is_default: int
    created_at: str
    document_count: Optional[int] = 0

# ================= DOCUMENT SCHEMAS =================
class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=2000000)
    category: Optional[str] = "General"
    tags: Optional[List[str]] = []
    workspace_id: Optional[str] = "default"
    file_type: Optional[str] = "text"

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[int] = None
    is_archived: Optional[int] = None
    is_trash: Optional[int] = None
    folder: Optional[str] = None

class DocumentResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    content: str
    category: str
    tags: List[str]
    file_type: str
    file_size: int
    is_favorite: int
    is_archived: int
    is_trash: int
    created_at: str
    updated_at: str
    chunk_count: Optional[int] = 0

class DocumentDetailResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    content: str
    category: str
    tags: List[str]
    file_type: str
    file_size: int
    is_favorite: int
    is_archived: int
    is_trash: int
    created_at: str
    updated_at: str
    chunks: List[Dict[str, Any]]
    related: List[Dict[str, Any]]

# ================= AI INTELLIGENCE & CHAT =================
class SummarizeRequest(BaseModel):
    document_id: Optional[str] = None
    content: Optional[str] = None
    max_sentences: Optional[int] = 4

class SummarizeResponse(BaseModel):
    summary: str
    sentence_count: int
    key_takeaways: List[str]

class QuestionAnsweringRequest(BaseModel):
    question: str = Field(..., min_length=2)
    document_id: Optional[str] = None
    workspace_id: Optional[str] = "default"

class QuestionAnsweringResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Research Chat"
    workspace_id: Optional[str] = "default"

class ConversationResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: Optional[int] = 0

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    document_id: Optional[str] = None

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: List[Dict[str, Any]]
    created_at: str

# ================= SEARCH & GRAPH =================
class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: Optional[int] = Field(10, ge=1, le=50)
    category: Optional[str] = None
    workspace_id: Optional[str] = None
    file_type: Optional[str] = None

class SearchResultItem(BaseModel):
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    score: float
    category: str
    file_type: Optional[str] = "text"

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

# ================= PRODUCTIVITY (NOTES & TASKS) =================
class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    tags: Optional[List[str]] = []
    workspace_id: Optional[str] = "default"
    linked_document_id: Optional[str] = None

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[int] = None
    is_favorite: Optional[int] = None

class NoteResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    content: str
    tags: List[str]
    is_pinned: int
    is_favorite: int
    linked_document_id: Optional[str] = None
    created_at: str
    updated_at: str

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=250)
    description: Optional[str] = ""
    status: Optional[str] = "todo"
    priority: Optional[str] = "medium"
    due_date: Optional[str] = None
    workspace_id: Optional[str] = "default"
    linked_document_id: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None

class TaskResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    description: str
    status: str
    priority: str
    due_date: Optional[str] = None
    linked_document_id: Optional[str] = None
    created_at: str
    updated_at: str

# ================= COLLABORATION & NOTIFICATIONS =================
class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class CommentResponse(BaseModel):
    id: str
    document_id: str
    author_name: str
    content: str
    created_at: str

class ShareLinkResponse(BaseModel):
    id: str
    document_id: str
    token: str
    share_url: str
    permission: str
    created_at: str

class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    type: str
    is_read: int
    created_at: str

# ================= ANALYTICS & TELEMETRY =================
class AnalyticsResponse(BaseModel):
    total_documents: int
    total_workspaces: int
    total_chunks: int
    total_notes: int
    total_tasks: int
    storage_bytes: int
    category_distribution: Dict[str, int]
    file_type_distribution: Dict[str, int]
    task_status_distribution: Dict[str, int]

class SystemStats(BaseModel):
    total_documents: int
    total_chunks: int
    total_edges: int
    database_engine: str
    version: str
    status: str
