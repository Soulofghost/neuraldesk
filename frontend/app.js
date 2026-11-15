/**
 * NeuralDesk 2.0 — Production SaaS Client Engine
 * Full implementation of Dashboard, Multi-format Document Management,
 * AI Intelligence & Chat Assistant, Notes, Kanban Tasks, Knowledge Graph,
 * Analytics Telemetry, and Workspaces.
 */

// Application State
let currentDocId = null;
let allDocuments = [];
let currentCategory = "ALL";
let currentDocView = "active"; // "active", "favorites", "archive", "trash"
let activeWorkspaceId = 1;
let allWorkspaces = [];
let currentUser = null;
let activeChatSessionId = null;
let isSaving = false;
let isDirty = false;
let currentExtractedActions = [];

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    setupTheme();
    setupNavigationTabs();
    setupEventListeners();
    setupKeyboardShortcuts();
    setupDragAndDrop();
    await loadCurrentUser();
    await loadWorkspaces();
    await loadDocuments();
    await loadDashboardStats();
    await checkInitialSeed();
}

/* ==========================================================
   THEME MANAGER
   ========================================================== */
function setupTheme() {
    const savedTheme = localStorage.getItem("neuraldesk_theme");
    const toggleBtn = document.getElementById("btn-toggle-theme");
    if (savedTheme === "light") {
        document.body.classList.add("light-theme");
        if (toggleBtn) toggleBtn.textContent = "Switch to Obsidian Dark";
    }

    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            const isLight = document.body.classList.toggle("light-theme");
            localStorage.setItem("neuraldesk_theme", isLight ? "light" : "dark");
            toggleBtn.textContent = isLight ? "Switch to Obsidian Dark" : "Switch to Light Theme";
            showToast(`Theme switched to ${isLight ? 'Light' : 'Obsidian Dark'}.`, "info");
        });
    }
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
   AUTHENTICATION & USER PROFILE
   ========================================================== */
async function loadCurrentUser() {
    try {
        const res = await fetch("/api/v1/auth/me");
        if (res.ok) {
            currentUser = await res.json();
            const avatar = document.getElementById("sidebar-user-avatar");
            const name = document.getElementById("sidebar-user-name");
            const tierBadge = document.getElementById("sidebar-tier-badge");
            const emailField = document.getElementById("settings-user-email");
            const planSelect = document.getElementById("settings-user-plan");

            const initials = (currentUser.full_name || currentUser.email || "ND").substring(0, 2).toUpperCase();
            if (avatar) avatar.textContent = initials;
            if (name) name.textContent = currentUser.email;
            if (tierBadge) tierBadge.textContent = (currentUser.tier || "pro").toUpperCase();
            if (emailField) emailField.value = currentUser.email;
            if (planSelect) planSelect.value = currentUser.tier || "pro";
        }
    } catch (err) {
        console.warn("Could not fetch user profile:", err);
    }
}

/* ==========================================================
   WORKSPACE MANAGEMENT
   ========================================================== */
async function loadWorkspaces() {
    try {
        const res = await fetch("/api/v1/workspaces");
        if (res.ok) {
            allWorkspaces = await res.json();
            const select = document.getElementById("workspace-select");
            const noteDocSelect = document.getElementById("note-doc-link-select");
            const settingsWsName = document.getElementById("settings-ws-name");
            const settingsWsSlug = document.getElementById("settings-ws-slug");
            const analyticsWsId = document.getElementById("analytics-workspace-id");

            if (select) {
                select.innerHTML = "";
                allWorkspaces.forEach(ws => {
                    const opt = document.createElement("option");
                    opt.value = ws.id;
                    opt.textContent = `${ws.name} (${ws.document_count || 0} docs)`;
                    if (ws.id === activeWorkspaceId) opt.selected = true;
                    select.appendChild(opt);
                });
            }

            const active = allWorkspaces.find(w => w.id === activeWorkspaceId) || allWorkspaces[0];
            if (active) {
                activeWorkspaceId = active.id;
                if (settingsWsName) settingsWsName.value = active.name;
                if (settingsWsSlug) settingsWsSlug.value = active.slug;
                if (analyticsWsId) analyticsWsId.textContent = active.id;
            }
        }
    } catch (err) {
        console.error("Failed loading workspaces:", err);
    }
}

function switchWorkspace(id) {
    activeWorkspaceId = parseInt(id, 10);
    showToast(`Switched to workspace #${activeWorkspaceId}`, "info");
    resetEditor();
    loadDocuments();
    loadDashboardStats();
    loadNotes();
    loadTasks();
    loadChatConversations();
}

/* ==========================================================
   NAVIGATION TABS
   ========================================================== */
