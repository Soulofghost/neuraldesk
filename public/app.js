let currentDocId = null;
let allDocuments = [];
let currentCategory = "ALL";

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    setupEventListeners();
    await loadDocuments();
    await checkInitialSeed();
}

function setupEventListeners() {
    // New Document
    document.getElementById("btn-new-doc").addEventListener("click", () => {
        resetEditor();
    });

    // Save Document
    document.getElementById("btn-save-doc").addEventListener("click", () => {
        saveDocument();
    });

    // Delete Document
    document.getElementById("btn-delete-doc").addEventListener("click", () => {
        if (currentDocId && confirm("Are you sure you want to delete this document?")) {
            deleteDocument(currentDocId);
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

    // Search Input
    const searchInput = document.getElementById("hybrid-search-input");
    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && searchInput.value.trim().length > 0) {
            executeHybridSearch(searchInput.value.trim());
        }
    });

    // Search Modal Close
    document.getElementById("btn-close-modal").addEventListener("click", () => {
        document.getElementById("search-modal").classList.remove("open");
    });

    document.getElementById("btn-refresh-graph").addEventListener("click", () => {
        renderKnowledgeGraph();
    });
}

async function loadDocuments() {
    try {
        const res = await fetch("/api/v1/documents");
        if (!res.ok) throw new Error("Failed to load documents");
        allDocuments = await res.json();
        renderDocumentList();
        document.getElementById("doc-count").textContent = allDocuments.length;
    } catch (err) {
        console.error("Error loading documents:", err);
    }
}

