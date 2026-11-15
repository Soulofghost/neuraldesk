let currentDocId = null;
let allDocuments = [];
let currentCategory = "ALL";
let isSaving = false;
let isDirty = false;

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    setupEventListeners();
    setupKeyboardShortcuts();
    setupDragAndDrop();
    await loadSystemStats();
    await loadDocuments();
    await checkInitialSeed();
}

/* ==========================================================
   TOAST NOTIFICATION SYSTEM
   ========================================================== */
function showToast(message, type = "info", duration = 3500) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    const iconMap = {
        success: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2ea043" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
        error: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f85149" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`,
        info: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e6a23c" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`
    };

    toast.innerHTML = `
        <span class="toast-icon">${iconMap[type] || iconMap.info}</span>
        <span class="toast-message">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(8px)";
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/* ==========================================================
   EVENT LISTENERS & NAVIGATION
   ========================================================== */
function setupEventListeners() {
    // New Document
    document.getElementById("btn-new-doc").addEventListener("click", () => {
        if (isDirty && !confirm("You have unsaved changes. Discard and create a new document?")) {
            return;
        }
        resetEditor();
        closeMobileSidebar();
    });

    // Save Document
    document.getElementById("btn-save-doc").addEventListener("click", () => {
        saveDocument();
    });

    // Delete Document
    document.getElementById("btn-delete-doc").addEventListener("click", () => {
        if (currentDocId && confirm("Are you sure you want to delete this document from the knowledge base?")) {
            deleteDocument(currentDocId);
        }
    });

    // Export Document (.md)
    document.getElementById("btn-export-doc").addEventListener("click", () => {
        if (currentDocId) {
            exportCurrentDocument();
        }
    });

    // File Import / Upload
    const btnUpload = document.getElementById("btn-upload-doc");
    const fileInput = document.getElementById("file-upload-input");
    btnUpload.addEventListener("click", () => {
        fileInput.value = "";
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files[0]) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Category Filter Chips
    const chips = document.querySelectorAll("#category-list .chip");
    chips.forEach(chip => {
        chip.addEventListener("click", () => {
            chips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            currentCategory = chip.dataset.category;
            renderDocumentList();
        });
    });

    // View Toggles
    const tabDoc = document.getElementById("tab-doc");
    const tabGraph = document.getElementById("tab-graph");
    const docPane = document.getElementById("doc-pane");
    const graphPane = document.getElementById("graph-pane");

    tabDoc.addEventListener("click", () => {
        tabDoc.classList.add("active");
        tabGraph.classList.remove("active");
        docPane.classList.add("active");
        graphPane.classList.remove("active");
    });

    tabGraph.addEventListener("click", () => {
        tabGraph.classList.add("active");
        tabDoc.classList.remove("active");
        graphPane.classList.add("active");
        docPane.classList.remove("active");
        renderKnowledgeGraph();
    });

    // Search Trigger (Enter or Search Icon)
    const searchInput = document.getElementById("hybrid-search-input");
    const searchIcon = document.getElementById("btn-trigger-search");

    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            const query = searchInput.value.trim();
            if (query.length > 0) {
                executeHybridSearch(query);
            } else {
                showToast("Please enter a search query.", "info");
            }
        }
    });

    searchIcon.addEventListener("click", () => {
        const query = searchInput.value.trim();
        if (query.length > 0) {
            executeHybridSearch(query);
        } else {
            searchInput.focus();
        }
    });

    // Search Modal Close
    document.getElementById("btn-close-modal").addEventListener("click", () => {
        document.getElementById("search-modal").classList.remove("open");
    });

    document.getElementById("search-modal").addEventListener("click", (e) => {
        if (e.target.id === "search-modal") {
            document.getElementById("search-modal").classList.remove("open");
        }
    });

    // Graph Refresh
    document.getElementById("btn-refresh-graph").addEventListener("click", () => {
        recomputeTopology();
    });

    // Mobile Sidebar Toggles
    const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
    const btnCloseSidebar = document.getElementById("btn-close-sidebar");
    const sidebarBackdrop = document.getElementById("sidebar-backdrop");

    btnToggleSidebar.addEventListener("click", () => {
        document.getElementById("app-sidebar").classList.add("open");
        sidebarBackdrop.classList.add("active");
    });

    btnCloseSidebar.addEventListener("click", closeMobileSidebar);
    sidebarBackdrop.addEventListener("click", closeMobileSidebar);

    // Track Dirty State
    const titleInput = document.getElementById("doc-title-input");
    const contentInput = document.getElementById("doc-content-input");
    [titleInput, contentInput].forEach(el => {
        el.addEventListener("input", () => {
            isDirty = true;
        });
    });
}

function closeMobileSidebar() {
    const sidebar = document.getElementById("app-sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("active");
}

function setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
        // Ctrl+S / Cmd+S: Save document
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            saveDocument();
        }
        // Ctrl+K / Cmd+K: Focus search
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            const searchInput = document.getElementById("hybrid-search-input");
            if (searchInput) searchInput.focus();
        }
        // Escape: Close search modal & mobile sidebar
        if (e.key === "Escape") {
            document.getElementById("search-modal").classList.remove("open");
            closeMobileSidebar();
        }
    });
}

function setupDragAndDrop() {
    const container = document.querySelector(".editor-container");
    if (!container) return;

    ["dragenter", "dragover"].forEach(eventName => {
        container.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            container.classList.add("drag-over");
        });
    });

    ["dragleave", "drop"].forEach(eventName => {
        container.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            container.classList.remove("drag-over");
        });
    });

    container.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        if (dt.files && dt.files.length > 0) {
            handleFileUpload(dt.files[0]);
        }
    });
}

/* ==========================================================
   SYSTEM TELEMETRY
   ========================================================== */
async function loadSystemStats() {
    try {
        const res = await fetch("/api/v1/stats");
        if (res.ok) {
            const stats = await res.json();
            const label = document.getElementById("system-status-label");
            if (label) {
                label.textContent = `${stats.database_engine} • ${stats.total_documents} Docs • ${stats.total_chunks} Chunks`;
            }
        }
    } catch (err) {
        console.warn("Telemetry stats unavailable:", err);
    }
}

/* ==========================================================
   DOCUMENT MANAGEMENT (CRUD)
   ========================================================== */
async function loadDocuments() {
    try {
        const res = await fetch("/api/v1/documents");
        if (!res.ok) throw new Error("Failed to load documents");
        allDocuments = await res.json();
        renderDocumentList();
        document.getElementById("doc-count").textContent = allDocuments.length;
    } catch (err) {
        console.error("Error loading documents:", err);
        showToast("Failed to load documents from database.", "error");
    }
}

function renderDocumentList() {
    const list = document.getElementById("document-list");
    list.innerHTML = "";

    const filtered = currentCategory === "ALL" 
        ? allDocuments 
        : allDocuments.filter(d => d.category === currentCategory);

    if (filtered.length === 0) {
        list.innerHTML = `
            <div style="padding:16px; text-align:center; font-size:12px; color:var(--text-muted);">
                No documents in this category.<br>
                <span style="font-size:11px; color:var(--accent-amber); cursor:pointer;" id="create-prompt-btn">+ Create document</span>
            </div>
        `;
        const promptBtn = document.getElementById("create-prompt-btn");
        if (promptBtn) {
            promptBtn.addEventListener("click", () => {
                resetEditor();
                if (currentCategory !== "ALL") {
                    document.getElementById("doc-category-select").value = currentCategory;
                }
            });
        }
        return;
    }

    filtered.forEach(doc => {
        const item = document.createElement("div");
        item.className = `doc-item ${doc.id === currentDocId ? 'active' : ''}`;
        item.innerHTML = `
            <div class="doc-item-title">${escapeHtml(doc.title)}</div>
            <div class="doc-item-meta">
                <span>[${escapeHtml(doc.category)}]</span>
                <span>• ${doc.chunk_count || 1} chunks</span>
            </div>
        `;
        item.addEventListener("click", () => {
            selectDocument(doc.id);
            closeMobileSidebar();
        });
        list.appendChild(item);
    });
}

async function selectDocument(id) {
    try {
        const res = await fetch(`/api/v1/documents/${id}`);
        if (!res.ok) throw new Error("Document not found");
        const doc = await res.json();
        currentDocId = doc.id;
        isDirty = false;

        document.getElementById("doc-title-input").value = doc.title;
        document.getElementById("doc-category-select").value = doc.category;
        document.getElementById("doc-tags-input").value = (doc.tags || []).join(", ");
        document.getElementById("doc-content-input").value = doc.content;
        
        document.getElementById("btn-delete-doc").style.display = "inline-block";
        document.getElementById("btn-export-doc").style.display = "inline-block";

        renderTelemetryDrawer(doc);
        renderDocumentList();
    } catch (err) {
        console.error("Failed to select document:", err);
        showToast("Error retrieving document details.", "error");
    }
}

function renderTelemetryDrawer(doc) {
    const chunkCount = (doc.chunks && doc.chunks.length) || 0;
    document.getElementById("chunk-info").textContent = `${chunkCount} Chunks Generated`;
    const drawer = document.getElementById("drawer-content");
    drawer.innerHTML = "";

    // Show related graph connections
    if (doc.related && doc.related.length > 0) {
        const relDiv = document.createElement("div");
        relDiv.style.marginBottom = "10px";
        relDiv.innerHTML = `<div style="font-size:11px; font-weight:600; color:var(--text-muted); margin-bottom:6px; letter-spacing:0.5px;">SEMANTIC RELATIONS & BACKLINKS:</div>`;
        
        doc.related.forEach(r => {
            const span = document.createElement("span");
            span.className = "related-chip";
            span.textContent = `↔ ${r.title} (${r.type}, score: ${r.weight})`;
            span.style.cursor = "pointer";
            span.title = "Click to open related document";
            span.addEventListener("click", () => selectDocument(r.id));
            relDiv.appendChild(span);
        });
        drawer.appendChild(relDiv);
    }

    // Show chunks
    if (doc.chunks && doc.chunks.length > 0) {
        doc.chunks.forEach(c => {
            const chunkBadge = document.createElement("div");
            chunkBadge.className = "chunk-badge";
            chunkBadge.innerHTML = `<strong>[Chunk #${c.index + 1}]</strong>: ${escapeHtml(c.content.substring(0, 160))}${c.content.length > 160 ? '...' : ''}`;
            drawer.appendChild(chunkBadge);
        });
    } else {
        drawer.innerHTML = `<div class="empty-state">No semantic chunks generated for this document yet.</div>`;
    }
}

