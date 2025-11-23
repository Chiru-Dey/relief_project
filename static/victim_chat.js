document.addEventListener("DOMContentLoaded", () => {
    const textarea = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const micBtn = document.getElementById('micBtn');
    const messagesContent = document.getElementById('messagesContent');
    const scrollContainer = document.getElementById('messagesContainer');
    const micIcon = document.getElementById('micIcon');
    const stopIcon = document.getElementById('stopIcon');
    const MAX_HEIGHT = 200;

    let isListening = false;
    const CLIENT_ID = 'vic_' + Math.random().toString(36).substring(2, 9);
    
    // 🔥 SESSION PERSISTENCE LOGIC
    let sessionId = sessionStorage.getItem("relief_session_id");
    if (!sessionId) {
        sessionId = 'session_' + Date.now();
        sessionStorage.setItem("relief_session_id", sessionId);
    }

    function autoResize() {
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
        if (textarea.scrollHeight > MAX_HEIGHT) textarea.style.overflowY = 'auto';
        else textarea.style.overflowY = 'hidden';
        sendBtn.disabled = !textarea.value.trim();
    }

    function addBubble(text, sender) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${sender}`;
        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${sender}`;
        // Basic markdown parsing for bold text
        const formatted = text.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        bubble.innerHTML = formatted;
        wrapper.appendChild(bubble);
        messagesContent.appendChild(wrapper);
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }

    // 🔥 LOAD HISTORY ON START
    async function loadHistory() {
        try {
            const res = await fetch(`/api/victim_history/${sessionId}`);
            const data = await res.json();
            
            // Clear existing (except maybe greeting)
            messagesContent.innerHTML = '';
            addBubble("Hello! How can I help you today?", "ai");

            if (data.history) {
                data.history.forEach(msg => {
                    // msg.sender is 'user' or 'ai'
                    addBubble(msg.text, msg.sender === 'user' ? 'user' : 'ai');
                });
            }
        } catch (e) { console.error("History load failed", e); }
    }

    async function submitTask(payload) {
        const taskName = payload.text ? `Text: ${payload.text.substring(0, 15)}...` : "Audio Message";
        showLoading();

        try {
            await fetch('/api/submit_task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...payload, client_id: CLIENT_ID, session_id: sessionId, task_name: taskName, persona: "victim" })
            });
        } catch (error) {
            hideLoading();
            addBubble("Error connecting.", 'ai');
        }
    }
    
    async function pollResults() {
        try {
            const res = await fetch(`/api/get_results/${CLIENT_ID}`);
            const data = await res.json();
            if (data.results && data.results.length > 0) {
                hideLoading();
                data.results.forEach(result => {
                    if (result.persona === 'victim') addBubble(result.output, 'ai');
                });
            }
        } catch (e) { console.error(e); }
    }

    let loadingDivId = null;
    function showLoading() {
        hideLoading(); 
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
    
    function handleSendText() {
        const text = textarea.value.trim();
        if (!text) return;
        // UI update handled by loadHistory logic if we want strict sync, 
        // but for responsiveness we add locally too.
        addBubble(text, 'user');
        textarea.value = ''; autoResize();
        submitTask({ text: text });
    }
    
    let mediaRecorder, audioChunks = [];
    async function handleToggleMic() {
        isListening = !isListening;
        micBtn.classList.toggle('listening', isListening);
        micIcon.classList.toggle('hidden', !isListening);
        stopIcon.classList.toggle('hidden', isListening);
        
        if (isListening) {
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
            } catch (err) { console.error(err); isListening = false; handleToggleMic(); }
        } else {
            if (mediaRecorder) mediaRecorder.stop();
        }
    }

    textarea.addEventListener('input', autoResize);
    textarea.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendText(); } });
    sendBtn.addEventListener('click', handleSendText);
    micBtn.addEventListener('click', handleToggleMic);
    
    // Init
    autoResize();
    loadHistory(); // 🔥 Load previous chat on startup
    setInterval(pollResults, 1000);
});