function renderDocumentList() {
    const list = document.getElementById("document-list");
    list.innerHTML = "";

    const filtered = currentCategory === "ALL" 
        ? allDocuments 
        : allDocuments.filter(d => d.category === currentCategory);

    if (filtered.length === 0) {
        list.innerHTML = `<div style="padding:12px; font-size:12px; color:var(--text-muted);">No documents in this category.</div>`;
        return;
    }

    filtered.forEach(doc => {
        const item = document.createElement("div");
        item.className = `doc-item ${doc.id === currentDocId ? 'active' : ''}`;
        item.innerHTML = `
            <div class="doc-item-title">${escapeHtml(doc.title)}</div>
            <div class="doc-item-meta">
                <span>[${doc.category}]</span>
                <span>• ${doc.chunk_count || 1} chunks</span>
            </div>
        `;
        item.addEventListener("click", () => {
            selectDocument(doc.id);
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

        document.getElementById("doc-title-input").value = doc.title;
        document.getElementById("doc-category-select").value = doc.category;
        document.getElementById("doc-tags-input").value = (doc.tags || []).join(", ");
        document.getElementById("doc-content-input").value = doc.content;
        document.getElementById("btn-delete-doc").style.display = "inline-block";

        renderTelemetryDrawer(doc);
        renderDocumentList();
    } catch (err) {
        console.error("Failed to select document:", err);
    }
}

function renderTelemetryDrawer(doc) {
    document.getElementById("chunk-info").textContent = `${doc.chunks.length} Chunks Generated`;
    const drawer = document.getElementById("drawer-content");
    drawer.innerHTML = "";

    // Show related graph connections
    if (doc.related && doc.related.length > 0) {
        const relDiv = document.createElement("div");
        relDiv.style.marginBottom = "8px";
        relDiv.innerHTML = `<div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">SEMANTIC RELATIONS & BACKLINKS:</div>`;
        doc.related.forEach(r => {
            const span = document.createElement("span");
            span.className = "related-chip";
            span.textContent = `↔ ${r.title} (${r.type}, score: ${r.weight})`;
            span.style.cursor = "pointer";
            span.addEventListener("click", () => selectDocument(r.id));
            relDiv.appendChild(span);
        });
        drawer.appendChild(relDiv);
    }

    // Show chunks
    doc.chunks.forEach(c => {
        const chunkBadge = document.createElement("div");
        chunkBadge.className = "chunk-badge";
        chunkBadge.innerHTML = `<strong>[Chunk #${c.index + 1}]</strong>: ${escapeHtml(c.content.substring(0, 160))}...`;
        drawer.appendChild(chunkBadge);
    });
}

function resetEditor() {
    currentDocId = null;
    document.getElementById("doc-title-input").value = "";
    document.getElementById("doc-category-select").value = "General";
    document.getElementById("doc-tags-input").value = "";
    document.getElementById("doc-content-input").value = "";
    document.getElementById("btn-delete-doc").style.display = "none";
    document.getElementById("chunk-info").textContent = "0 Chunks Generated";
    document.getElementById("drawer-content").innerHTML = `<div class="empty-state">New document draft. Enter content and save to index.</div>`;
    renderDocumentList();
}

async function saveDocument() {
    const title = document.getElementById("doc-title-input").value.trim();
    const content = document.getElementById("doc-content-input").value.trim();
    const category = document.getElementById("doc-category-select").value;
    const tagsRaw = document.getElementById("doc-tags-input").value;
    const tags = tagsRaw.split(",").map(t => t.trim()).filter(t => t.length > 0);

    if (!title || !content) {
        alert("Please provide both title and document content.");
        return;
    }

    const payload = { title, content, category, tags };

    try {
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

        if (!res.ok) throw new Error("Failed to save document");
        const saved = await res.json();
        currentDocId = saved.id;
        await loadDocuments();
        await selectDocument(saved.id);
    } catch (err) {
        console.error("Save error:", err);
        alert("Error saving document: " + err.message);
    }
}

async function deleteDocument(id) {
    try {
        const res = await fetch(`/api/v1/documents/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error("Failed to delete document");
        resetEditor();
        await loadDocuments();
    } catch (err) {
        console.error("Delete error:", err);
    }
}

async function executeHybridSearch(query) {
    try {
        const res = await fetch("/api/v1/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, limit: 6 })
        });
        if (!res.ok) throw new Error("Search failed");
        const results = await res.json();
        renderSearchResults(query, results);
    } catch (err) {
        console.error("Search query error:", err);
    }
}

function renderSearchResults(query, results) {
    const container = document.getElementById("search-results-list");
    container.innerHTML = "";

    if (results.length === 0) {
        container.innerHTML = `<div style="padding:20px; text-align:center; color:var(--text-muted);">No matching passages found for query "${escapeHtml(query)}".</div>`;
    } else {
        results.forEach(r => {
            const card = document.createElement("div");
            card.className = "result-card";
            card.innerHTML = `
                <div class="result-card-header">
                    <span style="font-weight:600; font-size:13px; color:var(--text-primary);">${escapeHtml(r.document_title)} [Chunk #${r.chunk_index + 1}]</span>
                    <span class="result-score">Hybrid Relevance: ${(r.score * 100).toFixed(1)}%</span>
                </div>
                <div class="result-snippet">${escapeHtml(r.content)}</div>
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

async function renderKnowledgeGraph() {
    const svg = document.getElementById("graph-svg");
    svg.innerHTML = "";

    try {
        const res = await fetch("/api/v1/graph");
        if (!res.ok) throw new Error("Failed to load graph");
        const { nodes, edges } = await res.json();

        if (nodes.length === 0) {
            svg.innerHTML = `<text x="50%" y="50%" fill="#6e7681" text-anchor="middle" font-size="13">No document nodes available. Add documents to generate knowledge graph.</text>`;
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
                line.setAttribute("stroke-width", Math.max(1, edge.weight * 3));
                line.setAttribute("stroke-opacity", "0.8");
                svg.appendChild(line);
            }
        });

        // Draw Nodes
        const colorMap = {
            "Architecture": "#388bfd",
            "Engineering": "#2ea043",
            "Research": "#a371f7",
            "General": "#e6a23c"
        };

        nodes.forEach(node => {
            const pos = nodePositions[node.id];
            const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
            g.style.cursor = "pointer";

            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", pos.x);
            circle.setAttribute("cy", pos.y);
            circle.setAttribute("r", 14);
            circle.setAttribute("fill", colorMap[node.category] || "#e6a23c");
            circle.setAttribute("stroke", "#161b22");
            circle.setAttribute("stroke-width", "3");

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
    }
}

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
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
