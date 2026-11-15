# NeuralDesk 2.0 — AI-Powered Knowledge Architecture & SaaS Platform

**Author:** Alvin MS ([@Soulofghost](https://github.com/Soulofghost))  
**Domain:** Artificial Intelligence & Information Retrieval  
**Tier:** ⭐ Flagship Portfolio Project  
**Status:** Verified & Production-Ready  
**Deployment:** Vercel Edge & Serverless Python 3.12 + Neon / Supabase PostgreSQL

---

## 1. Project Introduction

**NeuralDesk 2.0** is an enterprise-grade AI knowledge architecture and research assistant platform. It bridges unstructured documentation, dense subword vector retrieval, conversational RAG question-answering with citation grounding, dynamic concept graph visualization, notes capture, and action item Kanban pipelines.

Built with a high-throughput, decoupled FastAPI backend and a responsive desktop-class Obsidian-inspired workspace, NeuralDesk automatically partitions documents into overlapping semantic chunks, indexes them into high-dimensional vector spaces, establishes bidirectional relationship edges, and provides AI synthesis grounded strictly in verified source passages.

---

## 2. Problem Statement

Modern engineering and research organizations face acute knowledge fragmentation:
- Documentation scattered across wikis, PDFs, spreadsheets, and markdown files lacks cross-format discoverability.
- Traditional full-text keyword search fails on conceptual synonyms and paraphrased engineering queries.
- Static documents do not convey inter-service architectural dependencies or relational context.
- Generative AI assistants often hallucinate or fail to cite specific passages in corporate technical documents.
- Cloud vector databases introduce prohibitive cost and external latency overheads for localized and privacy-sensitive team knowledge bases.

---

## 3. Proposed Solution

NeuralDesk 2.0 provides an embedded, self-contained semantic knowledge engine:
- **Zero-External-API Dependency:** Employs a deterministic L2-normalized Subword N-gram Vector Engine generating continuous 384-dimensional dense vectors locally.
- **Hybrid Retrieval:** Blends vector cosine similarity (70%) with lexical token matching (30%) to ensure high precision on technical acronyms and semantic topics alike.
- **Multi-Format Ingestion:** Native, zero-C-dependency parser supporting PDF (`pypdf`), Word DOCX (OpenXML parsing via `zipfile`), CSV, Markdown, TXT, and JSON.
- **Citation-Grounded AI Assistant:** Conversational sessions with transparent attribution (`[Doc Title, Chunk #X]`), suggested prompt chips, and extractive salience summarization.
- **Action Item & Kanban Pipeline:** Automatic extraction of engineering deliverables and milestones from documents into interactive Kanban boards (`To Do`, `In Progress`, `Completed`).
- **Relational Notes & Collaboration:** Context-linked knowledge notes, document commenting, persistent public share links with secure tokens, and workspace isolation.
- **Dual Persistence Architecture:** Seamless local SQLite with WAL mode and serverless-compatible connection-pooled PostgreSQL (Neon / Supabase).

---

## 4. Key SaaS Modules

### A. Intelligent Dashboard
- Real-time telemetry: Total documents, dense vector chunks, knowledge notes, active tasks, and storage quota meter.
- Category breakdown and supported file format distributions.
- Live system activity stream and audit log tracking creates, updates, AI queries, and shares.

### B. Advanced Document Management
- Multi-format file ingestion (PDF, DOCX, TXT, MD, CSV, JSON) via drag-and-drop or file picker.
- Document lifecycle filters: Active, Favorites (⭐), Archive, and Trash & Restore.
- One-click document export to formatted Markdown (`.md`) or raw JSON.
- Real-time chunk telemetry drawer and semantic graph backlinks.

### C. AI Document Intelligence
- **Extractive Salience Summarization:** Top sentence scoring using token frequency and position weights.
- **Key Proposition Takeaways:** Structural concept extraction without hallucination.
- **Entity & Concept Detection:** Automatically detects architectural patterns, libraries, protocols, and system components.
- **Action Item Extraction:** Auto-extracts action verbs, deliverables, and priorities from documentation with one-click conversion to tasks.

### D. Conversational AI Assistant
- Multi-turn conversational research sessions with workspace or document scope selection.
- Grounded responses with clickable citation tags referencing source chunk provenance.
- Pre-configured prompt templates for architectural trade-off summaries, data consistency analyses, and action-item auditing.

### E. Notes & Knowledge Capture
- Rich notes grid with pinning (`is_pinned`), tagging (`#tag`), and bidirectional document linkage.
- Live keyword search across notes.

### F. Kanban Action Item Pipeline
- Status progression: `To Do` ➔ `In Progress` ➔ `Completed`.
- Priority indicators: `low`, `medium`, `high`, `urgent`.
- Auto-extraction button to populate tasks directly from active documents.

### G. Concept Graph Visualization 2.0
- Interactive SVG canvas with category color-coding (Architecture: Blue, Engineering: Green, Research: Purple, General: Amber).
- Dynamic edge weight calculation based on shared taxonomy and vector cosine proximity.
- Real-time topology recalculation across active workspace documents.

### H. Multi-Workspace Isolation & Collaboration
- Switch workspaces seamlessly or create new isolated knowledge domains.
- Document commenting and team discussion threads.
- Public read share tokens with expiration tracking.

---

## 5. Architecture Diagram

```mermaid
graph TD
    Client[Web UI / REST Client] --> Gateway[FastAPI Router Gateway]
    
    Gateway --> Auth[Auth & RBAC Service]
    Gateway --> DocService[Document Ingestion & Multi-Format Parser]
    Gateway --> SearchService[Hybrid Semantic & Lexical Search]
    Gateway --> AIService[AI Intelligence & Conversational RAG]
    Gateway --> NotesService[Notes & Knowledge Capture]
    Gateway --> TasksService[Tasks & Kanban Pipeline]
    Gateway --> CollabService[Collaboration & Share Tokens]
    Gateway --> GraphService[Concept Graph Topology Engine]

    DocService --> Parser[PDF / DOCX / MD / CSV / TXT Parser]
    Parser --> Chunker[Sliding Window Text Chunker]
    Chunker --> Embedder[Normalized Vector Embedder]
    
    Embedder --> Persistence[(Relational Persistence: PostgreSQL / SQLite)]
    AIService --> Chunker
    AIService --> Persistence
    SearchService --> Embedder
    SearchService --> Persistence
    GraphService --> Persistence
```

---

## 6. Technology Stack

- **Backend:** Python 3.12+, FastAPI, Uvicorn, Pydantic v2
- **Persistence:** PostgreSQL (Neon / Supabase with `ThreadedConnectionPool`) and SQLite 3 (WAL mode fallback)
- **Document Parsing:** `pypdf` (pure-Python PDF extraction), `zipfile` + `xml.etree` (zero-dependency Word DOCX extraction), standard `csv`
- **Mathematical Processing:** Subword N-gram Hashing, Cosine Similarity, Reciprocal Rank Fusion
- **Security & Auth:** PBKDF2 Password Hashing (350k iterations), PyJWT, Security Headers Middleware
- **Frontend:** Vanilla JavaScript (ES6+), Modern CSS Custom Properties, SVG Canvas API
- **Deployment Platform:** Vercel Serverless Functions (`api/index.py`) + Vercel Edge CDN (`public/`)
- **Testing & CI:** Pytest, HTTPX, GitHub Actions

---

## 7. Folder Structure

```
neuraldesk/
├── api/
│   └── index.py                 # Vercel serverless function entrypoint
├── backend/
│   ├── app/
│   │   ├── engine/
│   │   │   ├── chunker.py       # Sliding window text chunking logic
│   │   │   ├── embeddings.py    # Vector embedding & cosine similarity
│   │   │   ├── graph.py         # Dynamic node and edge generator
│   │   │   ├── intelligence.py  # Extractive summarization, entities & RAG Q&A
│   │   │   └── parser.py        # Multi-format parser (PDF, DOCX, CSV, MD, TXT)
│   │   ├── routers/
│   │   │   ├── admin.py         # Admin telemetry & plan management
│   │   │   ├── analytics.py     # Real-time dashboard analytics
│   │   │   ├── auth.py          # User registration, login & JWT auth
│   │   │   ├── chat.py          # Conversational AI sessions & messages
│   │   │   ├── collaboration.py # Share tokens, comments & activity logs
│   │   │   ├── documents.py     # Document CRUD, views, favorites & export
│   │   │   ├── graph.py         # Knowledge graph telemetry router
│   │   │   ├── intelligence.py  # Summaries, entity extraction & QA endpoints
│   │   │   ├── notes.py         # Notes CRUD, pinning & doc linking
│   │   │   ├── search.py        # Hybrid semantic search router
│   │   │   ├── tasks.py         # Kanban tasks & auto-extraction
│   │   │   └── workspaces.py    # Multi-workspace isolation
│   │   ├── auth.py              # PBKDF2 hashing & JWT utilities
│   │   ├── config.py            # Environment, runtime paths & serverless detection
│   │   ├── database.py          # Unified PostgreSQL/SQLite connection & schemas
│   │   ├── main.py              # Application entrypoint & static mount
│   │   └── schemas.py           # Pydantic request/response models
│   ├── requirements.txt         # Production backend dependencies
│   └── tests/
│       ├── test_chunker.py      # Chunking boundary unit tests
│       ├── test_embeddings.py   # Embedding math & cosine tests
│       ├── test_database.py     # Database adapter & Postgres detection tests
│       ├── test_api.py          # Full integration test suite (21 tests)
│       └── test_vercel.py       # Vercel serverless entrypoint tests
├── frontend/
│   ├── index.html               # Semantic layout for Dashboard, Chat, Notes, Tasks, Docs
│   ├── style.css                # Obsidian & amber design system + Light theme
│   └── app.js                   # Client state manager, SVG graph, and API client
├── public/                      # Static assets served via Vercel Edge CDN
├── .github/workflows/ci.yml     # Automated test workflow
├── .env.example                 # Environment defaults
├── .gitignore                   # Standard ignore rules
├── .python-version              # Target Python runtime (3.12)
├── .vercelignore                # Files excluded from Vercel deployment
├── Dockerfile                   # Multi-stage production container
├── docker-compose.yml           # Local deployment manifest
├── requirements.txt             # Root dependency manifest for Vercel
├── vercel.json                  # Vercel routing, rewrites & headers config
├── LICENSE                      # MIT License
└── README.md                    # System documentation
```

---

## 8. Installation & Local Development

### Prerequisites
- Python 3.10+ (or `uv` package runner)
- Git

### Local Setup
```bash
# Clone the repository
git clone https://github.com/Soulofghost/neuraldesk.git
cd neuraldesk

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Run server with live reload
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to `http://127.0.0.1:8000` to launch the workspace.

---

## 9. Environment Configuration

Copy `.env.example` to `.env`:
```ini
ENVIRONMENT=development
PORT=8000

# Database Persistence:
# Leave empty for local SQLite (backend/data/neuraldesk.db)
# Or set PostgreSQL connection string for permanent cloud storage:
# DATABASE_URL=postgresql://user:password@host/database?sslmode=require

DB_PATH=backend/data/neuraldesk.db

# Authentication
JWT_SECRET_KEY=neuraldesk-production-super-secret-key-change-me-in-production
STORAGE_QUOTA_MB=500
```

---

## 10. API Documentation

Interactive OpenAPI documentation is accessible at `/docs` (and `/api/docs`).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status and database engine telemetry |
| `GET` | `/api/v1/stats` | Real-time system telemetry (counts of documents, chunks, graph edges) |
| `GET` | `/api/v1/analytics/dashboard` | Aggregated dashboard metrics, storage, distributions, and activity |
| `POST` | `/api/v1/auth/register` | Register new user account |
| `POST` | `/api/v1/auth/login` | Authenticate user and receive JWT access token |
| `GET` | `/api/v1/auth/me` | Fetch currently authenticated user profile |
| `GET` | `/api/v1/workspaces` | List accessible workspaces |
| `POST` | `/api/v1/workspaces` | Create isolated workspace |
| `GET` | `/api/v1/documents` | List documents with workspace, view, and category filtering |
| `POST` | `/api/v1/documents` | Create document, calculate semantic chunks and vector embeddings |
| `POST` | `/api/v1/documents/upload` | Ingest PDF, DOCX, TXT, MD, CSV, or JSON file |
| `GET` | `/api/v1/documents/{id}`| Fetch document, chunk vectors, and relational backlinks |
| `POST` | `/api/v1/documents/{id}/favorite`| Toggle favorite status |
| `POST` | `/api/v1/documents/{id}/restore`| Restore document from Trash |
| `GET` | `/api/v1/documents/{id}/export`| Export document as formatted Markdown (`.md`) or raw JSON |
| `PUT` | `/api/v1/documents/{id}`| Update document content and recalculate vector index & graph edges |
| `DELETE` | `/api/v1/documents/{id}`| Move document to trash / cascade deletion |
| `POST` | `/api/v1/intelligence/summarize` | Generate extractive salience summary and key takeaways |
| `POST` | `/api/v1/intelligence/entities` | Extract named entities and architectural patterns |
| `POST` | `/api/v1/intelligence/action-items` | Extract actionable tasks and deliverables |
| `POST` | `/api/v1/intelligence/ask` | Grounded question-answering with citation attribution |
| `GET` | `/api/v1/chat/conversations` | List conversational AI sessions |
| `POST` | `/api/v1/chat/conversations` | Create new conversational research session |
| `POST` | `/api/v1/chat/conversations/{id}/messages` | Send query and receive citation-grounded response |
| `GET` | `/api/v1/notes` | List knowledge capture notes |
| `POST` | `/api/v1/notes` | Create note with optional document link and tags |
| `GET` | `/api/v1/tasks` | List Kanban tasks with status and priority filters |
| `POST` | `/api/v1/tasks` | Create task |
| `POST` | `/api/v1/tasks/extract-from-doc/{id}` | Automatically extract and generate tasks from document |
| `POST` | `/api/v1/collaboration/documents/{id}/share` | Generate persistent public share token |
| `GET` | `/api/v1/collaboration/documents/{id}/comments` | List document comments and discussion |
| `POST` | `/api/v1/search` | Execute hybrid semantic (70%) and lexical (30%) search |
| `GET` | `/api/v1/graph` | Retrieve nodes and weighted edges for interactive SVG topology canvas |
| `POST` | `/api/v1/graph/recompute` | Recalculate edge topology across all documents in knowledge base |

---

## 11. Testing Instructions

NeuralDesk includes a comprehensive automated test suite testing text chunking boundaries, vector mathematical properties, multi-format parsing, and complete API integration across all 12 router modules:

```bash
# Execute full test suite
pytest backend/tests/ -v
```

---

## 12. Deployment Instructions

### Vercel Serverless Deployment (Production Ready)

NeuralDesk is engineered for zero-config Vercel serverless deployment:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FSoulofghost%2Fneuraldesk)

#### Step-by-Step Vercel Setup:
1. Push your repository to GitHub: `https://github.com/Soulofghost/neuraldesk`.
2. In the [Vercel Dashboard](https://vercel.com/new), click **Add New Project** and select your repository.
3. Vercel automatically detects `vercel.json`, `public/` (for static CDN caching), and `api/index.py` (FastAPI serverless entrypoint).
4. **Environment Variables (Optional for Persistence):**
   - For permanent production storage, create a free PostgreSQL database on [Neon](https://neon.tech) or [Supabase](https://supabase.com).
   - Add `DATABASE_URL` in Vercel Project Settings ➔ Environment Variables:
     ```
     DATABASE_URL=postgresql://<username>:<password>@<neon-host>/neondb?sslmode=require
     ```
   - If `DATABASE_URL` is omitted, NeuralDesk runs with localized SQLite in `/tmp`.
5. Click **Deploy**.

---

## 13. Security Considerations

- **Input Sanitization & Escaping:** All HTML, user comments, and Markdown inputs are strictly escaped before DOM insertion.
- **Parameterized SQL:** All database transactions employ parameterized queries via Python SQLite bindings or psycopg2 to prevent SQL injection vulnerabilities.
- **Zero Remote Leakage:** Vector embedding and indexing run purely local without sending document contents to third-party model providers.
- **HTTP Security Headers:** Integrated middleware enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.
- **Payload & File Restrictions:** File uploads are validated with strict extension checks (`.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`) and memory limits.

---

## 14. License

Distributed under the MIT License. See `LICENSE` for details.