function resetEditor() {
    currentDocId = null;
    isDirty = false;
    document.getElementById("doc-title-input").value = "";
    document.getElementById("doc-category-select").value = "General";
    document.getElementById("doc-tags-input").value = "";
    document.getElementById("doc-content-input").value = "";
    document.getElementById("btn-delete-doc").style.display = "none";
    document.getElementById("btn-export-doc").style.display = "none";
    document.getElementById("chunk-info").textContent = "0 Chunks Generated";
    document.getElementById("drawer-content").innerHTML = `<div class="empty-state">New document draft. Enter content and save to index.</div>`;
    renderDocumentList();
    document.getElementById("doc-title-input").focus();
}

async function saveDocument() {
    if (isSaving) return;

    const title = document.getElementById("doc-title-input").value.trim();
    const content = document.getElementById("doc-content-input").value.trim();
    const category = document.getElementById("doc-category-select").value;
    const tagsRaw = document.getElementById("doc-tags-input").value;
    const tags = tagsRaw.split(",").map(t => t.trim()).filter(t => t.length > 0);

    // Validation
    if (!title) {
        showToast("Please enter a document title.", "error");
        document.getElementById("doc-title-input").focus();
        return;
    }
    if (!content) {
        showToast("Document content cannot be empty.", "error");
        document.getElementById("doc-content-input").focus();
        return;
    }

    const payload = { title, content, category, tags };
    const saveBtn = document.getElementById("btn-save-doc");
    const originalText = saveBtn.textContent;

    try {
        isSaving = true;
        saveBtn.disabled = true;
        saveBtn.textContent = "Indexing...";

        let res;
        if (currentDocId) {
            res = await fetch(`/api/v1/documents/${currentDocId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } else {
            res = await fetch("/api/v1/documents", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.detail || "Failed to save document");
        }

        const saved = await res.json();
        currentDocId = saved.id;
        isDirty = false;

        showToast(`"${saved.title}" saved and indexed (${saved.chunk_count} chunks).`, "success");
        await loadDocuments();
        await selectDocument(saved.id);
        await loadSystemStats();
    } catch (err) {
        console.error("Save error:", err);
        showToast("Error saving document: " + err.message, "error");
    } finally {
        isSaving = false;
        saveBtn.disabled = false;
        saveBtn.textContent = originalText;
    }
}

async function deleteDocument(id) {
    const deleteBtn = document.getElementById("btn-delete-doc");
    deleteBtn.disabled = true;
    deleteBtn.textContent = "Deleting...";

    try {
        const res = await fetch(`/api/v1/documents/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error("Failed to delete document from database");
        
        showToast("Document deleted successfully.", "success");
        resetEditor();
        await loadDocuments();
        await loadSystemStats();
    } catch (err) {
        console.error("Delete error:", err);
        showToast("Error deleting document: " + err.message, "error");
    } finally {
        deleteBtn.disabled = false;
        deleteBtn.textContent = "Delete";
    }
}

function exportCurrentDocument() {
    if (!currentDocId) return;
    window.open(`/api/v1/documents/${currentDocId}/export?format=md`, "_blank");
}

async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("category", document.getElementById("doc-category-select").value || "General");

    const uploadBtn = document.getElementById("btn-upload-doc");
    const originalText = uploadBtn.innerHTML;

    try {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = `<span>Uploading...</span>`;

        const res = await fetch("/api/v1/documents/upload", {
            method: "POST",
            body: formData
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to import document");
        }

        const saved = await res.json();
        showToast(`Imported "${saved.title}" successfully!`, "success");
        await loadDocuments();
        await selectDocument(saved.id);
        await loadSystemStats();
    } catch (err) {
        console.error("Import error:", err);
        showToast("Import failed: " + err.message, "error");
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalText;
    }
}

/* ==========================================================
   HYBRID VECTOR & LEXICAL SEARCH
   ========================================================== */
async function executeHybridSearch(query) {
    try {
        showToast(`Searching for "${query}"...`, "info", 1500);
        const res = await fetch("/api/v1/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query,
                limit: 10,
                category: currentCategory !== "ALL" ? currentCategory : null
            })
        });

        if (!res.ok) throw new Error("Search service failed to respond");
        const results = await res.json();
        renderSearchResults(query, results);
    } catch (err) {
        console.error("Search query error:", err);
        showToast("Search failed: " + err.message, "error");
    }
}