function setupNavigationTabs() {
    const tabs = [
        { btn: "tab-dashboard", pane: "dashboard-pane", onActive: loadDashboardStats, label: "Dashboard", isMore: false },
        { btn: "tab-doc", pane: "doc-pane", onActive: null, label: "Documents", isMore: false },
        { btn: "tab-chat", pane: "chat-pane", onActive: loadChatConversations, label: "AI Assistant", isMore: false },
        { btn: "tab-graph", pane: "graph-pane", onActive: renderKnowledgeGraph, label: "Graph", isMore: true },
        { btn: "tab-notes", pane: "notes-pane", onActive: loadNotes, label: "Notes", isMore: true },
        { btn: "tab-tasks", pane: "tasks-pane", onActive: loadTasks, label: "Tasks", isMore: true },
        { btn: "tab-analytics", pane: "analytics-pane", onActive: loadDashboardStats, label: "Analytics", isMore: true },
        { btn: "tab-settings", pane: "settings-pane", onActive: null, label: "Settings", isMore: true }
    ];

    const btnNavMore = document.getElementById("btn-nav-more");
    const navMoreMenu = document.getElementById("nav-more-menu");
    const navMoreLabel = document.getElementById("nav-more-label");

    tabs.forEach(t => {
        const btnElem = document.getElementById(t.btn);
        const paneElem = document.getElementById(t.pane);
        if (!btnElem || !paneElem) return;

        btnElem.addEventListener("click", () => {
            tabs.forEach(other => {
                const b = document.getElementById(other.btn);
                const p = document.getElementById(other.pane);
                if (b) b.classList.remove("active");
                if (p) p.classList.remove("active");
            });

            // Remove active from any dropdown items
            document.querySelectorAll(".nav-menu-item").forEach(item => item.classList.remove("active"));

            btnElem.classList.add("active");
            paneElem.classList.add("active");

            // Update More button state
            if (btnNavMore && navMoreLabel) {
                if (t.isMore) {
                    btnNavMore.classList.add("active");
                    navMoreLabel.textContent = t.label;
                } else {
                    btnNavMore.classList.remove("active");
                    navMoreLabel.textContent = "More";
                }
            }

            if (navMoreMenu) navMoreMenu.classList.remove("open");
            if (t.onActive) t.onActive();
        });
    });

    // Handle More dropdown toggle
    if (btnNavMore && navMoreMenu) {
        btnNavMore.addEventListener("click", (e) => {
            e.stopPropagation();
            navMoreMenu.classList.toggle("open");
        });

        // Close on outside click
        document.addEventListener("click", (e) => {
            if (!e.target.closest("#nav-more-dropdown")) {
                navMoreMenu.classList.remove("open");
            }
        });
    }

    // Handle compact menu item clicks (that forward to tab buttons)
    document.querySelectorAll(".tab-menu-item[data-tab-id]").forEach(item => {
        item.addEventListener("click", () => {
            const targetId = item.dataset.tabId;
            const targetBtn = document.getElementById(targetId);
            if (targetBtn) {
                targetBtn.click();
            }
        });
    });

    // Drawer collapse / expand toggle
    const btnToggleDrawer = document.getElementById("btn-toggle-drawer");
    const docDrawer = document.getElementById("doc-drawer");
    if (btnToggleDrawer && docDrawer) {
        btnToggleDrawer.addEventListener("click", () => {
            docDrawer.classList.toggle("collapsed");
        });
    }

    // Mobile Chat Sidebar toggle
    const btnToggleChatSidebar = document.getElementById("btn-toggle-chat-sidebar");
    const chatSidebar = document.getElementById("chat-sidebar");
    if (btnToggleChatSidebar && chatSidebar) {
        btnToggleChatSidebar.addEventListener("click", () => {
            chatSidebar.classList.toggle("mobile-open");
        });
    }

    // Dashboard Quick Actions
    const dashNewDoc = document.getElementById("dash-btn-new-doc");
    if (dashNewDoc) {
        dashNewDoc.addEventListener("click", () => {
            document.getElementById("tab-doc").click();
            resetEditor();
        });
    }

    const dashUpload = document.getElementById("dash-btn-upload");
    if (dashUpload) {
        dashUpload.addEventListener("click", () => {
            document.getElementById("file-upload-input").click();
        });
    }

    const dashChat = document.getElementById("dash-btn-open-chat");
    if (dashChat) {
        dashChat.addEventListener("click", () => {
            document.getElementById("tab-chat").click();
        });
    }
}

/* ==========================================================
   EVENT LISTENERS & NAVIGATION
   ========================================================== */
function setupEventListeners() {
    // Workspace dropdown
    const wsSelect = document.getElementById("workspace-select");
    if (wsSelect) {
        wsSelect.addEventListener("change", (e) => {
            switchWorkspace(e.target.value);
        });
    }

    // Create Workspace Modal
    const btnCreateWs = document.getElementById("btn-create-workspace");
    const wsModal = document.getElementById("workspace-modal");
    const closeWsModal = document.getElementById("btn-close-ws-modal");
    const submitWs = document.getElementById("btn-submit-new-ws");

    if (btnCreateWs) btnCreateWs.addEventListener("click", () => wsModal.classList.add("open"));
    if (closeWsModal) closeWsModal.addEventListener("click", () => wsModal.classList.remove("open"));
    if (submitWs) {
        submitWs.addEventListener("click", async () => {
            const name = document.getElementById("new-ws-name").value.trim();
            const desc = document.getElementById("new-ws-desc").value.trim();
            if (!name) {
                showToast("Please enter a workspace name", "error");
                return;
            }
            try {
                const res = await fetch("/api/v1/workspaces", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, description: desc })
                });
                if (res.ok) {
                    const created = await res.json();
                    showToast(`Workspace "${created.name}" created!`, "success");
                    wsModal.classList.remove("open");
                    document.getElementById("new-ws-name").value = "";
                    document.getElementById("new-ws-desc").value = "";
                    await loadWorkspaces();
                    switchWorkspace(created.id);
                } else {
                    showToast("Failed to create workspace", "error");
                }
            } catch (err) {
                showToast("Error creating workspace", "error");
            }
        });
    }

    // Document View Filters (Active, Favorites, Archive, Trash)
    const viewChips = document.querySelectorAll(".doc-view-filters .view-chip");
    viewChips.forEach(chip => {
        chip.addEventListener("click", () => {
            viewChips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            currentDocView = chip.dataset.view;
            loadDocuments();
        });
    });

    // New Document
    document.getElementById("btn-new-doc").addEventListener("click", () => {
        if (isDirty && !confirm("You have unsaved changes. Discard and create a new document?")) {
            return;
        }
        document.getElementById("tab-doc").click();
        resetEditor();
        closeMobileSidebar();
    });

    // Save Document
    document.getElementById("btn-save-doc").addEventListener("click", () => {
        saveDocument();
    });

    // Delete Document
    document.getElementById("btn-delete-doc").addEventListener("click", () => {
        if (currentDocId && confirm("Are you sure you want to delete this document? (Moves to Trash)")) {
            deleteDocument(currentDocId);
        }
    });

    // Restore Document
    const btnRestore = document.getElementById("btn-restore-doc");
    if (btnRestore) {
        btnRestore.addEventListener("click", () => {
            if (currentDocId) restoreDocument(currentDocId);
        });
    }

    // Favorite Document
    const btnFav = document.getElementById("btn-fav-doc");
    if (btnFav) {
        btnFav.addEventListener("click", () => {
            if (currentDocId) toggleFavoriteDocument(currentDocId);
        });
    }

    // AI Intelligence Modal
    const btnIntel = document.getElementById("btn-ai-intel");
    const intelModal = document.getElementById("ai-intel-modal");
    const closeIntel = document.getElementById("btn-close-intel-modal");
    if (btnIntel) {
        btnIntel.addEventListener("click", () => {
            if (currentDocId) triggerAiIntelligence(currentDocId);
            else showToast("Please select or save a document first.", "info");
        });
    }
    if (closeIntel) closeIntel.addEventListener("click", () => intelModal.classList.remove("open"));

    // Share Link Modal
    const btnShare = document.getElementById("btn-share-doc");
    const shareModal = document.getElementById("share-modal");
    const closeShare = document.getElementById("btn-close-share-modal");
    const btnCopyShare = document.getElementById("btn-copy-share-link");
    if (btnShare) {
        btnShare.addEventListener("click", () => {
            if (currentDocId) generateShareLink(currentDocId);
            else showToast("Please select or save a document first.", "info");
        });
    }
    if (closeShare) closeShare.addEventListener("click", () => shareModal.classList.remove("open"));
    if (btnCopyShare) {
        btnCopyShare.addEventListener("click", () => {
            const input = document.getElementById("share-link-input");
            input.select();
            navigator.clipboard.writeText(input.value);
            showToast("Share link copied to clipboard!", "success");
        });
    }

    // Export Document (.md)
    document.getElementById("btn-export-doc").addEventListener("click", () => {
        if (currentDocId) exportCurrentDocument();
    });

    // File Import / Upload (Multi-format)
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

    // Drawer Tabs (Vector Telemetry vs Comments)
    const tabTelemetry = document.getElementById("drawer-tab-telemetry");
    const tabComments = document.getElementById("drawer-tab-comments");
    const drawerTelemetry = document.getElementById("drawer-content");
    const drawerComments = document.getElementById("drawer-comments-pane");

    if (tabTelemetry && tabComments) {
        tabTelemetry.addEventListener("click", () => {
            tabTelemetry.classList.add("active");
            tabComments.classList.remove("active");
            drawerTelemetry.style.display = "block";
            drawerComments.style.display = "none";
        });

        tabComments.addEventListener("click", () => {
            tabComments.classList.add("active");
            tabTelemetry.classList.remove("active");
            drawerTelemetry.style.display = "none";
            drawerComments.style.display = "block";
            if (currentDocId) loadDocComments(currentDocId);
        });
    }

    // Submit Comment
    const btnComment = document.getElementById("btn-submit-comment");
    if (btnComment) {
        btnComment.addEventListener("click", submitComment);
    }
    const commentInput = document.getElementById("doc-comment-input");
    if (commentInput) {
        commentInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") submitComment();
        });
    }

    // Search Trigger (Enter or Search Icon)
    const searchInput = document.getElementById("hybrid-search-input");
    const searchIcon = document.getElementById("btn-trigger-search");

    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            const query = searchInput.value.trim();
            if (query.length > 0) executeHybridSearch(query);
            else showToast("Please enter a search query.", "info");
        }
    });

    searchIcon.addEventListener("click", () => {
        const query = searchInput.value.trim();
        if (query.length > 0) executeHybridSearch(query);
        else searchInput.focus();
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
        if (el) el.addEventListener("input", () => { isDirty = true; });
    });

    // Refresh Activity in Dashboard
    const btnRefreshActivity = document.getElementById("btn-refresh-activity");
    if (btnRefreshActivity) {
        btnRefreshActivity.addEventListener("click", loadDashboardStats);
    }

    // Plan Update in Settings
    const btnSavePlan = document.getElementById("btn-save-plan");
    if (btnSavePlan) {
        btnSavePlan.addEventListener("click", async () => {
            const plan = document.getElementById("settings-user-plan").value;
            try {
                const res = await fetch("/api/v1/auth/profile", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ full_name: currentUser ? currentUser.full_name : "User" })
                });
                showToast(`Subscription plan updated to ${plan.toUpperCase()}`, "success");
                const badge = document.getElementById("sidebar-tier-badge");
                if (badge) badge.textContent = plan.toUpperCase();
            } catch (err) {
                showToast("Failed to update plan", "error");
            }
        });
    }

    // AI Chat Assistant Events
    setupChatEvents();

    // Notes Events
    setupNotesEvents();

    // Tasks Events
    setupTasksEvents();
}

