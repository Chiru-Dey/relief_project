document.addEventListener("DOMContentLoaded", () => {
    const logContainer = document.getElementById("logContainer");
    // Generate a unique ID for this browser tab session
    const CLIENT_ID = 'sup_' + Math.random().toString(36).substring(2, 9);
    
    // --- API CALLS ---
    async function submitTask(payload) {
        // Just puts the job on the queue, doesn't wait for it
        await fetch("/api/submit_task", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...payload, client_id: CLIENT_ID }),
        });
    }
    
    async function pollResults() {
        try {
            const res = await fetch(`/api/get_results/${CLIENT_ID}`);
            const data = await res.json();
            if (data.results && data.results.length > 0) {
                data.results.forEach(result => {
                    log(`✅ ${result.task_name}: ${result.output}`);
                });
                fetchData(); // Refresh data after a result comes in
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    }

    async function fetchData() {
        const res = await fetch("/api/supervisor_data");
        const data = await res.json();
        if (data.error) { log(`DB Error: ${data.error}`); return; }
        renderInventory(data.inventory);
        renderRequests(data.requests);
    }

    // --- RENDER FUNCTIONS ---
    function renderInventory(items) { /* ... (same as before) ... */ }
    function renderRequests(requests) { /* ... (same as before) ... */ }

    function log(message) {
        const p = document.createElement("p");
        p.textContent = message;
        logContainer.prepend(p);
    }
    
    // --- UI EVENT LISTENERS ---
    
    // Command Input
    document.getElementById("commandSendBtn").addEventListener("click", () => {
        const input = document.getElementById("commandInput");
        if (input.value) {
            const taskName = `Command: ${input.value.substring(0, 20)}...`;
            log(`⏳ Queued: ${taskName}`);
            submitTask({
                persona: "supervisor",
                command: input.value,
                task_name: taskName,
            });
            input.value = "";
        }
    });

    // Request Buttons
    document.getElementById("requestList").addEventListener("click", e => {
        const id = e.target.dataset.id;
        if (e.target.classList.contains("approve-btn")) {
            const taskName = `Approving Req ${id}`;
            log(`⏳ Queued: ${taskName}`);
            submitTask({ persona: "supervisor", command: `Approve request ID ${id}`, task_name: taskName });
        }
        if (e.target.classList.contains("reject-btn")) {
            const taskName = `Rejecting Req ${id}`;
            log(`⏳ Queued: ${taskName}`);
            submitTask({ persona: "supervisor", command: `Reject request ID ${id}`, task_name: taskName });
        }
    });

    // --- INITIAL LOAD & POLLING ---
    fetchData();
    setInterval(pollResults, 1000); // Check for results every second
});