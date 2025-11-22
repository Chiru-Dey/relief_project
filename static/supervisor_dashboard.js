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

    // --- API ---
    async function submitTask(payload) {
        log(`⏳ Queued: ${payload.task_name}`);
        try {
            await fetch("/api/submit_task", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...payload, client_id: CLIENT_ID, persona: "supervisor" }),
            });
        } catch (e) { log(`❌ Error: ${e}`); }
    }
    
    async function pollResults() {
        try {
            const res = await fetch(`/api/get_results/${CLIENT_ID}`);
            const data = await res.json();
            if (data.results?.length > 0) {
                data.results.forEach(r => log(`✅ ${r.task_name}: ${r.output}`));
                fetchData();
            }
        } catch (e) {}
    }

    async function fetchData() {
        try {
            const res = await fetch("/api/supervisor_data");
            const data = await res.json();
            renderInventory(data.inventory);
            renderRequests(data.requests);
        } catch (e) { log(`Network Error: ${e}`); }
    }

    async function fetchAuditLog() {
        try {
            const res = await fetch("/api/audit_log");
            const data = await res.json();
            if (data.logs) {
                renderLogs(data.logs);
            }
        } catch (e) { console.error("Log fetch error", e); }
    }

    function renderLogs(logs) {
        logContainer.innerHTML = ""; // Clear old logs
        if (logs.length === 0) {
            logContainer.innerHTML = "<p>No recent activity.</p>";
            return;
        }
        logs.forEach(l => {
            const p = document.createElement("p");
            p.style.borderBottom = "1px solid #333";
            p.style.paddingBottom = "4px";
            p.style.marginBottom = "4px";
            // Color code based on status
            let color = "#10B981"; // Green for AI_APPROVED
            if (l.action.includes("REJECTED")) color = "#EF4444";
            
            p.innerHTML = `<span style="color:${color}">●</span> ${l.action}`;
            logContainer.appendChild(p);
        });
    }

    // --- Loop for Logs ---
    setInterval(fetchAuditLog, 3000); // Poll logs every 3s
    

    // --- RENDER ---
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
        if (!requests?.length) { requestList.innerHTML = "<p>No attention items.</p>"; return; }
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

    function log(msg) {
        const p = document.createElement("p");
        p.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        logContainer.prepend(p);
    }

    // --- EVENTS ---
    refreshBtn.onclick = fetchData;
    commandSendBtn.onclick = () => {
        if (commandInput.value) {
            submitTask({ text: commandInput.value, task_name: `CMD: ${commandInput.value}` });
            commandInput.value = "";
        }
    };
    commandInput.onkeydown = (e) => { if(e.key==="Enter") commandSendBtn.click(); };

    inventoryList.onclick = (e) => {
        if (e.target.classList.contains("restock-btn")) {
            currentRestockItem = e.target.dataset.item;
            document.getElementById("restockItemName").textContent = currentRestockItem.replace(/_/g, ' ');
            
            // FIXED: Clear input value before showing modal
            document.getElementById("restockQtyInput").value = "";
            
            restockModal.classList.remove("hidden");
        }
    };

    addItemBtn.onclick = () => {
        // FIXED: Clear input values before showing modal
        document.getElementById("newItemNameInput").value = "";
        document.getElementById("newItemQtyInput").value = "";
        
        addItemModal.classList.remove("hidden");
    };
    
    // Modals
    document.getElementById("cancelRestock").onclick = () => restockModal.classList.add("hidden");
    document.getElementById("cancelAddItem").onclick = () => addItemModal.classList.add("hidden");
    
    document.getElementById("confirmRestock").onclick = () => {
        const qty = document.getElementById("restockQtyInput").value;
        if(qty) {
            submitTask({ text: `Add ${qty} units to inventory for item '${currentRestockItem}'`, task_name: `Restocking ${currentRestockItem}` });
            restockModal.classList.add("hidden");
        }
    };
    document.getElementById("confirmAddItem").onclick = () => {
        const name = document.getElementById("newItemNameInput").value;
        const qty = document.getElementById("newItemQtyInput").value;
        if(name && qty) {
            submitTask({ text: `Add new item '${name}' with ${qty} units`, task_name: `Adding ${name}` });
            addItemModal.classList.add("hidden");
        }
    };

    requestList.onclick = (e) => {
        const id = e.target.dataset.id;
        if (!id) return;
        if (e.target.classList.contains("approve-btn")) submitTask({ text: `Approve request ID ${id}`, task_name: `Approving ${id}` });
        if (e.target.classList.contains("reject-btn")) submitTask({ text: `Reject request ID ${id}`, task_name: `Rejecting ${id}` });
        if (e.target.classList.contains("resolve-btn")) {
            const notes = e.target.dataset.notes;
            commandInput.value = `I need to resolve action item ${id}. Notes: ${notes}. Suggest a plan.`;
            commandInput.focus();
        }
    };

    fetchData();
    setInterval(pollResults, 1000);
});