function closeMobileSidebar() {
    const sidebar = document.getElementById("app-sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("active");
}

function setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
        // Ctrl+S: Save document
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            saveDocument();
        }
        // Ctrl+K: Focus search
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            const searchInput = document.getElementById("hybrid-search-input");
            if (searchInput) searchInput.focus();
        }
        // Escape: Close all modals & mobile sidebar
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("open"));
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
   DASHBOARD & TELEMETRY
   ========================================================== */
async function loadDashboardStats() {
    try {
        const res = await fetch(`/api/v1/analytics/dashboard?workspace_id=${activeWorkspaceId}`);
        if (!res.ok) return;
        const data = await res.json();

        // System telemetry badge
        const statusLabel = document.getElementById("system-status-label");
        if (statusLabel) {
            statusLabel.textContent = `${data.database_engine || 'SQLite'} • ${data.total_documents} Docs • ${data.total_chunks} Chunks`;
        }

        // Dashboard Stat Cards
        const dashDocs = document.getElementById("dash-total-docs");
        const dashActiveDocs = document.getElementById("dash-active-docs");
        const dashChunks = document.getElementById("dash-total-chunks");
        const dashNotes = document.getElementById("dash-total-notes");
        const dashPinnedNotes = document.getElementById("dash-pinned-notes");
        const dashTasks = document.getElementById("dash-total-tasks");
        const dashPendingTasks = document.getElementById("dash-pending-tasks");
        const dashStorage = document.getElementById("dash-storage-used");
        const dashQuota = document.getElementById("dash-storage-quota");

        if (dashDocs) dashDocs.textContent = data.total_documents || 0;
        if (dashActiveDocs) dashActiveDocs.textContent = `${data.active_documents || data.total_documents || 0} Active`;
        if (dashChunks) dashChunks.textContent = data.total_chunks || 0;
        if (dashNotes) dashNotes.textContent = data.total_notes || 0;
        if (dashPinnedNotes) dashPinnedNotes.textContent = `${data.pinned_notes || 0} Pinned`;
        if (dashTasks) dashTasks.textContent = data.total_tasks || 0;
        if (dashPendingTasks) dashPendingTasks.textContent = `${data.pending_tasks || 0} Pending`;
        if (dashStorage) dashStorage.textContent = `${data.storage_used_kb || 0} KB`;
        if (dashQuota) dashQuota.textContent = `of ${data.storage_quota_mb || 500} MB quota`;

        // Category breakdown
        const catBox = document.getElementById("dash-category-distribution");
        if (catBox) {
            catBox.innerHTML = "";
            const cats = data.category_distribution || {};
            const total = Math.max(1, data.total_documents || 1);
            const colorMap = {
                "Architecture": "var(--accent-blue)",
                "Engineering": "var(--accent-green)",
                "Research": "var(--accent-purple)",
                "General": "var(--accent-amber)"
            };

            const entries = Object.keys(cats).length > 0 ? Object.entries(cats) : [["Architecture", 1], ["Engineering", 1], ["Research", 1], ["General", 0]];
            entries.forEach(([cat, count]) => {
                const pct = Math.round((count / total) * 100);
                const row = document.createElement("div");
                row.style.marginBottom = "10px";
                row.innerHTML = `
                    <div class="distribution-row">
                        <span><strong>${escapeHtml(cat)}</strong></span>
                        <span style="color:var(--text-secondary); font-family:var(--font-mono);">${count} docs (${pct}%)</span>
                    </div>
                    <div class="distribution-bar">
                        <div class="distribution-bar-inner" style="width: ${pct}%; background: ${colorMap[cat] || 'var(--accent-amber)'};"></div>
                    </div>
                `;
                catBox.appendChild(row);
            });
        }

        // Format breakdown
        const formatBox = document.getElementById("dash-format-distribution");
        if (formatBox) {
            formatBox.innerHTML = "";
            const formats = data.file_type_distribution || { "markdown": data.total_documents || 3 };
            const total = Math.max(1, data.total_documents || 1);
            Object.entries(formats).forEach(([fmt, count]) => {
                const pct = Math.round((count / total) * 100);
                const row = document.createElement("div");
                row.style.marginBottom = "10px";
                row.innerHTML = `
                    <div class="distribution-row">
                        <span style="font-family:var(--font-mono); text-transform:uppercase;">.${escapeHtml(fmt)}</span>
                        <span style="color:var(--text-secondary);">${count} files (${pct}%)</span>
                    </div>
                    <div class="distribution-bar">
                        <div class="distribution-bar-inner" style="width: ${pct}%; background: var(--accent-amber);"></div>
                    </div>
                `;
                formatBox.appendChild(row);
            });
        }

        // Activity timeline
        const activityList = document.getElementById("dash-activity-list");
        if (activityList) {
            activityList.innerHTML = "";
            const activities = data.recent_activities || [];
            if (activities.length === 0) {
                activityList.innerHTML = `<div style="font-size:12px; color:var(--text-muted); padding:8px 0;">No recorded activity yet. Actions and document modifications will be logged here.</div>`;
            } else {
                activities.forEach(act => {
                    const item = document.createElement("div");
                    item.className = "activity-item";
                    let badgeClass = "badge-create";
                    if (act.action.includes("UPDATE")) badgeClass = "badge-update";
                    if (act.action.includes("DELETE") || act.action.includes("TRASH")) badgeClass = "badge-delete";
                    if (act.action.includes("AI") || act.action.includes("SUMMARIZE")) badgeClass = "badge-ai";
                    if (act.action.includes("SHARE")) badgeClass = "badge-share";

                    const timeStr = act.created_at ? new Date(act.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Just now";

                    item.innerHTML = `
                        <span class="activity-badge ${badgeClass}">${escapeHtml(act.action)}</span>
                        <span class="activity-desc">${escapeHtml(act.details || act.entity_type)}</span>
                        <span class="activity-time">${timeStr}</span>
                    `;
                    activityList.appendChild(item);
                });
            }
        }

        // Analytics Pane values
        const storageVal = document.getElementById("analytics-storage-val");
        const storageFill = document.getElementById("storage-bar-fill");
        const avgChunks = document.getElementById("analytics-avg-chunks");
        const dbEngine = document.getElementById("analytics-db-engine");

        if (storageVal) storageVal.textContent = `${data.storage_used_kb || 0} KB`;
        if (storageFill) {
            const pct = Math.min(100, Math.max(1, ((data.storage_used_kb || 1) / (500 * 1024)) * 100));
            storageFill.style.width = `${pct}%`;
        }
        if (avgChunks) avgChunks.textContent = data.average_chunks_per_doc || 0;
        if (dbEngine) dbEngine.textContent = data.database_engine || "SQLite / PostgreSQL";

    } catch (err) {
        console.warn("Dashboard stats error:", err);
    }
}

/* ==========================================================
   DOCUMENT MANAGEMENT (CRUD & MULTI-FORMAT)
   ========================================================== */
async function loadDocuments() {
    try {
        const res = await fetch(`/api/v1/documents?workspace_id=${activeWorkspaceId}&view=${currentDocView}`);
        if (!res.ok) throw new Error("Failed to load documents");
        allDocuments = await res.json();
        renderDocumentList();
        const docCountElem = document.getElementById("doc-count");
        if (docCountElem) docCountElem.textContent = allDocuments.length;
    } catch (err) {
        console.error("Error loading documents:", err);
        showToast("Failed to load documents from database.", "error");
    }
}

function renderDocumentList() {
    const list = document.getElementById("document-list");
    if (!list) return;
    list.innerHTML = "";

    const filtered = currentCategory === "ALL" 
        ? allDocuments 
        : allDocuments.filter(d => d.category === currentCategory);

    if (filtered.length === 0) {
        list.innerHTML = `
            <div style="padding:16px; text-align:center; font-size:12px; color:var(--text-muted);">
                No documents found in this view.<br>
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
        
        const favStar = doc.is_favorite ? `<span style="color:var(--accent-amber); margin-right:4px;">★</span>` : '';
        const trashBadge = doc.is_trash ? `<span style="color:var(--accent-red); font-size:10px; margin-left:4px;">[TRASH]</span>` : '';

        item.innerHTML = `
            <div class="doc-item-title">${favStar}${escapeHtml(doc.title)}${trashBadge}</div>
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
        
        // Buttons visibility
        const delBtn = document.getElementById("btn-delete-doc");
        const expBtn = document.getElementById("btn-export-doc");
        const resBtn = document.getElementById("btn-restore-doc");
        const favBtn = document.getElementById("btn-fav-doc");

        if (delBtn) delBtn.style.display = doc.is_trash ? "none" : "inline-block";
        if (expBtn) expBtn.style.display = "inline-block";
        if (resBtn) resBtn.style.display = doc.is_trash ? "inline-block" : "none";
        if (favBtn) favBtn.style.color = doc.is_favorite ? "var(--accent-amber)" : "var(--text-secondary)";

        renderTelemetryDrawer(doc);
        renderDocumentList();
    } catch (err) {
        console.error("Failed to select document:", err);
        showToast("Error retrieving document details.", "error");
    }
}

function renderTelemetryDrawer(doc) {
    const chunkCount = (doc.chunks && doc.chunks.length) || 0;
    const chunkInfo = document.getElementById("chunk-info");
    if (chunkInfo) chunkInfo.textContent = `${chunkCount} Chunks Generated`;
    const drawer = document.getElementById("drawer-content");
    if (!drawer) return;
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
    
    const delBtn = document.getElementById("btn-delete-doc");
    const expBtn = document.getElementById("btn-export-doc");
    const resBtn = document.getElementById("btn-restore-doc");
    const favBtn = document.getElementById("btn-fav-doc");

    if (delBtn) delBtn.style.display = "none";
    if (expBtn) expBtn.style.display = "none";
    if (resBtn) resBtn.style.display = "none";
    if (favBtn) favBtn.style.color = "var(--text-secondary)";

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

    const payload = { title, content, category, tags, workspace_id: activeWorkspaceId };
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
        await loadDashboardStats();
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
    if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.textContent = "Deleting...";
    }

    try {
        const res = await fetch(`/api/v1/documents/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error("Failed to delete document");
        
        showToast("Document moved to Trash.", "success");
        resetEditor();
        await loadDocuments();
        await loadDashboardStats();
    } catch (err) {
        console.error("Delete error:", err);
        showToast("Error deleting document: " + err.message, "error");
    } finally {
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = "Delete";
        }
    }
}

async function restoreDocument(id) {
    try {
        const res = await fetch(`/api/v1/documents/${id}/restore`, { method: "POST" });
        if (!res.ok) throw new Error("Failed to restore document");
        showToast("Document restored from Trash.", "success");
        await loadDocuments();
        await selectDocument(id);
    } catch (err) {
        showToast("Error restoring document: " + err.message, "error");
    }
}

async function toggleFavoriteDocument(id) {
    try {
        const res = await fetch(`/api/v1/documents/${id}/favorite`, { method: "POST" });
        if (res.ok) {
            const doc = await res.json();
            showToast(doc.is_favorite ? "Added to favorites ⭐" : "Removed from favorites", "info");
            const favBtn = document.getElementById("btn-fav-doc");
            if (favBtn) favBtn.style.color = doc.is_favorite ? "var(--accent-amber)" : "var(--text-secondary)";
            await loadDocuments();
        }
    } catch (err) {
        showToast("Failed to toggle favorite", "error");
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
    formData.append("workspace_id", activeWorkspaceId);

    const uploadBtn = document.getElementById("btn-upload-doc");
    const originalText = uploadBtn.innerHTML;

    try {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = `<span>Uploading & Parsing...</span>`;

        const res = await fetch("/api/v1/documents/upload", {
            method: "POST",
            body: formData
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to import document");
        }

        const saved = await res.json();
        showToast(`Imported "${saved.title}" successfully! (${saved.chunk_count} chunks)`, "success");
        await loadDocuments();
        await selectDocument(saved.id);
        await loadDashboardStats();
    } catch (err) {
        console.error("Import error:", err);
        showToast("Import failed: " + err.message, "error");
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalText;
    }
}

/* ==========================================================
   DOCUMENT COMMENTS & DISCUSSIONS
   ========================================================== */
async function loadDocComments(docId) {
    const list = document.getElementById("doc-comments-list");
    if (!list) return;
    list.innerHTML = "";

    try {
        const res = await fetch(`/api/v1/collaboration/documents/${docId}/comments`);
        if (res.ok) {
            const comments = await res.json();
            if (comments.length === 0) {
                list.innerHTML = `<div style="font-size:11px; color:var(--text-muted); padding:6px 0;">No comments on this document yet. Start a discussion!</div>`;
                return;
            }
            comments.forEach(c => {
                const card = document.createElement("div");
                card.className = "comment-card";
                card.innerHTML = `
                    <div class="comment-header">
                        <span style="font-weight:600; color:var(--text-primary);">${escapeHtml(c.user_email || 'Teammate')}</span>
                        <span>${new Date(c.created_at).toLocaleDateString()}</span>
                    </div>
                    <div>${escapeHtml(c.content)}</div>
                `;
                list.appendChild(card);
            });
        }
    } catch (err) {
        console.error("Failed loading comments:", err);
    }
}

async function submitComment() {
    if (!currentDocId) {
        showToast("Please select a document first", "info");
        return;
    }
    const input = document.getElementById("doc-comment-input");
    const content = input.value.trim();
    if (!content) return;

    try {
        const res = await fetch(`/api/v1/collaboration/documents/${currentDocId}/comments`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content })
        });
        if (res.ok) {
            input.value = "";
            showToast("Comment posted!", "success");
            loadDocComments(currentDocId);
        }
    } catch (err) {
        showToast("Failed to post comment", "error");
    }
}

/* ==========================================================
   SHARING & PERMANENT LINKS
   ========================================================== */
async function generateShareLink(docId) {
    const modal = document.getElementById("share-modal");
    const input = document.getElementById("share-link-input");

    try {
        const res = await fetch(`/api/v1/collaboration/documents/${docId}/share`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ access_type: "public_read" })
        });
        if (res.ok) {
            const link = await res.json();
            const shareUrl = `${window.location.origin}/share/${link.token}`;
            input.value = shareUrl;
            modal.classList.add("open");
        } else {
            showToast("Failed to generate share link", "error");
        }
    } catch (err) {
        showToast("Error generating share link", "error");
    }
}

/* ==========================================================
   AI DOCUMENT INTELLIGENCE
   ========================================================== */
async function triggerAiIntelligence(docId) {
    const modal = document.getElementById("ai-intel-modal");
    const summaryText = document.getElementById("intel-summary-text");
    const takeawaysList = document.getElementById("intel-takeaways-list");
    const entitiesBox = document.getElementById("intel-entities-chips");
    const actionsList = document.getElementById("intel-actions-list");

    summaryText.textContent = "Analyzing document content with extractive salience model...";
    takeawaysList.innerHTML = "<li>Extracting key propositions...</li>";
    entitiesBox.innerHTML = "<span class='intel-chip'>Scanning entities...</span>";
    actionsList.innerHTML = "<li>Searching for deliverables and milestones...</li>";
    modal.classList.add("open");

    try {
        // Parallel requests for summary, entities, action-items
        const [sumRes, entRes, actRes] = await Promise.all([
            fetch("/api/v1/intelligence/summarize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ document_id: docId, max_sentences: 3 })
            }),
            fetch("/api/v1/intelligence/entities", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ document_id: docId })
            }),
            fetch("/api/v1/intelligence/action-items", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ document_id: docId })
            })
        ]);

        if (sumRes.ok) {
            const data = await sumRes.json();
            summaryText.textContent = data.summary;
            takeawaysList.innerHTML = "";
            (data.key_takeaways || []).forEach(tk => {
                const li = document.createElement("li");
                li.textContent = tk;
                takeawaysList.appendChild(li);
            });
        }

        if (entRes.ok) {
            const data = await entRes.json();
            entitiesBox.innerHTML = "";
            (data.entities || []).forEach(e => {
                const chip = document.createElement("span");
                chip.className = "intel-chip";
                chip.textContent = `${e.name} (${e.type})`;
                entitiesBox.appendChild(chip);
            });
        }

        if (actRes.ok) {
            const data = await actRes.json();
            currentExtractedActions = data.action_items || [];
            actionsList.innerHTML = "";
            if (currentExtractedActions.length === 0) {
                actionsList.innerHTML = `<li>No explicit action items found in this document.</li>`;
            } else {
                currentExtractedActions.forEach(a => {
                    const li = document.createElement("li");
                    li.textContent = `${a.item} [Priority: ${a.priority.toUpperCase()}]`;
                    actionsList.appendChild(li);
                });
            }
        }

        // Convert to Tasks button
        const convertBtn = document.getElementById("btn-convert-intel-tasks");
        if (convertBtn) {
            convertBtn.onclick = async () => {
                if (currentExtractedActions.length === 0) {
                    showToast("No action items to convert", "info");
                    return;
                }
                for (const act of currentExtractedActions) {
                    await fetch("/api/v1/tasks", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            title: act.item,
                            priority: act.priority || "medium",
                            document_id: docId,
                            workspace_id: activeWorkspaceId
                        })
                    });
                }
                showToast(`Converted ${currentExtractedActions.length} items into tasks!`, "success");
                modal.classList.remove("open");
                loadTasks();
            };
        }

    } catch (err) {
        console.error("AI intelligence error:", err);
        showToast("Error processing AI document intelligence: " + err.message, "error");
    }
}

/* ==========================================================
   AI CONVERSATIONAL ASSISTANT
   ========================================================== */
function setupChatEvents() {
    const btnNewChat = document.getElementById("btn-new-chat");
    const btnSend = document.getElementById("btn-send-chat");
    const queryInput = document.getElementById("chat-query-input");

    if (btnNewChat) {
        btnNewChat.addEventListener("click", () => createNewChatSession());
    }

    if (btnSend && queryInput) {
        btnSend.addEventListener("click", () => sendChatMessage());
        queryInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }

    // Prompt Chips
    const promptChips = document.querySelectorAll(".prompt-chip");
    promptChips.forEach(chip => {
        chip.addEventListener("click", () => {
            if (queryInput) {
                queryInput.value = chip.dataset.prompt;
                sendChatMessage();
            }
        });
    });
}

async function loadChatConversations() {
    const list = document.getElementById("chat-conversation-list");
    if (!list) return;
    list.innerHTML = "";

    try {
        const res = await fetch(`/api/v1/chat/conversations?workspace_id=${activeWorkspaceId}`);
        if (res.ok) {
            const convs = await res.json();
            if (convs.length === 0) {
                // Auto create initial conversation
                await createNewChatSession();
                return;
            }

            convs.forEach(c => {
                const item = document.createElement("div");
                item.className = `chat-session-item ${c.id === activeChatSessionId ? 'active' : ''}`;
                item.innerHTML = `<span>${escapeHtml(c.title)}</span>`;
                item.addEventListener("click", () => selectChatSession(c.id, c.title));
                list.appendChild(item);
            });

            if (!activeChatSessionId && convs.length > 0) {
                selectChatSession(convs[0].id, convs[0].title);
            }
        }
    } catch (err) {
        console.error("Failed loading chat sessions:", err);
    }
}

async function createNewChatSession() {
    try {
        const res = await fetch("/api/v1/chat/conversations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title: "Research Chat",
                workspace_id: activeWorkspaceId
            })
        });
        if (res.ok) {
            const conv = await res.json();
            activeChatSessionId = conv.id;
            await loadChatConversations();
            selectChatSession(conv.id, conv.title);
        }
    } catch (err) {
        showToast("Error starting chat session", "error");
    }
}

async function selectChatSession(id, title) {
    activeChatSessionId = id;
    const activeTitle = document.getElementById("chat-active-title");
    if (activeTitle) activeTitle.textContent = title;

    // Highlight active session item
    document.querySelectorAll(".chat-session-item").forEach(item => item.classList.remove("active"));
    const list = document.getElementById("chat-conversation-list");
    if (list) {
        Array.from(list.children).forEach(el => {
            if (el.textContent.trim() === title) el.classList.add("active");
        });
    }

    const messagesBox = document.getElementById("chat-messages-container");
    messagesBox.innerHTML = "";

    try {
        const res = await fetch(`/api/v1/chat/conversations/${id}/messages`);
        if (res.ok) {
            const msgs = await res.json();
            if (msgs.length === 0) {
                messagesBox.innerHTML = `
                    <div class="chat-message assistant">
                        <div class="message-avatar">ND</div>
                        <div class="message-content">
                            <p>Hello! I am your <strong>NeuralDesk AI Assistant</strong>. Ask me anything about your documents, architecture notes, or research papers. All answers are grounded with vector citations directly from your workspace.</p>
                        </div>
                    </div>
                `;
            } else {
                msgs.forEach(m => renderChatMessage(m.role, m.content, m.citations));
            }
        }
    } catch (err) {
        console.error("Failed loading messages:", err);
    }
}

function renderChatMessage(role, content, citations = []) {
    const box = document.getElementById("chat-messages-container");
    if (!box) return;

    const msg = document.createElement("div");
    msg.className = `chat-message ${role}`;

    const avatarText = role === "user" ? (currentUser ? currentUser.email.substring(0,2).toUpperCase() : "ME") : "ND";

    let citationsHtml = "";
    if (citations && citations.length > 0) {
        citationsHtml = `<div style="margin-top:8px;">` + citations.map(c => 
            `<span class="citation-tag" title="${escapeHtml(c.snippet)}">📄 ${escapeHtml(c.title)} [Chunk #${c.chunk_index + 1}]</span>`
        ).join("") + `</div>`;
    }

    msg.innerHTML = `
        <div class="message-avatar">${avatarText}</div>
        <div class="message-content">
            <div>${escapeHtml(content).replace(/\n/g, '<br>')}</div>
            ${citationsHtml}
        </div>
    `;

    box.appendChild(msg);
    box.scrollTop = box.scrollHeight;
}

async function sendChatMessage() {
    const input = document.getElementById("chat-query-input");
    const query = input.value.trim();
    if (!query) return;

    if (!activeChatSessionId) {
        await createNewChatSession();
    }

    const scope = document.getElementById("chat-scope-select").value;
    const docId = (scope === "document" && currentDocId) ? currentDocId : null;

    input.value = "";
    renderChatMessage("user", query);

    // Show typing state
    const box = document.getElementById("chat-messages-container");
    const typingMsg = document.createElement("div");
    typingMsg.className = "chat-message assistant typing-indicator";
    typingMsg.innerHTML = `
        <div class="message-avatar">ND</div>
        <div class="message-content"><p style="font-style:italic; color:var(--text-muted);">Retrieving semantic chunks and synthesizing answer...</p></div>
    `;
    box.appendChild(typingMsg);
    box.scrollTop = box.scrollHeight;

    try {
        const res = await fetch(`/api/v1/chat/conversations/${activeChatSessionId}/messages`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt: query,
                document_id: docId,
                workspace_id: activeWorkspaceId
            })
        });

        typingMsg.remove();

        if (res.ok) {
            const data = await res.json();
            renderChatMessage("assistant", data.content, data.citations);
        } else {
            renderChatMessage("assistant", "Sorry, I encountered an error while synthesizing the answer. Please try again.");
        }
    } catch (err) {
        typingMsg.remove();
        renderChatMessage("assistant", "Error connecting to AI assistant: " + err.message);
    }
}

