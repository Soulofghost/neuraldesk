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


# ================= CLOUD STORAGE SCHEMAS =================
class StorageFolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    parent_id: Optional[str] = None
    color: Optional[str] = "#e6a23c"
    workspace_id: Optional[str] = "default"

class StorageFolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None
    color: Optional[str] = None
    is_trash: Optional[int] = None

class StorageFolderResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    parent_id: Optional[str] = None
    name: str
    color: str
    is_trash: int
    created_at: str
    updated_at: str
    file_count: Optional[int] = 0

class PresignedUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., gt=0)
    mime_type: Optional[str] = "application/octet-stream"
    folder_id: Optional[str] = None
    workspace_id: Optional[str] = "default"

class PresignedUploadResponse(BaseModel):
    upload_url: str
    method: str
    headers: Dict[str, str]
    storage_key: str
    provider: str
    expires_in: int
    file_id: str

class UploadCompleteRequest(BaseModel):
    storage_key: str
    filename: str
    file_size: int
    mime_type: Optional[str] = "application/octet-stream"
    folder_id: Optional[str] = None
    workspace_id: Optional[str] = "default"
    checksum: Optional[str] = ""

class StorageFileUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[str] = None
    is_favorite: Optional[int] = None
    is_trash: Optional[int] = None

class StorageFileResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    folder_id: Optional[str] = None
    name: str
    original_name: str
    storage_key: str
    storage_provider: str
    file_size: int
    mime_type: str
    file_extension: str
    checksum: str
    is_favorite: int
    is_trash: int
    version: int
    created_at: str
    updated_at: str
    download_url: Optional[str] = None

class FileShareCreate(BaseModel):
    access_type: Optional[str] = "public_read" # public_read, download_only
    expires_in_hours: Optional[int] = 72

class FileShareResponse(BaseModel):
    id: str
    file_id: Optional[str] = None
    token: str
    access_type: str
    share_url: str
    expires_at: Optional[str] = None
    created_at: str

class StorageDashboardResponse(BaseModel):
    total_files: int
    total_folders: int
    used_storage_bytes: int
    used_storage_mb: float
    storage_quota_mb: int
    usage_percentage: float
    file_type_distribution: Dict[str, int]
    provider: str
    provider_status: str
    is_r2_active: bool
    recent_files: List[StorageFileResponse]
    large_files: List[StorageFileResponse]

# ================= DOCUMENT VERSIONS & COMPARISON =================
class BulkDocumentAction(BaseModel):
    action: str = Field(..., description="Action to perform: trash, restore, delete, favorite, unfavorite, categorize")
    document_ids: List[str] = Field(..., min_length=1)
    category: Optional[str] = None

class DocumentVersionResponse(BaseModel):
    id: str
    document_id: str
    version_number: int
    title: str
    content: str
    created_at: str

class DocumentDiffRequest(BaseModel):
    document_id: str
    version_a: int
    version_b: int

class DocumentDiffResponse(BaseModel):
    document_id: str
    version_a: int
    version_b: int
    diff_text: str
    additions: int
    deletions: int

# ================= GLOBAL SEARCH SCHEMAS =================
class GlobalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    workspace_id: Optional[str] = "default"
    types: Optional[List[str]] = ["documents", "files", "notes", "tasks"]
    limit: Optional[int] = 20

class GlobalSearchResult(BaseModel):
    id: str
    type: str # document, file, note, task
    title: str
    snippet: str
    score: float
    metadata: Dict[str, Any]

class GlobalSearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[GlobalSearchResult]