function renderSearchResults(query, results) {
    const container = document.getElementById("search-results-list");
    container.innerHTML = "";

    if (results.length === 0) {
        container.innerHTML = `
            <div style="padding:32px 16px; text-align:center; color:var(--text-muted);">
                <p style="font-size:14px; margin-bottom:8px;">No matching passages found for query <strong>"${escapeHtml(query)}"</strong></p>
                <p style="font-size:12px;">Try different keywords or switch category filter to "All Nodes".</p>
            </div>
        `;
    } else {
        results.forEach(r => {
            const card = document.createElement("div");
            card.className = "result-card";
            const highlightedContent = highlightQuery(r.content, query);
            
            card.innerHTML = `
                <div class="result-card-header">
                    <span style="font-weight:600; font-size:13px; color:var(--text-primary);">${escapeHtml(r.document_title)} [Chunk #${r.chunk_index + 1}]</span>
                    <span class="result-score">Hybrid Relevance: ${(r.score * 100).toFixed(1)}%</span>
                </div>
                <div class="result-snippet">${highlightedContent}</div>
            `;
            card.addEventListener("click", () => {
                document.getElementById("search-modal").classList.remove("open");
                selectDocument(r.document_id);
            });
            container.appendChild(card);
        });
    }

    document.getElementById("search-modal").classList.add("open");
}