/* ==========================================================
   NOTES MODULE
   ========================================================== */
function setupNotesEvents() {
    const btnCreateNote = document.getElementById("btn-create-note");
    const noteModal = document.getElementById("note-modal");
    const closeNoteModal = document.getElementById("btn-close-note-modal");
    const submitNote = document.getElementById("btn-submit-note");
    const searchNotes = document.getElementById("notes-search-input");

    if (btnCreateNote) {
        btnCreateNote.addEventListener("click", () => {
            openNoteModal();
        });
    }

    if (closeNoteModal) {
        closeNoteModal.addEventListener("click", () => noteModal.classList.remove("open"));
    }

    if (submitNote) {
        submitNote.addEventListener("click", saveNoteFromModal);
    }

    if (searchNotes) {
        searchNotes.addEventListener("input", (e) => {
            filterNotes(e.target.value.trim().toLowerCase());
        });
    }
}

let cachedNotes = [];
let editingNoteId = null;

async function loadNotes() {
    const grid = document.getElementById("notes-grid");
    if (!grid) return;
    grid.innerHTML = "";

    try {
        const res = await fetch(`/api/v1/notes?workspace_id=${activeWorkspaceId}`);
        if (res.ok) {
            cachedNotes = await res.json();
            renderNotesGrid(cachedNotes);
        }
    } catch (err) {
        console.error("Failed loading notes:", err);
    }
}

