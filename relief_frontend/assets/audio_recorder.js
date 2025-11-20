console.log("Loading Audio Recorder Script...");

let mediaRecorder;
let audioChunks = [];

window.startRecording = async () => {
    console.log("startRecording called");
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };
        
        mediaRecorder.start();
        console.log("Recording started...");
    } catch (err) {
        console.error("Error accessing microphone:", err);
        alert("Error accessing microphone. Please allow permissions.");
    }
}

window.stopRecording = () => {
    console.log("stopRecording called");
    if (!mediaRecorder) return;
    
    return new Promise(resolve => {
        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const reader = new FileReader();
            reader.readAsDataURL(audioBlob);
            reader.onloadend = () => {
                const base64data = reader.result;
                console.log("Audio converted to base64");
                
                // Find the hidden input in Reflex
                const input = document.getElementById("audio-bridge");
                
                if (input) {
                    // React/Reflex requires a specific setter for event triggering
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(input, base64data);
                    
                    // Dispatch input event to notify Reflex
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    console.log("Sent to Reflex");
                } else {
                    console.error("Error: audio-bridge input not found!");
                }
            };
        };
        mediaRecorder.stop();
    });
}