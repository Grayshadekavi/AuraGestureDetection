/* ==========================================================================
   AuraGesture - Core Client Application Script
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // --- State Variables ---
    let pollingInterval = null;
    let chartInstance = null;
    let lastLockedGesture = "Unknown";
    let lastSpokenGesture = "";
    
    // Voice Settings
    let currentVoiceMode = 'browser'; // 'browser' | 'backend' | 'muted'
    let selectedSpeechVoice = null;
    let speechRate = 1.0;
    
    // Telemetry storage for Chart.js
    const maxChartDataPoints = 30;
    const chartLabels = Array.from({length: maxChartDataPoints}, (_, i) => "");
    const chartData = Array(maxChartDataPoints).fill(0);

    // --- DOM Elements ---
    const elements = {
        webcamImage: document.getElementById('webcamImage'),
        cameraPlaceholder: document.getElementById('cameraPlaceholder'),
        scanningLine: document.getElementById('scanningLine'),
        initCameraBtn: document.getElementById('initCameraBtn'),
        toggleCameraBtn: document.getElementById('toggleCameraBtn'),
        cameraToggleIcon: document.getElementById('cameraToggleIcon'),
        cameraToggleText: document.getElementById('cameraToggleText'),
        screenshotBtn: document.getElementById('screenshotBtn'),
        
        // Stats
        cameraStatusBadge: document.getElementById('cameraStatusBadge'),
        cameraPulse: document.getElementById('cameraPulse'),
        cameraStatusText: document.getElementById('cameraStatusText'),
        liveFPS: document.getElementById('liveFPS'),
        streamTypeLabel: document.getElementById('streamTypeLabel'),
        
        // Active Prediction Elements
        activeGestureText: document.getElementById('activeGestureText'),
        gestureIcon: document.getElementById('gestureIcon'),
        gestureIconBox: document.getElementById('gestureIconBox'),
        confidenceValue: document.getElementById('confidenceValue'),
        confidenceProgressBar: document.getElementById('confidenceProgressBar'),
        
        // History & Screenshot Gallery
        historyLogList: document.getElementById('historyLogList'),
        emptyHistoryPlaceholder: document.getElementById('emptyHistoryPlaceholder'),
        historyItemsContainer: document.getElementById('historyItemsContainer'),
        clearHistoryBtn: document.getElementById('clearHistoryBtn'),
        screenshotDrawer: document.getElementById('screenshotDrawer'),
        galleryContainer: document.getElementById('galleryContainer'),
        closeGalleryBtn: document.getElementById('closeGalleryBtn'),
        
        // Settings Modal
        voiceMenuButton: document.getElementById('voiceMenuButton'),
        activeVoiceMode: document.getElementById('activeVoiceMode'),
        btnVoiceBrowser: document.getElementById('btnVoiceBrowser'),
        btnVoiceBackend: document.getElementById('btnVoiceBackend'),
        btnVoiceMuted: document.getElementById('btnVoiceMuted'),
        selectVoice: document.getElementById('selectVoice'),
        rangeVoiceRate: document.getElementById('rangeVoiceRate'),
        lblVoiceRate: document.getElementById('lblVoiceRate')
    };

    // --- FontAwesome Icon Mapping per Gesture ---
    const gestureIcons = {
        "Hello": { icon: "fa-hand", colorClass: "active-glow" },
        "Stop": { icon: "fa-hand-back-fist", colorClass: "active-glow-alt" },
        "Yes": { icon: "fa-hand-fist", colorClass: "active-glow" },
        "No": { icon: "fa-hand-point-up", colorClass: "active-glow-alt" },
        "Peace": { icon: "fa-hand-peace", colorClass: "active-glow" },
        "OK": { icon: "fa-circle-check", colorClass: "active-glow" },
        "Thumbs Up": { icon: "fa-thumbs-up", colorClass: "active-glow" },
        "Thumbs Down": { icon: "fa-thumbs-down", colorClass: "active-glow-alt" },
        "I Love You": { icon: "fa-heart", colorClass: "active-glow-alt" },
        "Thanks": { icon: "fa-hands-praying", colorClass: "active-glow" },
        "How are you": { icon: "fa-comments", colorClass: "active-glow" },
        "Where are you going?": { icon: "fa-route", colorClass: "active-glow" },
        "Water": { icon: "fa-droplet", colorClass: "active-glow" },
        "Toilet": { icon: "fa-restroom", colorClass: "active-glow-alt" },
        "Please": { icon: "fa-handshake", colorClass: "active-glow" },
        "Food": { icon: "fa-utensils", colorClass: "active-glow" },
        "Medicine": { icon: "fa-pills", colorClass: "active-glow-alt" },
        "Read": { icon: "fa-book-open", colorClass: "active-glow" },
        "Sleep": { icon: "fa-bed", colorClass: "active-glow-alt" },
        "Emergency": { icon: "fa-triangle-exclamation", colorClass: "active-glow-alt" },
        "Money": { icon: "fa-dollar-sign", colorClass: "active-glow" },
        "Attention": { icon: "fa-circle-exclamation", colorClass: "active-glow-alt" },
        "Happy": { icon: "fa-face-smile", colorClass: "active-glow" },
        "Question": { icon: "fa-circle-question", colorClass: "active-glow-alt" },
        "Good Morning": { icon: "fa-sun", colorClass: "active-glow" },
        "Unknown": { icon: "fa-question", colorClass: "" },
        "No Hand": { icon: "fa-hand-slash", colorClass: "" }
    };

    // --- Web Speech API (Browser TTS) Initialization ---
    function initializeBrowserVoices() {
        if ('speechSynthesis' in window) {
            // Function to populate voice select element
            const populateVoices = () => {
                const voices = window.speechSynthesis.getVoices();
                elements.selectVoice.innerHTML = '<option value="default">Default System Voice</option>';
                
                voices.forEach((voice, index) => {
                    const option = document.createElement('option');
                    option.value = index;
                    option.textContent = `${voice.name} (${voice.lang})`;
                    
                    // Prioritize standard English voices
                    if (voice.lang.includes('en-US') || voice.lang.includes('en-GB')) {
                        if (voice.name.toLowerCase().includes('google') || voice.name.toLowerCase().includes('zira') || voice.name.toLowerCase().includes('samantha')) {
                            option.selected = true;
                            selectedSpeechVoice = voice;
                        }
                    }
                    elements.selectVoice.appendChild(option);
                });
            };

            populateVoices();
            if (window.speechSynthesis.onvoiceschanged !== undefined) {
                window.speechSynthesis.onvoiceschanged = populateVoices;
            }
        } else {
            console.warn("Browser Speech Synthesis not supported in this client.");
            elements.btnVoiceBrowser.classList.add('disabled');
            setVoiceMode('backend'); // Default fallback to server pyttsx3
        }
    }

    // --- Text-to-Speech Engine Core ---
    function speakPhrase(phrase) {
        if (currentVoiceMode === 'muted' || !phrase) return;
        
        if (currentVoiceMode === 'browser' && 'speechSynthesis' in window) {
            // Cancel any current speaking to announce new state immediately
            window.speechSynthesis.cancel();
            
            const utterance = new SpeechSynthesisUtterance(phrase);
            utterance.rate = speechRate;
            
            // Apply selected voice
            const voices = window.speechSynthesis.getVoices();
            const voiceVal = elements.selectVoice.value;
            if (voiceVal !== 'default' && voices[voiceVal]) {
                utterance.voice = voices[voiceVal];
            } else if (selectedSpeechVoice) {
                utterance.voice = selectedSpeechVoice;
            }
            
            window.speechSynthesis.speak(utterance);
        } else if (currentVoiceMode === 'backend') {
            // Send request to Flask backend to speak in background thread
            fetch('/speak', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: phrase })
            }).catch(err => console.error("Failed to call backend voice engine:", err));
        }
    }

    // --- Chart.js Real-time Telemetry Setup ---
    function initializeChart() {
        const ctx = document.getElementById('confidenceChart').getContext('2d');
        
        // Define clean custom gradient fill
        const gradient = ctx.createLinearGradient(0, 0, 0, 150);
        gradient.addColorStop(0, 'rgba(0, 240, 240, 0.25)');
        gradient.addColorStop(1, 'rgba(0, 240, 240, 0.0)');

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: [{
                    label: 'Confidence (%)',
                    data: chartData,
                    borderColor: '#00f0f0',
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    fill: true,
                    backgroundColor: gradient,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: true }
                },
                scales: {
                    x: { display: false },
                    y: {
                        min: 0,
                        max: 100,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                        },
                        ticks: {
                            color: '#a39eb9',
                            font: { size: 9 },
                            stepSize: 25
                        }
                    }
                }
            }
        });
    }

    // --- Update Chart Telemetry Data ---
    function updateChartTelemetry(newConfidence) {
        if (!chartInstance) return;
        
        // Shift old points and append new
        chartData.shift();
        chartData.push(newConfidence);
        
        chartInstance.update('none'); // update without animations for super fast rendering
    }

    // --- Toggle Camera Feed (Client Request) ---
    function toggleWebcam(forceAction = null) {
        let action = '';
        if (forceAction) {
            action = forceAction;
        } else {
            const isOffline = elements.cameraStatusText.textContent.includes('Offline');
            action = isOffline ? 'start' : 'stop';
        }

        fetch('/toggle_camera', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'started') {
                setCameraUIActive(true);
            } else {
                setCameraUIActive(false);
            }
        })
        .catch(err => console.error("Error setting camera state:", err));
    }

    // --- Set UI elements to active camera state ---
    function setCameraUIActive(isActive) {
        if (isActive) {
            // Update Image source to MJPEG stream
            elements.webcamImage.src = '/video_feed?t=' + new Date().getTime();
            elements.webcamImage.classList.remove('d-none');
            elements.scanningLine.classList.remove('d-none');
            elements.cameraPlaceholder.classList.add('d-none');
            
            // Update buttons & status badges
            elements.cameraPulse.className = 'pulse-dot bg-success';
            elements.cameraStatusText.textContent = 'Camera Active';
            elements.cameraToggleIcon.className = 'fa-solid fa-video me-2 text-magenta';
            elements.cameraToggleText.textContent = 'Stop Camera';
            elements.toggleCameraBtn.classList.add('active');
            elements.screenshotBtn.disabled = false;
            elements.streamTypeLabel.textContent = "DETECTION LIVE";
            elements.streamTypeLabel.className = "badge bg-magenta-glow py-1 px-2 rounded-pill font-monospace";
            
            // Start Polling Telemetry Data
            startPolling();
        } else {
            // Reset image source
            elements.webcamImage.src = '';
            elements.webcamImage.classList.add('d-none');
            elements.scanningLine.classList.add('d-none');
            elements.cameraPlaceholder.classList.remove('d-none');
            
            // Update buttons & status badges
            elements.cameraPulse.className = 'pulse-dot bg-danger';
            elements.cameraStatusText.textContent = 'Camera Offline';
            elements.cameraToggleIcon.className = 'fa-solid fa-video-slash me-2';
            elements.cameraToggleText.textContent = 'Start Camera';
            elements.toggleCameraBtn.classList.remove('active');
            elements.screenshotBtn.disabled = true;
            elements.streamTypeLabel.textContent = "RAW FEED";
            elements.streamTypeLabel.className = "badge bg-secondary-glow py-1 px-2 rounded-pill font-monospace";
            
            // Stop Polling Telemetry Data
            stopPolling();
            resetTelemetryUI();
        }
    }

    // --- Reset telemetry cards when camera offline ---
    function resetTelemetryUI() {
        elements.liveFPS.textContent = "0.0";
        elements.activeGestureText.textContent = "No Hand";
        elements.confidenceValue.textContent = "0%";
        elements.confidenceProgressBar.style.width = "0%";
        
        // Reset Chart points
        chartData.fill(0);
        if (chartInstance) chartInstance.update();
        
        // Clear Active Visual Card Glows
        elements.gestureIconBox.className = "gesture-icon-avatar";
        elements.gestureIcon.className = "fa-solid fa-hand-slash";
        
        lastLockedGesture = "Unknown";
    }

    // --- Polling Data Loop ---
    function startPolling() {
        if (pollingInterval) return;
        
        // Poll every 100ms for fresh prediction updates (highly responsive!)
        pollingInterval = setInterval(() => {
            fetch('/prediction_data')
                .then(res => res.json())
                .then(data => {
                    updateTelemetryUI(data);
                })
                .catch(err => console.error("Error polling telemetry data:", err));
        }, 100);
    }

    function stopPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    // --- Update Telemetry UI elements based on polled data ---
    function updateTelemetryUI(data) {
        // 1. Update live performance markers
        elements.liveFPS.textContent = data.fps;
        
        // 2. Active gesture classifications
        const gesture = data.has_hand ? data.gesture : "No Hand";
        const confidence = data.has_hand ? data.confidence : 0;
        
        elements.activeGestureText.textContent = gesture;
        elements.confidenceValue.textContent = `${confidence}%`;
        elements.confidenceProgressBar.style.width = `${confidence}%`;
        
        // 3. Match visual theme accent and icon
        const iconConfig = gestureIcons[gesture] || gestureIcons["Unknown"];
        elements.gestureIcon.className = `fa-solid ${iconConfig.icon}`;
        elements.gestureIconBox.className = `gesture-icon-avatar ${iconConfig.colorClass}`;
        
        if (gesture === "Stop" || gesture === "Thumbs Down" || gesture === "No") {
            elements.confidenceProgressBar.className = "progress-bar progress-bar-glow bg-magenta";
        } else {
            elements.confidenceProgressBar.className = "progress-bar progress-bar-glow bg-cyan";
        }

        // 4. Trigger asynchronous speech when gesture changes state
        if (data.has_hand && gesture !== "Unknown" && gesture !== lastLockedGesture) {
            // Lock tracking update
            lastLockedGesture = gesture;
            
            // Prevent talking overlaps if gesture matches last spoken immediately (anti-stutter)
            if (gesture !== lastSpokenGesture) {
                lastSpokenGesture = gesture;
                speakPhrase(gesture);
            }
        } else if (!data.has_hand) {
            lastLockedGesture = "No Hand";
        }
        
        // 5. Update timeline data chart
        updateChartTelemetry(confidence);
        
        // 6. Update Gesture History list
        updateHistoryList(data.history);
    }

    // --- Update History List Panel ---
    function updateHistoryList(historyData) {
        if (!historyData || historyData.length === 0) {
            elements.emptyHistoryPlaceholder.classList.remove('d-none');
            if (elements.historyItemsContainer) {
                elements.historyItemsContainer.innerHTML = '';
                elements.historyItemsContainer.dataset.hash = '';
            }
            return;
        }

        elements.emptyHistoryPlaceholder.classList.add('d-none');
        
        // Render up to 10 latest items smoothly
        const renderData = historyData.slice(0, 10);
        
        const newHtml = renderData.map(item => {
            return `
                <div class="history-item">
                    <div>
                        <i class="fa-solid fa-clock me-2 text-cyan"></i>
                        <span class="history-name">${item.gesture}</span>
                    </div>
                    <span class="history-time">${item.timestamp}</span>
                </div>
            `;
        }).join('');
        
        const hash = (str) => {
            let h = 0;
            for (let i = 0; i < str.length; i++) {
                h = 31 * h + str.charCodeAt(i);
            }
            return h;
        };
        
        const newHashVal = hash(newHtml).toString();
        if (elements.historyItemsContainer) {
            if (elements.historyItemsContainer.dataset.hash !== newHashVal) {
                elements.historyItemsContainer.innerHTML = newHtml;
                elements.historyItemsContainer.dataset.hash = newHashVal;
            }
        }
    }

    // --- Capture Visual Screenshot ---
    function captureScreenshot() {
        if (elements.screenshotBtn.disabled) return;
        
        fetch('/capture_screenshot', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    addScreenshotToGallery(data.img_url);
                } else {
                    alert("Failed to capture frame: " + data.error);
                }
            })
            .catch(err => console.error("Error capturing screenshot:", err));
    }

    // --- Dynamic Screenshot Gallery Drawer Updates ---
    function addScreenshotToGallery(imgUrl) {
        elements.screenshotDrawer.classList.remove('d-none');
        
        const card = document.createElement('div');
        card.className = 'screenshot-thumb-box';
        card.innerHTML = `
            <img src="${imgUrl}" class="screenshot-thumb" alt="Captured Frame thumbnail">
            <div class="screenshot-download-overlay">
                <a href="${imgUrl}" download class="btn-dl-screenshot" title="Download Image file">
                    <i class="fa-solid fa-download"></i>
                </a>
            </div>
        `;
        
        // Prepend to show latest screenshot first
        elements.galleryContainer.insertBefore(card, elements.galleryContainer.firstChild);
        
        // Scroll gallery to start
        elements.galleryContainer.scrollLeft = 0;
    }

    // --- Sound/Voice Settings Handlers ---
    function setVoiceMode(mode) {
        currentVoiceMode = mode;
        
        // Update active badge selectors
        elements.btnVoiceBrowser.classList.remove('active');
        elements.btnVoiceBackend.classList.remove('active');
        elements.btnVoiceMuted.classList.remove('active');
        
        if (mode === 'browser') {
            elements.btnVoiceBrowser.classList.add('active');
            elements.activeVoiceMode.textContent = "Browser";
            elements.voiceMenuButton.className = "btn btn-action-glass dropdown-toggle";
            
            // Notify backend to mute its TTS
            fetch('/toggle_voice', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'mute'}) });
        } else if (mode === 'backend') {
            elements.btnVoiceBackend.classList.add('active');
            elements.activeVoiceMode.textContent = "Backend";
            elements.voiceMenuButton.className = "btn btn-action-glass dropdown-toggle border-magenta";
            
            // Notify backend to enable SAPI5/pyttsx3
            fetch('/toggle_voice', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'unmute'}) });
        } else {
            elements.btnVoiceMuted.classList.add('active');
            elements.activeVoiceMode.textContent = "Muted";
            elements.voiceMenuButton.className = "btn btn-action-glass dropdown-toggle border-danger text-danger";
            
            // Notify backend to mute its TTS
            fetch('/toggle_voice', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'mute'}) });
        }
    }

    // --- Bind DOM Interactions & Triggers ---
    function bindInterfaceEvents() {
        // Toggle Webcam Click
        elements.initCameraBtn.addEventListener('click', () => toggleWebcam('start'));
        elements.toggleCameraBtn.addEventListener('click', () => toggleWebcam());
        
        // Capture frame Click
        elements.screenshotBtn.addEventListener('click', captureScreenshot);
        
        // Close screenshot gallery
        elements.closeGalleryBtn.addEventListener('click', () => {
            elements.screenshotDrawer.classList.add('d-none');
            elements.galleryContainer.innerHTML = '';
        });
        
        // Clear log
        elements.clearHistoryBtn.addEventListener('click', () => {
            fetch('/toggle_camera', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'stop' })
            }).then(() => {
                // Restart to clean stabilizer memory
                toggleWebcam('start');
            });
        });

        // Speech selector switches
        elements.btnVoiceBrowser.addEventListener('click', () => setVoiceMode('browser'));
        elements.btnVoiceBackend.addEventListener('click', () => setVoiceMode('backend'));
        elements.btnVoiceMuted.addEventListener('click', () => setVoiceMode('muted'));

        // Settings adjustments
        elements.rangeVoiceRate.addEventListener('input', (e) => {
            speechRate = parseFloat(e.target.value);
            elements.lblVoiceRate.textContent = `${speechRate.toFixed(1)}x`;
        });
        
        // Keyboard Hotkeys
        document.addEventListener('keydown', (e) => {
            // Ignore keystrokes inside configuration input fields
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            const key = e.key.toLowerCase();
            if (key === ' ') {
                e.preventDefault(); // Prevent page scrolling
                toggleWebcam();
            } else if (key === 's') {
                captureScreenshot();
            } else if (key === 'm') {
                // Rotate Voice modes
                if (currentVoiceMode === 'browser') setVoiceMode('backend');
                else if (currentVoiceMode === 'backend') setVoiceMode('muted');
                else setVoiceMode('browser');
            } else if (key === 'q') {
                // Escape key or Q shuts camera safely
                toggleWebcam('stop');
            }
        });
    }

    // --- Bootstrapper Initialization ---
    function initialize() {
        initializeChart();
        initializeBrowserVoices();
        bindInterfaceEvents();
        
        // Query current state from server on load to check if camera is already running
        fetch('/prediction_data')
            .then(res => res.json())
            .then(data => {
                if (data.is_camera_active) {
                    setCameraUIActive(true);
                    setVoiceMode(data.voice_enabled ? 'backend' : 'browser');
                } else {
                    setCameraUIActive(false);
                }
            })
            .catch(() => setCameraUIActive(false));
    }

    // Run launcher
    initialize();
});
