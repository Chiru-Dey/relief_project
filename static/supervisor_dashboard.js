document.addEventListener("DOMContentLoaded", () => {
    const logContainer = document.getElementById("logContainer");
    const inventoryList = document.getElementById("inventoryList");
    const requestList = document.getElementById("requestList");
    const refreshBtn = document.getElementById("refreshBtn");
    const commandInput = document.getElementById("commandInput");
    const commandSendBtn = document.getElementById("commandSendBtn");
    const restockModal = document.getElementById("restockModal");
    const addItemModal = document.getElementById("addItemModal");
    const addItemBtn = document.getElementById("addItemBtn");
    
    let currentRestockItem = "";
    const CLIENT_ID = 'sup_' + Math.random().toString(36).substring(2, 9);
    const seenLogIds = new Set();

    // --- API CALLS ---
    async function submitTask(payload) {
        const queuedMsg = `⏳ Queued: ${payload.task_name}`;
        const logKey = `queued_${Date.now()}_${payload.task_name}`;
        seenLogIds.add(logKey); // Mark as seen to prevent duplicate from backend
        log(queuedMsg, "queued");
        
        // DON'T log to backend here - it will be logged when the command executes
        
        try {
            await fetch("/api/submit_task", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...payload, client_id: CLIENT_ID, persona: "supervisor" }),
            });
        } catch (e) { log(`❌ Error: ${e}`, "error"); }
    }

    // 🔥 NEW: Direct Admin Call
    async function submitAdminAction(url, payload, actionName) {
        const processingMsg = `⚙️ Processing: ${actionName}...`;
        const logKey = `admin_${actionName}_${Date.now()}`;
        seenLogIds.add(logKey); // Prevent duplicate
        log(processingMsg, "queued");
        // DON'T log to backend - backend will log itself
        
        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.success) {
                // DON'T log success locally - it will come from backend via fetchActivityLog
                // Just refresh the data
                fetchData(); // Refresh UI immediately
                fetchActivityLog(); // Fetch new logs from backend
            } else {
                const errorMsg = `❌ Error: ${data.error}`;
                log(errorMsg, "error");
                logToActivityLog(errorMsg, "error");
            }
        } catch (e) { 
            const networkError = `❌ Network Error: ${e}`;
            log(networkError, "error");
            logToActivityLog(networkError, "error");
        }
    }
    
    async function pollResults() {
        try {
            const res = await fetch(`/api/get_results/${CLIENT_ID}`);
            const data = await res.json();
            if (data.results?.length > 0) {
                // Just refresh data, don't log locally - backend already logged
                // The logs will appear via fetchActivityLog()
                fetchData();
                fetchActivityLog(); // Fetch the new logs from backend
            }
        } catch (e) {}
    }

    async function fetchData() {
        try {
            const res = await fetch("/api/supervisor_data");
            const data = await res.json();
            if (!data.error) {
                renderInventory(data.inventory);
                renderRequests(data.requests);
            }
        } catch (e) {}
    }

    async function fetchAuditLog() {
        try {
            const res = await fetch("/api/audit_log");
            const data = await res.json();
            if (data.logs?.length > 0) {
                data.logs.forEach(l => {
                    if (!seenLogIds.has(l.id)) {
                        seenLogIds.add(l.id);
                        log(`SYSTEM: ${l.action}`, "server");
                    }
                });
            }
        } catch (e) {}
    }

    async function fetchActivityLog() {
        try {
            const res = await fetch("/api/supervisor_activity_log");
            const data = await res.json();
            if (data.logs?.length > 0) {
                // Display backend logs (admin actions, system events, command responses)
                data.logs.forEach(l => {
                    // Create a unique key based on timestamp and action content
                    const logKey = `backend_${l.timestamp}_${l.action.substring(0, 100)}`;
                    if (!seenLogIds.has(logKey)) {
                        seenLogIds.add(logKey);
                        // Map backend log type to frontend display type with proper colors
                        let displayType = "response"; // Default blue for command responses
                        if (l.type === "error") {
                            displayType = "error"; // Red for errors
                        } else if (l.type === "success") {
                            displayType = "server"; // Green for success
                        } else if (l.type === "system") {
                            displayType = "response"; // Blue for system events
                        } else if (l.type === "info") {
                            displayType = "response"; // Blue for info/command responses
                        } else if (l.type === "warning") {
                            displayType = "queued"; // Yellow for warnings
                        }
                        // Don't add timestamp here since log() function adds its own
                        log(l.action, displayType);
                    }
                });
            }
        } catch (e) {}
    }

    // Helper to log to backend activity log
    async function logToActivityLog(message, logType) {
        try {
            await fetch("/api/log_supervisor_activity", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: message, type: logType })
            });
        } catch (e) {}
    }

    function log(message, type="local") {
        const p = document.createElement("div");
        p.className = "log-entry";
        const time = new Date().toLocaleTimeString();
        let colorClass = "log-local";
        if (type === "error") colorClass = "log-error";
        if (type === "server") colorClass = "log-server";
        if (type === "queued") colorClass = "log-queued"; // Yellow for queued
        if (type === "response") colorClass = "log-response"; // Blue for responses
        p.innerHTML = `<span class="log-time">[${time}]</span><span class="${colorClass}">${message}</span>`;
        logContainer.prepend(p);
    }

    // --- RENDER (Unchanged) ---
    function renderInventory(items) {
        inventoryList.innerHTML = "";
        if (!items?.length) { inventoryList.innerHTML = "<p>No inventory.</p>"; return; }
        items.forEach(item => {
            const div = document.createElement("div");
            div.className = "inventory-item";
            div.innerHTML = `<span><strong>${item.item_name.replace(/_/g, ' ')}</strong></span><div><span style="margin-right:1rem;">${item.quantity} units</span><button class="restock-btn" data-item="${item.item_name}">Restock</button></div>`;
            inventoryList.appendChild(div);
        });
    }

    function renderRequests(requests) {
        requestList.innerHTML = "";
        if (!requests?.length) { requestList.innerHTML = "<p>No pending requests.</p>"; return; }
        requests.forEach(req => {
            const div = document.createElement("div");
            div.className = "request-item";
            
            if (req.status === 'ACTION_REQUIRED') {
                // Critical action needed - yellow border
                div.style.borderColor = "#FBBF24";
                div.innerHTML = `<div class="request-details"><strong>❗ ACTION REQUIRED (ID ${req.id}):</strong> ${req.notes}<br><small>${req.location}</small></div><div class="request-actions"><button class="resolve-btn" data-id="${req.id}" data-notes="${req.notes}" style="background-color:#10B981;">Resolve</button></div>`;
            } else if (req.status === 'PENDING_DISPATCH' || req.status === 'PARTIAL') {
                // Waiting for restock - blue/cyan border, needs resolve action
                div.style.borderColor = "#3B82F6";
                const displayText = req.notes || `${req.quantity}x ${req.item_name.replace(/_/g, ' ')} for ${req.location}`;
                div.innerHTML = `<div class="request-details"><strong>⏳ ${req.status} (ID ${req.id}):</strong> ${displayText}<br><small>Click Resolve to restock & dispatch</small></div><div class="request-actions"><button class="resolve-btn" data-id="${req.id}" data-notes="${displayText}" style="background-color:#3B82F6;">Resolve</button></div>`;
            } else {
                // Regular pending - default styling
                div.innerHTML = `<div class="request-details"><strong>⏳ PENDING (ID ${req.id}):</strong> ${req.quantity}x ${req.item_name.replace(/_/g, ' ')} for ${req.location}</div><div class="request-actions"><button class="approve-btn" data-id="${req.id}">Approve</button><button class="reject-btn" data-id="${req.id}" style="background-color:#DC2626;">Reject</button></div>`;
            }
            requestList.appendChild(div);
        });
    }

    // --- EVENT LISTENERS ---
    refreshBtn.onclick = fetchData;
    commandSendBtn.onclick = () => { if (commandInput.value) { submitTask({ text: `[[SOURCE: SUPERVISOR]] ${commandInput.value}`, task_name: `CMD: ${commandInput.value}` }); commandInput.value = ""; } };
    commandInput.onkeydown = (e) => { if(e.key==="Enter") commandSendBtn.click(); };

    inventoryList.onclick = (e) => {
        if (e.target.classList.contains("restock-btn")) {
            currentRestockItem = e.target.dataset.item;
            document.getElementById("restockItemName").textContent = currentRestockItem.replace(/_/g, ' ');
            restockModal.classList.remove("hidden");
        }
    };
    addItemBtn.onclick = () => addItemModal.classList.remove("hidden");
    document.getElementById("cancelRestock").onclick = () => restockModal.classList.add("hidden");
    document.getElementById("cancelAddItem").onclick = () => addItemModal.classList.add("hidden");

    // 🔥 FIX: Calls Direct Admin API
    document.getElementById("confirmRestock").onclick = () => {
        const qty = document.getElementById("restockQtyInput").value;
        if(qty) {
            submitAdminAction("/api/admin/restock", { item_name: currentRestockItem, quantity: qty }, `Restocking ${currentRestockItem}`);
            restockModal.classList.add("hidden");
            document.getElementById("restockQtyInput").value = "";
        }
    };
    // 🔥 FIX: Calls Direct Admin API
    document.getElementById("confirmAddItem").onclick = () => {
        const name = document.getElementById("newItemNameInput").value;
        const qty = document.getElementById("newItemQtyInput").value;
        if(name && qty) {
            submitAdminAction("/api/admin/add_item", { item_name: name, quantity: qty }, `Adding ${name}`);
            addItemModal.classList.add("hidden");
            document.getElementById("newItemNameInput").value = "";
        }
    };

    requestList.onclick = (e) => {
        const id = e.target.dataset.id;
        if (!id) return;
        if (e.target.classList.contains("approve-btn")) submitTask({ text: `[[SOURCE: SUPERVISOR]] Approve request ID ${id}`, task_name: `Approving ${id}` });
        if (e.target.classList.contains("reject-btn")) submitTask({ text: `[[SOURCE: SUPERVISOR]] Reject request ID ${id}`, task_name: `Rejecting ${id}` });
        if (e.target.classList.contains("resolve-btn")) {
            // Directly call the resolve API
            const resolveMsg = `⏳ Resolving action item ${id}...`;
            const logKey = `resolve_${id}_${Date.now()}`;
            seenLogIds.add(logKey); // Prevent duplicate
            log(resolveMsg, "queued");
            // DON'T log to backend - backend will log itself
            
            fetch(`/api/admin/resolve/${id}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    // DON'T log success locally - it will come from backend via fetchActivityLog
                    fetchData(); // Refresh
                    fetchActivityLog(); // Fetch new logs from backend
                } else {
                    log(`❌ Resolve failed: ${data.error}`, "error");
                    logToActivityLog(`Resolve failed: ${data.error}`, "error");
                }
            }).catch(e => log(`❌ Error: ${e}`, "error"));
        }
    };

    fetchData();
    fetchAuditLog();
    fetchActivityLog();
    setInterval(pollResults, 1000);
    setInterval(fetchAuditLog, 3000);
    setInterval(fetchActivityLog, 2000);  // Poll activity log more frequently
    setInterval(fetchData, 5000);
});