function renderNotesGrid(notes) {
    const grid = document.getElementById("notes-grid");
    if (!grid) return;
    grid.innerHTML = "";

    if (notes.length === 0) {
        grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:32px; color:var(--text-muted);">No notes found in this workspace. Click "+ New Note" to capture your ideas.</div>`;
        return;
    }

    notes.forEach(note => {
        const card = document.createElement("div");
        card.className = `note-card ${note.is_pinned ? 'pinned' : ''}`;

        const tagsHtml = (note.tags || []).map(t => `<span class="note-tag">#${escapeHtml(t)}</span>`).join("");
        const linkedDoc = allDocuments.find(d => d.id === note.document_id);
        const linkHtml = linkedDoc 
            ? `<span class="note-link-pill" title="Click to view linked document">🔗 ${escapeHtml(linkedDoc.title)}</span>` 
            : '';

        card.innerHTML = `
            <div class="note-card-header">
                <span class="note-title">${escapeHtml(note.title)}</span>
                <span class="note-pinned-btn" style="cursor:pointer; color:${note.is_pinned ? 'var(--accent-amber)' : 'var(--text-muted)'};" title="Toggle pin">📌</span>
            </div>
            <div class="note-card-body">${escapeHtml(note.content)}</div>
            ${tagsHtml ? `<div class="note-tags-list">${tagsHtml}</div>` : ''}
            <div class="note-card-footer">
                <div>${linkHtml}</div>
                <div class="note-actions">
                    <button class="btn-subtle btn-sm btn-edit-note">Edit</button>
                    <button class="btn-subtle btn-sm btn-delete-note" style="color:var(--accent-red);">Del</button>
                </div>
            </div>
        `;

        // Toggle pin
        card.querySelector(".note-pinned-btn").addEventListener("click", async () => {
            await fetch(`/api/v1/notes/${note.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_pinned: !note.is_pinned })
            });
            loadNotes();
        });

        // Edit note
        card.querySelector(".btn-edit-note").addEventListener("click", () => {
            openNoteModal(note);
        });

        // Delete note
        card.querySelector(".btn-delete-note").addEventListener("click", async () => {
            if (confirm("Delete this note?")) {
                await fetch(`/api/v1/notes/${note.id}`, { method: "DELETE" });
                showToast("Note deleted", "success");
                loadNotes();
            }
        });

        // Linked document click
        if (linkedDoc) {
            const pill = card.querySelector(".note-link-pill");
            if (pill) {
                pill.addEventListener("click", () => {
                    document.getElementById("tab-doc").click();
                    selectDocument(linkedDoc.id);
                });
            }
        }

        grid.appendChild(card);
    });
}

function filterNotes(query) {
    if (!query) {
        renderNotesGrid(cachedNotes);
        return;
    }
    const filtered = cachedNotes.filter(n => 
        n.title.toLowerCase().includes(query) || 
        n.content.toLowerCase().includes(query) ||
        (n.tags && n.tags.some(t => t.toLowerCase().includes(query)))
    );
    renderNotesGrid(filtered);
}

function openNoteModal(existingNote = null) {
    const modal = document.getElementById("note-modal");
    const titleInput = document.getElementById("note-title-input");
    const contentInput = document.getElementById("note-content-input");
    const tagsInput = document.getElementById("note-tags-input");
    const docSelect = document.getElementById("note-doc-link-select");
    const modalTitle = document.getElementById("note-modal-title");

    // Populate doc dropdown
    docSelect.innerHTML = `<option value="">-- No Linked Document --</option>`;
    allDocuments.forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.id;
        opt.textContent = d.title;
        docSelect.appendChild(opt);
    });

    if (existingNote) {
        editingNoteId = existingNote.id;
        modalTitle.textContent = "Edit Note";
        titleInput.value = existingNote.title;
        contentInput.value = existingNote.content;
        tagsInput.value = (existingNote.tags || []).join(", ");
        docSelect.value = existingNote.document_id || "";
    } else {
        editingNoteId = null;
        modalTitle.textContent = "Create Knowledge Note";
        titleInput.value = "";
        contentInput.value = "";
        tagsInput.value = "";
        docSelect.value = currentDocId || "";
    }

    modal.classList.add("open");
}

async function saveNoteFromModal() {
    const title = document.getElementById("note-title-input").value.trim();
    const content = document.getElementById("note-content-input").value.trim();
    const tagsRaw = document.getElementById("note-tags-input").value;
    const docIdRaw = document.getElementById("note-doc-link-select").value;

    if (!title || !content) {
        showToast("Please enter title and content", "error");
        return;
    }

    const tags = tagsRaw.split(",").map(t => t.trim()).filter(t => t.length > 0);
    const docId = docIdRaw ? parseInt(docIdRaw, 10) : null;

    try {
        if (editingNoteId) {
            await fetch(`/api/v1/notes/${editingNoteId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, content, tags, document_id: docId })
            });
            showToast("Note updated!", "success");
        } else {
            await fetch("/api/v1/notes", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title,
                    content,
                    tags,
                    document_id: docId,
                    workspace_id: activeWorkspaceId
                })
            });
            showToast("Note created!", "success");
        }
        document.getElementById("note-modal").classList.remove("open");
        loadNotes();
    } catch (err) {
        showToast("Error saving note", "error");
    }
}

