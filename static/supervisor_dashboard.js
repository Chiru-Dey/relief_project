document.addEventListener("DOMContentLoaded", () => {
    // --- ELEMENT REFERENCES ---
    const logContainer = document.getElementById("logContainer");
    const inventoryList = document.getElementById("inventoryList");
    const requestList = document.getElementById("requestList");
    const refreshBtn = document.getElementById("refreshBtn");
    const commandInput = document.getElementById("commandInput");
    const commandSendBtn = document.getElementById("commandSendBtn");
    
    // Modals
    const restockModal = document.getElementById("restockModal");
    const addItemModal = document.getElementById("addItemModal");
    const addItemBtn = document.getElementById("addItemBtn");
    
    // --- STATE ---
    const CLIENT_ID = 'sup_' + Math.random().toString(36).substring(2, 9);
    let currentRestockItem = "";

    // --- API & DATA HANDLING ---
    async function submitTask(payload) {
        log(`⏳ Queued: ${payload.task_name}`);
        try {
            await fetch("/api/submit_task", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...payload, client_id: CLIENT_ID, persona: "supervisor" }),
            });
        } catch (e) {
            log(`❌ Network Error on Submit: ${e}`);
        }
    }
    
    async function pollResults() {
        try {
            const res = await fetch(`/api/get_results/${CLIENT_ID}`);
            const data = await res.json();
            if (data.results && data.results.length > 0) {
                data.results.forEach(result => {
                    log(`✅ ${result.task_name}: ${result.output}`);
                });
                fetchData(); // Refresh all data after a result comes in
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    }

    async function fetchData() {
        try {
            const res = await fetch("/api/supervisor_data");
            const data = await res.json();
            if (data.error) {
                log(`DB Error: ${data.error}`);
                return;
            }
            renderInventory(data.inventory);
            renderRequests(data.requests);
        } catch (e) {
            log(`Network Error fetching data: ${e}`);
        }
    }

    // --- RENDER FUNCTIONS ---
    function renderInventory(items) {
        inventoryList.innerHTML = "";
        if (!items || items.length === 0) {
            inventoryList.innerHTML = "<p>No inventory found.</p>";
            return;
        }
        items.forEach(item => {
            const div = document.createElement("div");
            div.className = "inventory-item";
            div.innerHTML = `
                <span><strong>${item.item_name.replace(/_/g, ' ')}</strong></span>
                <div>
                    <span style="margin-right: 1rem; color: ${item.quantity < 20 ? '#F87171' : 'inherit'};">${item.quantity} units</span>
                    <button class="restock-btn" data-item="${item.item_name}">Restock</button>
                </div>
            `;
            inventoryList.appendChild(div);
        });
    }

    function renderRequests(requests) {
        requestList.innerHTML = "";
        if (!requests || requests.length === 0) {
            requestList.innerHTML = "<p>No pending requests.</p>";
            return;
        }
        requests.forEach(req => {
            const div = document.createElement("div");
            div.className = "request-item";
            const criticalSpan = req.urgency === 'CRITICAL' ? '<span style="color:#F87171; font-weight: bold; margin-left: 8px;">CRITICAL</span>' : '';
            div.innerHTML = `
                <div class="request-details">
                    <strong>ID ${req.id}:</strong> ${req.quantity}x ${req.item_name.replace(/_/g, ' ')} for ${req.location}
                    ${criticalSpan}
                </div>
                <div class="request-actions">
                    <button class="approve-btn" data-id="${req.id}">Approve</button>
                    <button class="reject-btn" data-id="${req.id}" style="background-color:#DC2626;">Reject</button>
                </div>
            `;
            requestList.appendChild(div);
        });
    }

    function log(message) {
        const p = document.createElement("p");
        p.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        logContainer.prepend(p);
    }

    // --- MODAL HANDLING ---
    
    // Show Modals
    inventoryList.addEventListener("click", e => {
        if (e.target.classList.contains("restock-btn")) {
            currentRestockItem = e.target.dataset.item;
            document.getElementById("restockItemName").textContent = currentRestockItem.replace(/_/g, ' ');
            restockModal.classList.remove("hidden");
        }
    });
    addItemBtn.addEventListener("click", () => addItemModal.classList.remove("hidden"));

    // Hide Modals
    document.getElementById("cancelRestock").addEventListener("click", () => restockModal.classList.add("hidden"));
    document.getElementById("cancelAddItem").addEventListener("click", () => addItemModal.classList.add("hidden"));

    // Submit Modals
    document.getElementById("confirmRestock").addEventListener("click", () => {
        const qtyInput = document.getElementById("restockQtyInput");
        const qty = qtyInput.value;
        if (qty && currentRestockItem) {
            const taskName = `Restocking ${currentRestockItem}`;
            // 🔥 FIX: Use "text" key to send command
            submitTask({ 
                text: `Add ${qty} units to inventory for item '${currentRestockItem}'`, 
                task_name: taskName 
            });
            restockModal.classList.add("hidden");
            qtyInput.value = "";
        }
    });
    document.getElementById("confirmAddItem").addEventListener("click", () => {
        const nameInput = document.getElementById("newItemNameInput");
        const qtyInput = document.getElementById("newItemQtyInput");
        const name = nameInput.value;
        const qty = qtyInput.value;
        if (name && qty) {
            const taskName = `Adding ${name}`;
            // 🔥 FIX: Use "text" key to send command
            submitTask({ 
                text: `Add new item '${name}' with ${qty} units`, 
                task_name: taskName 
            });
            addItemModal.classList.add("hidden");
            nameInput.value = "";
            qtyInput.value = "";
        }
    });
    
    // --- EVENT LISTENERS ---
    
    refreshBtn.addEventListener("click", fetchData);
    
    commandSendBtn.addEventListener("click", () => {
        if (commandInput.value) {
            const taskName = `Command: ${commandInput.value.substring(0, 25)}...`;
            // 🔥 FIX: Use "text" key to send command
            submitTask({ text: commandInput.value, task_name: taskName });
            commandInput.value = "";
        }
    });
    commandInput.addEventListener("keydown", e => {
        if (e.key === "Enter") {
            commandSendBtn.click();
        }
    });

    requestList.addEventListener("click", e => {
        const id = e.target.dataset.id;
        if (!id) return;
        if (e.target.classList.contains("approve-btn")) {
            // 🔥 FIX: Use "text" key to send command
            submitTask({ text: `Approve request ID ${id}`, task_name: `Approving Req ${id}` });
        }
        if (e.target.classList.contains("reject-btn")) {
            // 🔥 FIX: Use "text" key to send command
            submitTask({ text: `Reject request ID ${id}`, task_name: `Rejecting Req ${id}` });
        }
    });

    // --- INITIAL LOAD & POLLING ---
    fetchData();
    setInterval(pollResults, 1000);
});