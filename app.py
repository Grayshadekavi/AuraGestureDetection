import os
import cv2
import time
import threading
import datetime
import logging
from flask import Flask, render_template, Response, jsonify, request
#python files
import mediapipe as mp
import numpy as np

# Import custom detection modules
from detector.gesture_detector import GestureDetector
from utils.gesture_stabilizer import GestureStabilizer
from utils.voice_engine import BackgroundVoiceEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Ensure assets directory exists for screenshots
ASSETS_DIR = os.path.join(app.root_path, 'static', 'assets')
os.makedirs(ASSETS_DIR, exist_ok=True)

class WebcamManager:
    def __init__(self):
        self.cap = None
        self.thread = None
        self.running = False
        self.lock = threading.Lock()
        
        # State variables
        self.latest_frame = None
        self.latest_raw_frame = None
        self.fps = 0
        self.has_hand = False
        self.active_gesture = "Unknown"
        self.confidence = 0.0
        
        # Settings
        self.voice_enabled = False  # Disabled by default on server (browser Web Speech takes priority)
        
        # Core engines
        self.detector = GestureDetector()
        self.stabilizer = GestureStabilizer(
            window_size=10,
            min_confidence=0.70,
            lock_consecutive_frames=4,
            cooldown_seconds=0.6
        )
        self.voice_engine = BackgroundVoiceEngine()
        
        # MediaPipe initialization
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=1,
            min_detection_confidence=0.70,
            min_tracking_confidence=0.70
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # Custom drawing styles for premium appearance (neon theme)
        self.landmark_style = self.mp_draw.DrawingSpec(
            color=(240, 240, 60),  # Cyan joints
            thickness=2,
            circle_radius=4
        )
        self.connection_style = self.mp_draw.DrawingSpec(
            color=(255, 255, 255),  # White skeleton lines
            thickness=2,
            circle_radius=1
        )
        
        # Start camera by default
        self.start()

    def start(self):
        """Starts the camera acquisition thread."""
        with self.lock:
            if self.running:
                return True
                
            logger.info("Starting Webcam Acquisition Thread...")
            
            # Try to open index 0 camera
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                # Fallback to index 1 if 0 is not available
                logger.warning("Camera index 0 not available. Trying index 1...")
                self.cap = cv2.VideoCapture(1)
                
            if not self.cap.isOpened():
                logger.error("Failed to open any webcam device.")
                self.cap = None
                return False
                
            # Set camera dimensions for optimal speed/performance balance
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.running = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            return True

    def stop(self):
        """Stops the thread and releases the webcam."""
        with self.lock:
            if not self.running:
                return
                
            logger.info("Stopping Webcam Acquisition Thread...")
            self.running = False
            
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
            
        with self.lock:
            if self.cap:
                self.cap.release()
                self.cap = None
            self.stabilizer.clear()
            self.active_gesture = "Unknown"
            self.confidence = 0.0
            self.fps = 0
            self.has_hand = False
            self.latest_frame = None
            self.latest_raw_frame = None
            
        logger.info("Webcam successfully closed and resources released.")

    def _capture_loop(self):
        """Background frame reading and processing loop."""
        prev_time = time.time()
        
        while self.running:
            with self.lock:
                if self.cap is None:
                    break
                ret, frame = self.cap.read()
                
            if not ret:
                time.sleep(0.01)
                continue
                
            # Keep raw frame in memory for clean screenshots (no landmarks)
            self.latest_raw_frame = frame.copy()
            
            # Mirror the frame horizontally for intuitive interaction
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            
            # Convert color space for MediaPipe (BGR -> RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process frame with MediaPipe
            results = self.hands.process(rgb_frame)
            
            raw_gesture = "No Hand"
            raw_confidence = 0.0
            hand_present = False
            
            if results.multi_hand_landmarks:
                hand_present = True
                hand_landmarks = results.multi_hand_landmarks[0]
                
                # Draw high-fidelity custom hand skeleton
                self.mp_draw.draw_landmarks(
                    frame, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS,
                    landmark_drawing_spec=self.landmark_style,
                    connection_drawing_spec=self.connection_style
                )
                
                # Extract hand labeled side (Left vs Right)
                # MediaPipe handedness gives the actual hand (which is inverted because of mirrored image)
                try:
                    handedness = results.multi_handedness[0].classification[0].label
                except:
                    handedness = "Right"
                
                # Calculate raw gesture and score
                raw_gesture, raw_confidence = self.detector.detect_gesture(hand_landmarks, handedness)
            
            # Apply stabilizer rules
            locked_gest, smoothed_conf, was_updated = self.stabilizer.add_prediction(raw_gesture, raw_confidence)
            
            # Update background variables
            with self.lock:
                self.has_hand = hand_present
                self.active_gesture = locked_gest
                self.confidence = smoothed_conf
                
                # Handle text-to-speech triggers (if server-side TTS enabled)
                if was_updated and self.voice_enabled and locked_gest not in ["No Hand", "Unknown"]:
                    self.voice_engine.speak(locked_gest)
                
                # Draw the gesture name directly on the video feed corner for reassurance
                if hand_present and locked_gest not in ["No Hand", "Unknown"]:
                    cv2.putText(
                        frame, 
                        f"Gesture: {locked_gest} ({int(smoothed_conf*100)}%)", 
                        (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.9, 
                        (255, 60, 160),  # Neon pink/magenta
                        2, 
                        cv2.LINE_AA
                    )
                
                # Encode final processed frame to JPEG bytes
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                self.latest_frame = buffer.tobytes()
                
            # Calculate FPS
            curr_time = time.time()
            time_diff = curr_time - prev_time
            prev_time = curr_time
            if time_diff > 0:
                self.fps = round(1.0 / time_diff, 1)
                
            # Prevent excessive CPU spinning
            time.sleep(0.005)

    def get_frame(self):
        """Returns the latest JPEG buffer."""
        with self.lock:
            return self.latest_frame

    def get_screenshot(self):
        """Saves current raw (unmarked) mirrored frame to assets folder."""
        with self.lock:
            if self.latest_raw_frame is None:
                return None
            frame = cv2.flip(self.latest_raw_frame, 1)  # keep mirrored for standard visual matches
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"capture_{timestamp}.jpg"
        filepath = os.path.join(ASSETS_DIR, filename)
        
        # Save frame
        cv2.imwrite(filepath, frame)
        return f"/static/assets/{filename}"

    def get_data(self):
        """Returns current state metrics."""
        with self.lock:
            return {
                "gesture": self.active_gesture,
                "confidence": round(self.confidence * 100, 1),
                "fps": self.fps if self.running else 0.0,
                "has_hand": self.has_hand,
                "history": self.stabilizer.get_history(),
                "is_camera_active": self.running,
                "voice_enabled": self.voice_enabled
            }

# Create WebcamManager Singleton instance
camera_manager = WebcamManager()

@app.route('/')
def index():
    """Renders main premium HTML panel."""
    return render_template('index.html')

def gen_video(manager):
    """Generator function that yields live processed frames."""
    while True:
        frame_bytes = manager.get_frame()
        if frame_bytes is None:
            # Yield placeholder frame or empty when camera is closed
            time.sleep(0.1)
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # cap yield at roughly 30 FPS to avoid streaming bottlenecks

@app.route('/video_feed')
def video_feed():
    """Streams live MJPEG camera feed."""
    return Response(gen_video(camera_manager),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/prediction_data')
def prediction_data():
    """Returns real-time prediction telemetry."""
    return jsonify(camera_manager.get_data())

@app.route('/toggle_camera', methods=['POST'])
def toggle_camera():
    """Starts or stops the webcam feed."""
    data = request.json or {}
    action = data.get('action')
    
    if action == 'start':
        success = camera_manager.start()
        return jsonify({"status": "started" if success else "failed"})
    elif action == 'stop':
        camera_manager.stop()
        return jsonify({"status": "stopped"})
    else:
        # Toggle current state
        if camera_manager.running:
            camera_manager.stop()
            return jsonify({"status": "stopped"})
        else:
            success = camera_manager.start()
            return jsonify({"status": "started" if success else "failed"})

@app.route('/toggle_voice', methods=['POST'])
def toggle_voice():
    """Toggles backend pyttsx3 speech manager."""
    camera_manager.voice_enabled = not camera_manager.voice_enabled
    logger.info(f"Server-side TTS Speech toggled to: {camera_manager.voice_enabled}")
    return jsonify({"voice_enabled": camera_manager.voice_enabled})

@app.route('/capture_screenshot', methods=['POST'])
def capture_screenshot():
    """Captures high resolution frame and returns url."""
    img_url = camera_manager.get_screenshot()
    if img_url:
        return jsonify({"success": True, "img_url": img_url})
    return jsonify({"success": False, "error": "Camera not active or frame empty."})

@app.route('/speak', methods=['POST'])
def speak():
    """Custom endpoint to speak raw message using backend engine."""
    data = request.json or {}
    text = data.get('text', '')
    if text:
        camera_manager.voice_engine.speak(text)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No text provided."})

# Cleanup hooks when shutting down flask server
def cleanup():
    logger.info("Cleaning up backend thread services...")
    camera_manager.stop()
    camera_manager.voice_engine.shutdown()

import atexit
atexit.register(cleanup)

if __name__ == '__main__':
    try:
        # Host on 0.0.0.0 for potential local network access (e.g. testing on mobile browser)
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        cleanup()