function highlightQuery(text, query) {
    if (!query) return escapeHtml(text);
    const escapedText = escapeHtml(text);
    const words = query.trim().split(/\s+/).filter(w => w.length > 2);
    if (words.length === 0) return escapedText;

    const regex = new RegExp(`(${words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    return escapedText.replace(regex, '<span class="highlight-term">$1</span>');
}

/* ==========================================================
   KNOWLEDGE GRAPH VISUALIZATION
   ========================================================== */
async function renderKnowledgeGraph() {
    const svg = document.getElementById("graph-svg");
    svg.innerHTML = "";

    try {
        const res = await fetch("/api/v1/graph");
        if (!res.ok) throw new Error("Failed to load knowledge graph");
        const { nodes, edges } = await res.json();

        if (nodes.length === 0) {
            svg.innerHTML = `
                <text x="50%" y="50%" fill="#6e7681" text-anchor="middle" font-size="13">
                    No document nodes available. Add or import documents to generate graph topology.
                </text>
            `;
            return;
        }

        const width = svg.clientWidth || 800;
        const height = svg.clientHeight || 500;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) * 0.38;

        const nodePositions = {};
        const angleStep = (2 * Math.PI) / nodes.length;

        nodes.forEach((node, i) => {
            const angle = i * angleStep;
            nodePositions[node.id] = {
                x: centerX + radius * Math.cos(angle),
                y: centerY + radius * Math.sin(angle),
                node: node
            };
        });

        // Draw Edges
        edges.forEach(edge => {
            const src = nodePositions[edge.source];
            const tgt = nodePositions[edge.target];
            if (src && tgt) {
                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", src.x);
                line.setAttribute("y1", src.y);
                line.setAttribute("x2", tgt.x);
                line.setAttribute("y2", tgt.y);
                line.setAttribute("stroke", "#28303e");
                line.setAttribute("stroke-width", Math.max(1.2, edge.weight * 3));
                line.setAttribute("stroke-opacity", "0.75");
                
                const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
                title.textContent = `Relation: ${edge.relation} (Weight: ${edge.weight})`;
                line.appendChild(title);

                svg.appendChild(line);
            }
        });

        // Category Color Mapping
        const colorMap = {
            "Architecture": "#388bfd",
            "Engineering": "#2ea043",
            "Research": "#a371f7",
            "General": "#e6a23c"
        };

        // Draw Nodes
        nodes.forEach(node => {
            const pos = nodePositions[node.id];
            const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
            g.style.cursor = "pointer";

            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", pos.x);
            circle.setAttribute("cy", pos.y);
            circle.setAttribute("r", 15);
            circle.setAttribute("fill", colorMap[node.category] || "#e6a23c");
            circle.setAttribute("stroke", "#161b22");
            circle.setAttribute("stroke-width", "3");

            const titleElem = document.createElementNS("http://www.w3.org/2000/svg", "title");
            titleElem.textContent = `${node.label} (${node.category}) - Click to open`;
            g.appendChild(titleElem);

            const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
            label.setAttribute("x", pos.x);
            label.setAttribute("y", pos.y + 24);
            label.setAttribute("fill", "#c9d1d9");
            label.setAttribute("font-size", "11");
            label.setAttribute("font-family", "JetBrains Mono, monospace");
            label.setAttribute("text-anchor", "middle");
            label.textContent = node.label.length > 20 ? node.label.substring(0, 18) + "..." : node.label;

            g.appendChild(circle);
            g.appendChild(label);

            g.addEventListener("click", () => {
                document.getElementById("tab-doc").click();
                selectDocument(node.id);
            });

            svg.appendChild(g);
        });

    } catch (err) {
        console.error("Graph render error:", err);
        showToast("Error rendering graph canvas.", "error");
    }
}

async function recomputeTopology() {
    const btn = document.getElementById("btn-refresh-graph");
    btn.disabled = true;
    btn.textContent = "Recalculating...";

    try {
        const res = await fetch("/api/v1/graph/recompute", { method: "POST" });
        if (!res.ok) throw new Error("Topology calculation failed");
        showToast("Topology recalculated across all documents.", "success");
        await renderKnowledgeGraph();
        await loadSystemStats();
    } catch (err) {
        console.error("Recompute error:", err);
        showToast("Failed to recalculate topology: " + err.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Recalculate Topology";
    }
}

/* ==========================================================
   INITIAL SEEDING
   ========================================================== */
async function checkInitialSeed() {
    if (allDocuments.length === 0) {
        const seedDocs = [
            {
                title: "Distributed Systems & Consensus Mechanics",
                category: "Architecture",
                tags: ["raft", "consensus", "distributed-systems", "fault-tolerance"],
                content: "Distributed consensus ensures multiple autonomous nodes agree on a single data value or state transition. Protocols like Paxos and Raft address leader election, log replication, and Byzantine fault handling under intermittent network partitions."
            },
            {
                title: "Vector Similarity & High-Dimensional Embeddings",
                category: "Research",
                tags: ["vectors", "embeddings", "information-retrieval", "machine-learning"],
                content: "Vector embeddings project natural language tokens into dense continuous vector spaces where cosine angle correlates with semantic meaning. Approximate nearest neighbor algorithms (HNSW, ScaNN) enable sub-millisecond retrieval across millions of chunked passages."
            },
            {
                title: "Event-Driven Microservices & Sagas",
                category: "Engineering",
                tags: ["microservices", "event-driven", "architecture", "distributed-systems"],
                content: "In distributed microservices architectures, data consistency across domain boundaries is maintained using asynchronous events and the Saga pattern. Choreographed and orchestrated sagas prevent distributed lock contention and manage compensating transactions."
            }
        ];

        for (const doc of seedDocs) {
            await fetch("/api/v1/documents", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(doc)
            });
        }
        await loadDocuments();
        await loadSystemStats();
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
