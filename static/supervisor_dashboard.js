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
    
    let currentRestockItem = "";

    // --- API & DATA HANDLING ---

    async function runCommand(command, taskName) {
        log(`⏳ Queued: ${taskName}`);
        try {
            const response = await fetch("/api/supervisor_command", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command }),
            });
            const data = await response.json();
            log(`✅ ${taskName}: ${data.reply}`);
        } catch (e) {
            log(`❌ Command Error: ${e}`);
        }
        fetchData(); // Refresh all data after every action
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

    // --- RENDER LOGIC ---

    function renderInventory(items) {
        inventoryList.innerHTML = ""; // Clear list before re-rendering
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
        // Prepend to show new logs at the top and keep view scrolled there
        logContainer.prepend(p);
    }

    // --- MODAL HANDLING ---

    // Show
    inventoryList.addEventListener("click", e => {
        if (e.target.classList.contains("restock-btn")) {
            currentRestockItem = e.target.dataset.item;
            document.getElementById("restockItemName").textContent = currentRestockItem.replace(/_/g, ' ');
            restockModal.classList.remove("hidden");
        }
    });
    addItemBtn.addEventListener("click", () => addItemModal.classList.remove("hidden"));

    // Hide
    document.getElementById("cancelRestock").addEventListener("click", () => restockModal.classList.add("hidden"));
    document.getElementById("cancelAddItem").addEventListener("click", () => addItemModal.classList.add("hidden"));

    // Submit
    document.getElementById("confirmRestock").addEventListener("click", () => {
        const qtyInput = document.getElementById("restockQtyInput");
        const qty = qtyInput.value;
        if (qty && currentRestockItem) {
            runCommand(`Add ${qty} units to inventory for item '${currentRestockItem}'`, `Restocking ${currentRestockItem}`);
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
            runCommand(`Add new item '${name}' with ${qty} units`, `Adding ${name}`);
            addItemModal.classList.add("hidden");
            nameInput.value = "";
            qtyInput.value = "";
        }
    });
    
    // --- EVENT LISTENERS ---
    
    // Refresh Button
    refreshBtn.addEventListener("click", fetchData);
    
    // Command Center
    commandSendBtn.addEventListener("click", () => {
        if (commandInput.value) {
            runCommand(commandInput.value, `Command: ${commandInput.value.substring(0, 25)}...`);
            commandInput.value = "";
        }
    });
    commandInput.addEventListener("keydown", e => {
        if (e.key === "Enter") {
            commandSendBtn.click();
        }
    });

    // Action Buttons on Request Items
    requestList.addEventListener("click", e => {
        const id = e.target.dataset.id;
        if (!id) return;

        if (e.target.classList.contains("approve-btn")) {
            runCommand(`Approve request ID ${id}`, `Approving Req ${id}`);
        }
        if (e.target.classList.contains("reject-btn")) {
            runCommand(`Reject request ID ${id}`, `Rejecting Req ${id}`);
        }
    });

    // --- INITIAL LOAD & POLLING ---
    fetchData();
    setInterval(fetchData, 5000); // Auto-refresh data every 5 seconds
});