/* ==========================================================
   TASKS KANBAN MODULE
   ========================================================== */
function setupTasksEvents() {
    const btnCreate = document.getElementById("btn-create-task");
    const taskModal = document.getElementById("task-modal");
    const closeTask = document.getElementById("btn-close-task-modal");
    const submitTask = document.getElementById("btn-submit-task");
    const btnAutoExtract = document.getElementById("btn-auto-extract-tasks");

    if (btnCreate) {
        btnCreate.addEventListener("click", () => {
            document.getElementById("task-title-input").value = "";
            document.getElementById("task-desc-input").value = "";
            document.getElementById("task-due-date").value = "";
            taskModal.classList.add("open");
        });
    }

    if (closeTask) closeTask.addEventListener("click", () => taskModal.classList.remove("open"));

    if (submitTask) {
        submitTask.addEventListener("click", async () => {
            const title = document.getElementById("task-title-input").value.trim();
            const desc = document.getElementById("task-desc-input").value.trim();
            const priority = document.getElementById("task-priority-select").value;
            const status = document.getElementById("task-status-select").value;
            const dueDate = document.getElementById("task-due-date").value || null;

            if (!title) {
                showToast("Please provide a task title", "error");
                return;
            }

            try {
                await fetch("/api/v1/tasks", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        title,
                        description: desc,
                        priority,
                        status,
                        due_date: dueDate,
                        document_id: currentDocId,
                        workspace_id: activeWorkspaceId
                    })
                });
                showToast("Task created!", "success");
                taskModal.classList.remove("open");
                loadTasks();
            } catch (err) {
                showToast("Error creating task", "error");
            }
        });
    }

    if (btnAutoExtract) {
        btnAutoExtract.addEventListener("click", async () => {
            if (!currentDocId) {
                showToast("Please select a document first.", "info");
                return;
            }
            try {
                showToast("Extracting tasks from document...", "info");
                const res = await fetch(`/api/v1/tasks/extract-from-doc/${currentDocId}`, { method: "POST" });
                if (res.ok) {
                    const tasks = await res.json();
                    showToast(`Extracted and created ${tasks.length} tasks!`, "success");
                    loadTasks();
                } else {
                    showToast("No action items found in document", "info");
                }
            } catch (err) {
                showToast("Failed to extract tasks", "error");
            }
        });
    }
}

