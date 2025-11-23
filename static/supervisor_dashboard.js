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
    
    const CLIENT_ID = 'sup_' + Math.random().toString(36).substring(2, 9);
    let currentRestockItem = "";
    const seenLogIds = new Set();

    // --- API ---
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
    
    async function pollResults() {
        try {
            const res = await fetch(`/api/get_results/${CLIENT_ID}`);
            const data = await res.json();
            if (data.results && data.results.length > 0) {
                data.results.forEach(result => {
                    const output = result.output;
                    
                    // 🔥 FIX: Smart Error Detection
                    if (output.startsWith("ERROR") || output.includes("System busy") || output.includes("failed")) {
                        log(`❌ ${result.task_name}: ${output}`, "error"); // RED
                    } else {
                        log(`✅ ${result.task_name}: ${output}`, "local"); // GREEN
                    }
                });
                fetchData(); 
            }
        } catch (e) { console.error(e); }
    }


    async function fetchData() {
        try {
            const res = await fetch("/api/supervisor_data");
            const data = await res.json();
            if (data.error) return;
            renderInventory(data.inventory);
            renderRequests(data.requests);
        } catch (e) {}
    }

    async function fetchAuditLog() {
        try {
            const res = await fetch("/api/audit_log");
            const data = await res.json();
            if (data.logs && data.logs.length > 0) {
                data.logs.forEach(l => {
                    if (!seenLogIds.has(l.id)) {
                        seenLogIds.add(l.id);
                        log(`SYSTEM: ${l.action}`, "server");
                    }
                });
            }
        } catch (e) {}
    }

    // --- RENDER ---
    function renderInventory(items) {
        inventoryList.innerHTML = "";
        if (!items || items.length === 0) {
            inventoryList.innerHTML = "<p>No inventory found.</p>";
            return;
        }
        items.forEach(item => {
            const div = document.createElement("div");
            div.className = "inventory-item";
            div.innerHTML = `<span><strong>${item.item_name.replace(/_/g, ' ')}</strong></span><div><span style="margin-right:1rem;">${item.quantity} units</span><button class="restock-btn" data-item="${item.item_name}">Restock</button></div>`;
            inventoryList.appendChild(div);
        });
    }

    function renderRequests(requests) {
        requestList.innerHTML = "";
        if (!requests || requests.length === 0) { requestList.innerHTML = "<p>No items require attention.</p>"; return; }
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
    

    function log(message, type="local") {
        const p = document.createElement("div");
        p.className = "log-entry";
        const time = new Date().toLocaleTimeString();
        const colorClass = type === "error" ? "log-error" : (type === "server" ? "log-server" : "log-local");
        p.innerHTML = `<span class="log-time">[${time}]</span><span class="${colorClass}">${message}</span>`;
        logContainer.prepend(p);
    }

    // --- EVENTS ---
    refreshBtn.onclick = fetchData;
    commandSendBtn.onclick = () => {
        if (commandInput.value) {
            submitTask({ text: commandInput.value, task_name: `CMD: ${commandInput.value.substring(0, 20)}` });
            commandInput.value = "";
        }
    };
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
    
    document.getElementById("confirmRestock").onclick = () => {
        const qty = document.getElementById("restockQtyInput").value;
        if(qty) {
            submitTask({ text: `Add ${qty} units to inventory for item '${currentRestockItem}'`, task_name: `Restocking ${currentRestockItem}` });
            restockModal.classList.add("hidden");
            document.getElementById("restockQtyInput").value = "";
        }
    };
    document.getElementById("confirmAddItem").onclick = () => {
        const name = document.getElementById("newItemNameInput").value;
        const qty = document.getElementById("newItemQtyInput").value;
        if(name && qty) {
            submitTask({ text: `Add new item '${name}' with ${qty} units`, task_name: `Adding ${name}` });
            addItemModal.classList.add("hidden");
            document.getElementById("newItemNameInput").value = "";
        }
    };

    requestList.onclick = (e) => {
        const id = e.target.dataset.id;
        if (!id) return;
        if (e.target.classList.contains("approve-btn")) submitTask({ text: `Approve request ID ${id}`, task_name: `Approving ${id}` });
        if (e.target.classList.contains("reject-btn")) submitTask({ text: `Reject request ID ${id}`, task_name: `Rejecting ${id}` });
        
        // 🔥 UPDATED: SEND "FIX IT" COMMAND
        if (e.target.classList.contains("resolve-btn")) {
            const notes = e.target.dataset.notes;
            // The prompt now COMMANDS the agent to fix the issue, rather than asking for advice.
            const command = `Fix action item ${id} immediately. Read the notes: '${notes}'. Restock the item with a buffer, send the required amount to the victim, and mark the task as resolved.`;
            
            commandInput.value = command;
            commandInput.focus();
        }
    };

    fetchData();
    fetchAuditLog();
    setInterval(pollResults, 1000);
    setInterval(fetchAuditLog, 3000);
    setInterval(fetchData, 5000);
});