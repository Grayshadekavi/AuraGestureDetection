import numpy as np

class GestureDetector:
    def __init__(self):
        # Joint mapping for normal fingers: (TIP, PIP)
        # Index: 8, 6
        # Middle: 12, 10
        # Ring: 16, 14
        # Pinky: 20, 18
        self.fingers = {
            'index': (8, 6),
            'middle': (12, 10),
            'ring': (16, 14),
            'pinky': (20, 18)
        }

    def _get_distance_2d(self, pt1, pt2):
        """Calculate stable 2D Euclidean distance in the XY plane, avoiding noisy Z axis."""
        return np.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)

    def detect_gesture(self, hand_landmarks, handedness="Right"):
        """
        Detects hand gesture based on 21 2D hand landmarks in XY plane.
        Returns a tuple of (gesture_name, confidence_value).
        """
        if not hand_landmarks:
            return "No Hand", 0.0

        # Convert landmarks to simple list of [x, y] coordinates in 2D
        pts = [[lm.x, lm.y] for lm in hand_landmarks.landmark]
        
        # Wrist is landmark 0
        wrist = pts[0]
        
        # Palm scale factor (knuckle width between Index MCP landmark 5 and Pinky MCP landmark 17)
        palm_width = self._get_distance_2d(pts[5], pts[17])
        if palm_width < 1e-4:
            palm_width = 1e-4

        # 1. Determine states of 4 fingers (Index, Middle, Ring, Pinky)
        # Using the Knuckle-to-Tip Distance Rule:
        # A finger is extended if its TIP is far from its MCP (knuckle) joint.
        # This completely bypasses the noisy and easily-occluded PIP joints.
        fingers_extended = {}
        knuckle_tips = {
            'index': (5, 8),
            'middle': (9, 12),
            'ring': (13, 16),
            'pinky': (17, 20)
        }
        # Customized anatomical thresholds for each finger
        thresholds = {
            'index': 0.65,
            'middle': 0.65,
            'ring': 0.65,
            'pinky': 0.60
        }
        for name, joints in knuckle_tips.items():
            mcp_idx, tip_idx = joints
            d_tip_mcp = self._get_distance_2d(pts[tip_idx], pts[mcp_idx]) / palm_width
            fingers_extended[name] = d_tip_mcp > thresholds[name]

        # 2. Determine Thumb extended state
        # Distance between Thumb TIP (4) and Index MCP (5) normalized by palm width
        thumb_tip = pts[4]
        index_mcp = pts[5]
        pinky_mcp = pts[17]
        
        thumb_index_dist = self._get_distance_2d(thumb_tip, index_mcp) / palm_width
        thumb_pinky_dist = self._get_distance_2d(thumb_tip, pinky_mcp) / palm_width
        
        # A thumb is extended if it is far from the index knuckle (>0.30)
        thumb_extended = thumb_index_dist > 0.30

        # 3. Fingertip coordinates for detailed gesture metrics
        t_tip = pts[4]
        i_tip = pts[8]
        m_tip = pts[12]
        r_tip = pts[16]
        p_tip = pts[20]

        # Calculate distances between adjacent fingertips to check finger spread
        # Used to distinguish "Hello" (spread) from "Stop" (closed)
        spread_dist = (self._get_distance_2d(i_tip, m_tip) + 
                       self._get_distance_2d(m_tip, r_tip) + 
                       self._get_distance_2d(r_tip, p_tip)) / palm_width

        # Check proximity of Index Tip and Thumb Tip for the "OK" gesture
        ok_pinch_dist = self._get_distance_2d(t_tip, i_tip) / palm_width

        # Calculate coordinates for pinched Food gesture
        pinch_middle = self._get_distance_2d(t_tip, m_tip) / palm_width
        pinch_ring = self._get_distance_2d(t_tip, r_tip) / palm_width
        pinch_pinky = self._get_distance_2d(t_tip, p_tip) / palm_width

        # Calculate average pinch distance to handle MediaPipe landmark occlusion noise
        avg_pinch_dist = (ok_pinch_dist + pinch_middle + pinch_ring + pinch_pinky) / 4.0

        # Classify based on logical patterns
        
        # A. Food / Eat (Pinched hand shape: all 5 fingertips touching in a cone)
        # Check if at least 3 of the finger tips are in close proximity to the thumb tip (< 0.52)
        # AND the average pinch distance is small (< 0.50). Bypasses rigid binary extensions.
        # We also check pinch_pinky < 0.52 to ensure the hand is in a pinch rather than a fist.
        pinch_count = sum([1 for d in [ok_pinch_dist, pinch_middle, pinch_ring, pinch_pinky] if d < 0.52])
        if pinch_count >= 3 and avg_pinch_dist < 0.50 and pinch_pinky < 0.52:
            return "Food", 0.98

        # B. OK Gesture: Index and Thumb pinching (touching), others extended.
        # We require a real pinch distance check to prevent falsely intercepting "Emergency"
        if ok_pinch_dist < 0.55 and not fingers_extended['index'] and fingers_extended['middle'] and fingers_extended['ring'] and fingers_extended['pinky']:
            return "OK", 0.98

        # C. Money / Cost (Thumb and Middle finger pinched, Index, Ring, Pinky extended)
        if pinch_middle < 0.40 and fingers_extended['index'] and not fingers_extended['middle'] and fingers_extended['ring'] and fingers_extended['pinky']:
            return "Money", 0.98

        # D. Attention (Thumb and Pinky pinched, Index, Middle, Ring extended)
        if pinch_pinky < 0.45 and fingers_extended['index'] and fingers_extended['middle'] and fingers_extended['ring'] and not fingers_extended['pinky']:
            return "Attention", 0.98

        # E. Read / Book (ASL 'Book' shape: Index, Middle, and Pinky extended; Ring and Thumb folded)
        if fingers_extended['index'] and fingers_extended['middle'] and fingers_extended['pinky'] and not thumb_extended and not fingers_extended['ring']:
            d_ring_wrist = self._get_distance_2d(pts[16], wrist)
            d_middle_wrist = self._get_distance_2d(pts[12], wrist)
            d_pinky_wrist = self._get_distance_2d(pts[20], wrist)
            # The ring finger is folded if it is significantly closer to the wrist than the middle & pinky
            if d_ring_wrist < d_middle_wrist * 0.92 and d_ring_wrist < d_pinky_wrist * 0.95:
                return "Read", 0.98

        # F. Emergency / Danger (Index folded; Thumb, Middle, Ring, Pinky extended)
        if thumb_extended and fingers_extended['middle'] and fingers_extended['ring'] and fingers_extended['pinky'] and not fingers_extended['index']:
            d_index_wrist = self._get_distance_2d(pts[8], wrist)
            d_middle_wrist = self._get_distance_2d(pts[12], wrist)
            # Index is folded if it is significantly shorter than the middle finger
            if d_index_wrist < d_middle_wrist * 0.88:
                return "Emergency", 0.98

        # G. Question (Ring folded; Thumb, Index, Middle, Pinky extended)
        if thumb_extended and fingers_extended['index'] and fingers_extended['middle'] and fingers_extended['pinky'] and not fingers_extended['ring']:
            d_ring_wrist = self._get_distance_2d(pts[16], wrist)
            d_middle_wrist = self._get_distance_2d(pts[12], wrist)
            d_pinky_wrist = self._get_distance_2d(pts[20], wrist)
            if d_ring_wrist < d_middle_wrist * 0.92 and d_ring_wrist < d_pinky_wrist * 0.95:
                return "Question", 0.98

        # H. Good Morning (Pinky folded; Thumb, Index, Middle, Ring extended)
        if thumb_extended and fingers_extended['index'] and fingers_extended['middle'] and fingers_extended['ring'] and not fingers_extended['pinky']:
            return "Good Morning", 0.98

        # I. Combined Flat Palm Logic: Hello vs Stop vs Please
        # All three require Index, Middle, Ring, and Pinky to be extended.
        # This unified branch completely avoids logical overlaps and ensures 100% stable results.
        all_four_extended = fingers_extended['index'] and fingers_extended['middle'] and fingers_extended['ring'] and fingers_extended['pinky']
        if all_four_extended:
            # 1. If the thumb is curled across the palm (close to the pinky: thumb_pinky_dist <= 0.82):
            # It is strictly the "Please" gesture!
            if thumb_pinky_dist <= 0.82:
                return "Please", 0.98
            else:
                # 2. If the thumb is not curled across the palm (pointing up/out):
                # It is Hello or Stop, separated by finger spread:
                # We use the highly stable Tip-Width to Knuckle-Width Ratio
                tip_width = self._get_distance_2d(pts[8], pts[20])
                if tip_width / palm_width > 1.30:
                    return "Hello", 0.95
                else:
                    return "Stop", 0.95

        # J. How are you? (3-Finger shape: Thumb, Index, and Middle extended; Ring and Pinky folded)
        if thumb_extended and fingers_extended['index'] and fingers_extended['middle'] and not (fingers_extended['ring'] or fingers_extended['pinky']):
            return "How are you", 0.98

        # K. Peace Gesture (V-Sign)
        # Index and Middle extended, Ring and Pinky folded, Thumb folded.
        if fingers_extended['index'] and fingers_extended['middle'] and not (fingers_extended['ring'] or fingers_extended['pinky'] or thumb_extended):
            return "Peace", 0.98

        # L. Medicine / Sick (L-shape: Thumb and Index extended; Middle, Ring, Pinky folded)
        if thumb_extended and fingers_extended['index'] and not (fingers_extended['middle'] or fingers_extended['ring'] or fingers_extended['pinky']):
            return "Medicine", 0.98

        # M. Thumbs Up vs Thumbs Down
        # Only thumb extended, all other fingers folded
        if thumb_extended and not (fingers_extended['index'] or fingers_extended['middle'] or fingers_extended['ring'] or fingers_extended['pinky']):
            thumb_mcp = pts[2]
            # Check y-coordinate orientation in 2D
            if t_tip[1] < thumb_mcp[1] - 0.015:
                return "Thumbs Up", 0.98
            elif t_tip[1] > thumb_mcp[1] + 0.015:
                return "Thumbs Down", 0.98

        # N. I Love You (ILY)
        # Thumb, Index, and Pinky extended, Middle and Ring folded
        if thumb_extended and fingers_extended['index'] and fingers_extended['pinky'] and not (fingers_extended['middle'] or fingers_extended['ring']):
            return "I Love You", 0.98

        # O. Thanks (Shaka)
        # Thumb and Pinky extended, Index, Middle, Ring folded
        if thumb_extended and fingers_extended['pinky'] and not (fingers_extended['index'] or fingers_extended['middle'] or fingers_extended['ring']):
            return "Thanks", 0.98

        # P. Where are you going? (Horns shape: Index and Pinky extended; Thumb, Middle, and Ring folded)
        if fingers_extended['index'] and fingers_extended['pinky'] and not (thumb_extended or fingers_extended['middle'] or fingers_extended['ring']):
            return "Where are you going?", 0.98

        # Q. Water (W-shape: Index, Middle, and Ring extended; Thumb and Pinky folded)
        if fingers_extended['index'] and fingers_extended['middle'] and fingers_extended['ring'] and not (thumb_extended or fingers_extended['pinky']):
            return "Water", 0.98

        # R. Toilet / Washroom (Pinky extended only; Thumb, Index, Middle, Ring folded)
        if fingers_extended['pinky'] and not (thumb_extended or fingers_extended['index'] or fingers_extended['middle'] or fingers_extended['ring']):
            return "Toilet", 0.98

        # S. Sleep / Tired (ASL 'Rest' shape: Ring and Pinky extended; Thumb, Index, and Middle folded)
        if fingers_extended['ring'] and fingers_extended['pinky'] and not (thumb_extended or fingers_extended['index'] or fingers_extended['middle']):
            return "Sleep", 0.98

        # T. Happy (Thumb, Ring, Pinky extended; Index, Middle folded)
        if thumb_extended and fingers_extended['ring'] and fingers_extended['pinky'] and not (fingers_extended['index'] or fingers_extended['middle']):
            return "Happy", 0.98

        # U. No (Pointing index finger up, middle/ring/pinky folded)
        if fingers_extended['index'] and not (thumb_extended or fingers_extended['middle'] or fingers_extended['ring'] or fingers_extended['pinky']):
            return "No", 0.95

        # V. Yes (Fist)
        # All fingers folded, including thumb
        if not (thumb_extended or fingers_extended['index'] or fingers_extended['middle'] or fingers_extended['ring'] or fingers_extended['pinky']):
            return "Yes", 0.92

        # Default fallback
        return "Unknown", 0.0
