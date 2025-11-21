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
    let sessionId = 'session_' + Date.now();

    // --- Functions ---
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
        bubble.innerHTML = text.replace(/\n/g, '<br>'); // Handles newlines in markdown
        wrapper.appendChild(bubble);
        messagesContent.appendChild(wrapper);
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
    
    // --- BACKEND COMMUNICATION ---
    async function callBackend(payload) {
        const loadingId = 'loading-' + Date.now();
        const loader = document.createElement('div');
        loader.id = loadingId;
        loader.className = 'message-wrapper ai';
        loader.innerHTML = '<div class="message-bubble ai" style="color:#A8C7FA">Thinking...</div>';
        messagesContent.appendChild(loader);
        scrollContainer.scrollTop = scrollContainer.scrollHeight;

        try {
            // Sends to the Flask API endpoint defined in frontend_app.py
            const response = await fetch('/api/victim_chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...payload, session_id: sessionId })
            });
            const data = await response.json();
            document.getElementById(loadingId).remove();
            addBubble(data.reply, 'ai');
        } catch (error) {
            document.getElementById(loadingId).remove();
            addBubble("Error: Could not connect to the agent backend.", 'ai');
        }
    }
    
    // --- Event Handlers ---
    function handleSendText() {
        const text = textarea.value.trim();
        if (!text) return;
        addBubble(text, 'user');
        textarea.value = ''; autoResize();
        callBackend({ text: text });
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
                        callBackend({ audio: reader.result });
                    };
                };
                mediaRecorder.start();
            } catch (err) { console.error(err); isListening = false; }
        } else {
            if (mediaRecorder) mediaRecorder.stop();
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
});