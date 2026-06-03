import collections
import time

class GestureStabilizer:
    def __init__(self, window_size=10, min_confidence=0.75, lock_consecutive_frames=5, cooldown_seconds=0.8):
        """
        Stabilizes raw gesture predictions over time using a rolling window,
        minimum confidence thresholds, frame repetition checks, and cooldown timers.
        """
        self.window_size = window_size
        self.min_confidence = min_confidence
        self.lock_consecutive_frames = lock_consecutive_frames
        self.cooldown_seconds = cooldown_seconds
        
        # History queue of raw predictions
        self.prediction_window = collections.deque(maxlen=window_size)
        
        # Active locked gesture state
        self.locked_gesture = "Unknown"
        self.smoothed_confidence = 0.0
        
        # Cooldown state tracking
        self.last_transition_time = 0.0
        
        # Tracker for consecutive agreement of a new candidate gesture
        self.candidate_gesture = "Unknown"
        self.candidate_counter = 0
        
        # History list of officially locked transitions (for UI log)
        # Format: {"gesture": name, "timestamp": str}
        self.gesture_history = []

    def add_prediction(self, raw_gesture, raw_confidence):
        """
        Processes a raw prediction frame-by-frame and applies stabilization rules.
        Returns a tuple (locked_gesture, smoothed_confidence, was_updated)
        """
        current_time = time.time()
        was_updated = False
        
        # 1. Update rolling window
        # Ignore "No Hand" when drawing rolling window but keep it for immediate state if needed
        # We append all raw frames to make sure we detect state changes rapidly
        self.prediction_window.append(raw_gesture)
        
        # 2. Compute Mode (most common gesture in window) and its frequency (confidence)
        if len(self.prediction_window) == 0:
            return self.locked_gesture, 0.0, False
            
        counter = collections.Counter(self.prediction_window)
        dominant_gesture, count = counter.most_common(1)[0]
        smoothed_conf = count / len(self.prediction_window)
        
        # Update current smoothed confidence level for live display
        self.smoothed_confidence = smoothed_conf
        
        # 3. Check for stable transitions to new gestures
        # A new gesture is considered a "candidate" if it's different from our current locked one
        if dominant_gesture != self.locked_gesture:
            # If we match the same candidate as the previous frame, increment counter
            if dominant_gesture == self.candidate_gesture:
                self.candidate_counter += 1
            else:
                self.candidate_gesture = dominant_gesture
                self.candidate_counter = 1
                
            # Requirements to officially lock a new gesture:
            # 1. Candidate must be stable for consecutive frames
            # 2. Smoothed confidence must meet the minimum threshold
            # 3. Cooldown timer since last transition must have expired (to prevent rapid flutter)
            is_stable = self.candidate_counter >= self.lock_consecutive_frames
            is_confident = smoothed_conf >= self.min_confidence
            cooldown_expired = (current_time - self.last_transition_time) >= self.cooldown_seconds
            
            # Special fast-path for "No Hand" or "Unknown" to clear the screen instantly
            if dominant_gesture in ["No Hand", "Unknown"]:
                is_stable = True
                is_confident = True
                cooldown_expired = True
                
            if is_stable and is_confident and cooldown_expired:
                # Store the change
                old_gesture = self.locked_gesture
                self.locked_gesture = dominant_gesture
                self.last_transition_time = current_time
                self.candidate_counter = 0
                was_updated = True
                
                # Add to history (avoid duplicates in sequence, only add meaningful gestures)
                if self.locked_gesture not in ["No Hand", "Unknown"]:
                    timestamp = time.strftime("%H:%M:%S")
                    # Prepend to keep latest first in history
                    self.gesture_history.insert(0, {
                        "gesture": self.locked_gesture,
                        "timestamp": timestamp
                    })
                    # Limit history log size to 25 items
                    if len(self.gesture_history) > 25:
                        self.gesture_history.pop()
        else:
            # If candidate matches locked gesture, reset candidate tracking
            self.candidate_counter = 0
            self.candidate_gesture = self.locked_gesture
            
        return self.locked_gesture, self.smoothed_confidence, was_updated

    def get_history(self):
        """Returns the list of recently locked gestures."""
        return self.gesture_history

    def clear(self):
        """Clears state."""
        self.prediction_window.clear()
        self.locked_gesture = "Unknown"
        self.smoothed_confidence = 0.0
        self.candidate_counter = 0
        self.candidate_gesture = "Unknown"
