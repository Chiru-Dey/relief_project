document.addEventListener("DOMContentLoaded", () => {
    // --- Elements ---
    const textarea = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const micBtn = document.getElementById('micBtn');
    const messagesContent = document.getElementById('messagesContent');
    const scrollContainer = document.getElementById('messagesContainer');
    const micIcon = document.getElementById('micIcon');
    const stopIcon = document.getElementById('stopIcon');
    const MAX_HEIGHT = 200;

    // --- State ---
    let isListening = false;
    // Generate unique IDs for this browser tab
    const CLIENT_ID = 'vic_' + Math.random().toString(36).substring(2, 9);
    let sessionId = 'session_' + Date.now();

    // --- Core Functions ---

    function autoResize() {
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
        if (textarea.scrollHeight > MAX_HEIGHT) {
            textarea.style.overflowY = 'auto';
        } else {
            textarea.style.overflowY = 'hidden';
        }
        sendBtn.disabled = !textarea.value.trim();
    }

    function addBubble(text, sender) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${sender}`;
        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${sender}`;
        bubble.innerHTML = text.replace(/\n/g, '<br>');
        wrapper.appendChild(bubble);
        messagesContent.appendChild(wrapper);
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
    
    // --- BACKEND COMMUNICATION (Queue Pattern) ---
    
    async function submitTask(payload) {
        const taskName = payload.text ? `Text: ${payload.text.substring(0, 15)}...` : "Audio Message";
        showLoading(taskName);

        try {
            // 🔥 FIX: Send to the correct unified endpoint
            await fetch('/api/submit_task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    ...payload, 
                    client_id: CLIENT_ID, 
                    session_id: sessionId, 
                    task_name: taskName, 
                    persona: "victim" 
                })
            });
        } catch (error) {
            hideLoading();
            addBubble("Error: Could not submit task to the agent backend.", 'ai');
        }
    }
    
    async function pollResults() {
        try {
            const res = await fetch(`/api/get_results/${CLIENT_ID}`);
            const data = await res.json();
            if (data.results && data.results.length > 0) {
                hideLoading();
                data.results.forEach(result => {
                    if (result.persona === 'victim') {
                        addBubble(result.output, 'ai');
                    }
                });
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }

    let loadingDivId = null;
    function showLoading(taskName) {
        hideLoading(); // Clear any old loaders
        loadingDivId = 'loading-' + Date.now();
        const loader = document.createElement('div');
        loader.id = loadingDivId;
        loader.className = 'message-wrapper ai';
        loader.innerHTML = '<div class="message-bubble ai" style="color:#A8C7FA">Thinking...</div>';
        messagesContent.appendChild(loader);
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
    
    function hideLoading() {
        if(loadingDivId) {
            const loader = document.getElementById(loadingDivId);
            if(loader) loader.remove();
            loadingDivId = null;
        }
    }
    
    // --- Event Handlers ---

    function handleSendText() {
        const text = textarea.value.trim();
        if (!text) return;
        addBubble(text, 'user');
        textarea.value = ''; autoResize();
        submitTask({ text: text });
    }
    
    let mediaRecorder, audioChunks = [];
    async function handleToggleMic() {
        isListening = !isListening;

        // 🔥 FIX: Correctly toggle classes for 2-state button
        micBtn.classList.toggle('listening', isListening);
        micIcon.classList.toggle('hidden', isListening);
        micIcon.classList.toggle('block', !isListening);
        stopIcon.classList.toggle('hidden', !isListening);
        stopIcon.classList.toggle('block', isListening);
        
        if (isListening) {
            // START RECORDING
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.readAsDataURL(audioBlob);
                    reader.onloadend = () => {
                        addBubble("🎤 [Audio Sent]", "user");
                        submitTask({ audio: reader.result });
                    };
                };
                mediaRecorder.start();
            } catch (err) { 
                console.error("Microphone access denied:", err);
                isListening = false; // Reset state on error
                handleToggleMic(); // Revert UI
            }
        } else {
            // STOP RECORDING
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
        }
    }

    // --- Event Listeners ---
    textarea.addEventListener('input', autoResize);
    textarea.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendText(); } });
    sendBtn.addEventListener('click', handleSendText);
    micBtn.addEventListener('click', handleToggleMic);
    
    // --- Init ---
    addBubble("Hello! How can I help you today?", "ai");
    autoResize();
    setInterval(pollResults, 1000); // Start polling for results
});