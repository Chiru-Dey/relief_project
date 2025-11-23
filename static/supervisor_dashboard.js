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
        log(`⏳ Queued: ${payload.task_name}`, "local");
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
        log(`⚙️ Processing: ${actionName}...`, "local");
        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.success) {
                log(`✅ Success: ${data.message}`, "server");
                fetchData(); // Refresh UI immediately
                fetchAuditLog(); // Refresh logs
            } else {
                log(`❌ Error: ${data.error}`, "error");
            }
        } catch (e) { log(`❌ Network Error: ${e}`, "error"); }
    }
    
    async function pollResults() {
        try {
            const res = await fetch(`/api/get_results/${CLIENT_ID}`);
            const data = await res.json();
            if (data.results?.length > 0) {
                data.results.forEach(r => {
                     // Simple error check
                     const type = r.output.includes("ERROR") ? "error" : "local";
                     log(`✅ ${r.task_name}: ${r.output}`, type);
                });
                fetchData(); 
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

    function log(message, type="local") {
        const p = document.createElement("div");
        p.className = "log-entry";
        const time = new Date().toLocaleTimeString();
        let colorClass = "log-local";
        if (type === "error") colorClass = "log-error";
        if (type === "server") colorClass = "log-server";
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
                div.style.borderColor = "#FBBF24";
                div.innerHTML = `<div class="request-details"><strong>❗ ACTION (ID ${req.id}):</strong> ${req.notes}<br><small>${req.location}</small></div><div class="request-actions"><button class="resolve-btn" data-id="${req.id}" data-notes="${req.notes}" style="background-color:#10B981;">Resolve</button></div>`;
            } else {
                div.innerHTML = `<div class="request-details"><strong>⏳ PENDING (ID ${req.id}):</strong> ${req.quantity}x ${req.item_name.replace(/_/g, ' ')} for ${req.location}</div><div class="request-actions"><button class="approve-btn" data-id="${req.id}">Approve</button><button class="reject-btn" data-id="${req.id}" style="background-color:#DC2626;">Reject</button></div>`;
            }
            requestList.appendChild(div);
        });
    }

    // --- EVENT LISTENERS ---
    refreshBtn.onclick = fetchData;
    commandSendBtn.onclick = () => { if (commandInput.value) { submitTask({ text: commandInput.value, task_name: `CMD: ${commandInput.value.substring(0, 20)}` }); commandInput.value = ""; } };
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
        if (e.target.classList.contains("approve-btn")) submitTask({ text: `Approve request ID ${id}`, task_name: `Approving ${id}` });
        if (e.target.classList.contains("reject-btn")) submitTask({ text: `Reject request ID ${id}`, task_name: `Rejecting ${id}` });
        if (e.target.classList.contains("resolve-btn")) {
            const notes = e.target.dataset.notes;
            commandInput.value = `Fix action item ${id} immediately. Notes: '${notes}'. Restock buffer, send to victim, mark resolved.`;
            commandInput.focus();
        }
    };

    fetchData();
    fetchAuditLog();
    setInterval(pollResults, 1000);
    setInterval(fetchAuditLog, 3000);
    setInterval(fetchData, 5000);
});