async function loadTasks() {
    const listTodo = document.getElementById("tasks-list-todo");
    const listInProgress = document.getElementById("tasks-list-in-progress");
    const listDone = document.getElementById("tasks-list-done");

    if (!listTodo || !listInProgress || !listDone) return;
    listTodo.innerHTML = "";
    listInProgress.innerHTML = "";
    listDone.innerHTML = "";

    try {
        const res = await fetch(`/api/v1/tasks?workspace_id=${activeWorkspaceId}`);
        if (res.ok) {
            const tasks = await res.json();
            let countTodo = 0, countProg = 0, countDone = 0;

            tasks.forEach(t => {
                const card = document.createElement("div");
                card.className = "task-card";

                const nextStatusMap = {
                    "todo": "in_progress",
                    "in_progress": "done",
                    "done": "todo"
                };

                const nextStatusLabel = {
                    "todo": "→ Start",
                    "in_progress": "✔ Complete",
                    "done": "↺ Reopen"
                };

                card.innerHTML = `
                    <div class="task-card-title">${escapeHtml(t.title)}</div>
                    ${t.description ? `<div class="task-card-desc">${escapeHtml(t.description)}</div>` : ''}
                    <div class="task-card-meta">
                        <span class="task-priority-badge priority-${t.priority}">${escapeHtml(t.priority)}</span>
                        <div style="display:flex; gap:6px;">
                            <button class="btn-subtle btn-sm btn-status-toggle">${nextStatusLabel[t.status] || 'Move'}</button>
                            <button class="btn-subtle btn-sm btn-delete-task" style="color:var(--accent-red);">✕</button>
                        </div>
                    </div>
                `;

                // Status toggle
                card.querySelector(".btn-status-toggle").addEventListener("click", async () => {
                    await fetch(`/api/v1/tasks/${t.id}/status`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ status: nextStatusMap[t.status] })
                    });
                    loadTasks();
                });

                // Delete task
                card.querySelector(".btn-delete-task").addEventListener("click", async () => {
                    await fetch(`/api/v1/tasks/${t.id}`, { method: "DELETE" });
                    loadTasks();
                });

                if (t.status === "todo") {
                    listTodo.appendChild(card);
                    countTodo++;
                } else if (t.status === "in_progress") {
                    listInProgress.appendChild(card);
                    countProg++;
                } else {
                    listDone.appendChild(card);
                    countDone++;
                }
            });

            document.getElementById("count-todo").textContent = countTodo;
            document.getElementById("count-in-progress").textContent = countProg;
            document.getElementById("count-done").textContent = countDone;
        }
    } catch (err) {
        console.error("Failed loading tasks:", err);
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
                workspace_id: activeWorkspaceId,
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
                document.getElementById("tab-doc").click();
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
    if (!svg) return;
    svg.innerHTML = "";

    try {
        const res = await fetch(`/api/v1/graph?workspace_id=${activeWorkspaceId}`);
        if (!res.ok) throw new Error("Failed to load knowledge graph");
        const { nodes, edges } = await res.json();

        if (nodes.length === 0) {
            svg.innerHTML = `
                <text x="50%" y="50%" fill="#6e7681" text-anchor="middle" font-size="13">
                    No document nodes available in this workspace. Add or import documents to generate graph topology.
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
        const res = await fetch(`/api/v1/graph/recompute?workspace_id=${activeWorkspaceId}`, { method: "POST" });
        if (!res.ok) throw new Error("Topology calculation failed");
        showToast("Topology recalculated across all documents.", "success");
        await renderKnowledgeGraph();
        await loadDashboardStats();
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
                body: JSON.stringify({ ...doc, workspace_id: activeWorkspaceId })
            });
        }
        await loadDocuments();
        await loadDashboardStats();
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
