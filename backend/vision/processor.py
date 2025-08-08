"""
Vision Processor for Omi Companion App
Handles computer vision tasks like object detection, face recognition, and OCR
"""
import asyncio
import logging
import numpy as np
from typing import Optional, List, Dict, Any
from datetime import datetime
import cv2
import mediapipe as mp
import os

logger = logging.getLogger(__name__)

class VisionProcessor:
    """Handles computer vision processing tasks"""
    
    def __init__(self):
        self.mp_face_detection = mp.solutions.face_detection
        self.mp_hands = mp.solutions.hands
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        
        # Initialize MediaPipe solutions
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Processing state
        self.is_processing = False
        self.frame_queue = asyncio.Queue(maxsize=10)
        
        # Statistics
        self.stats = {
            "frames_processed": 0,
            "faces_detected": 0,
            "objects_detected": 0,
            "gestures_detected": 0,
            "errors": 0,
            "last_activity": None
        }
    
    async def initialize(self):
        """Initialize the vision processor"""
        try:
            logger.info("👁️  Initializing Vision Processor...")
            # Create data directories
            os.makedirs("data/images", exist_ok=True)
            os.makedirs("data/frames", exist_ok=True)
            logger.info("✅ Vision processor initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing vision processor: {e}")
            raise
    
    async def process_frame_queue(self):
        """Process frames from the queue"""
        if self.frame_queue.empty():
            return
        
        try:
            frame = await self.frame_queue.get()
            if frame is not None:
                await self.process_frame(frame)
                self.stats["frames_processed"] += 1
                self.stats["last_activity"] = datetime.now()
        except Exception as e:
            logger.error(f"❌ Error processing frame: {e}")
            self.stats["errors"] += 1
    
    async def process_frame(self, frame: np.ndarray):
        """Process a single frame"""
        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process face detection
            face_results = self.face_detection.process(rgb_frame)
            detections = {}
            
            if face_results.detections:
                self.stats["faces_detected"] += len(face_results.detections)
                detections["faces"] = []
                for detection in face_results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    detections["faces"].append({
                        "bbox": [bbox.xmin, bbox.ymin, bbox.width, bbox.height],
                        "confidence": detection.score[0]
                    })
            
            # Process hand detection
            hand_results = self.hands.process(rgb_frame)
            if hand_results.multi_hand_landmarks:
                self.stats["gestures_detected"] += len(hand_results.multi_hand_landmarks)
                detections["hands"] = []
                for hand_landmarks in hand_results.multi_hand_landmarks:
                    landmarks = []
                    for landmark in hand_landmarks.landmark:
                        landmarks.append([landmark.x, landmark.y, landmark.z])
                    detections["hands"].append({"landmarks": landmarks})
            
            # Process pose detection
            pose_results = self.pose.process(rgb_frame)
            
            # Save frame if detections are found or periodically
            if detections or self.stats["frames_processed"] % 30 == 0:  # Save every 30 frames or when detections found
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if detections:
                    filename = f"frame_detections_{timestamp}.jpg"
                    await self.save_frame_with_detections(frame, detections, filename)
                else:
                    filename = f"frame_{timestamp}.jpg"
                    await self.save_frame(frame, filename)
            
        except Exception as e:
            logger.error(f"❌ Error in frame processing: {e}")
            self.stats["errors"] += 1
    
    async def add_frame(self, frame: np.ndarray):
        """Add a frame to the processing queue"""
        try:
            if not self.frame_queue.full():
                await self.frame_queue.put(frame)
        except Exception as e:
            logger.error(f"❌ Error adding frame to queue: {e}")
    
    async def save_frame(self, frame: np.ndarray, filename: str = None) -> str:
        """Save a frame as an image"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"frame_{timestamp}.jpg"
            
            # Create data directory if it doesn't exist
            os.makedirs("data/images", exist_ok=True)
            filepath = f"data/images/{filename}"
            
            # Save image
            success = cv2.imwrite(filepath, frame)
            if success:
                logger.info(f"📸 Frame saved: {filepath}")
                return filepath
            else:
                logger.error(f"❌ Failed to save frame: {filepath}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Error saving frame: {e}")
            return ""
    
    async def save_frame_with_detections(self, frame: np.ndarray, detections: Dict[str, Any] = None, filename: str = None) -> str:
        """Save a frame with detection overlays"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"frame_detections_{timestamp}.jpg"
            
            # Create a copy of the frame for drawing
            annotated_frame = frame.copy()
            
            # Draw detections if provided
            if detections:
                # Draw face detections
                if "faces" in detections:
                    for face in detections["faces"]:
                        bbox = face.get("bbox", [])
                        if len(bbox) == 4:
                            x, y, w, h = bbox
                            cv2.rectangle(annotated_frame, (int(x), int(y)), (int(x+w), int(y+h)), (0, 255, 0), 2)
                            cv2.putText(annotated_frame, "Face", (int(x), int(y)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Draw hand detections
                if "hands" in detections:
                    for hand in detections["hands"]:
                        landmarks = hand.get("landmarks", [])
                        for landmark in landmarks:
                            x, y = int(landmark[0]), int(landmark[1])
                            cv2.circle(annotated_frame, (x, y), 3, (255, 0, 0), -1)
            
            # Save annotated frame
            return await self.save_frame(annotated_frame, filename)
            
        except Exception as e:
            logger.error(f"❌ Error saving frame with detections: {e}")
            return ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self.stats.copy()
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            self.face_detection.close()
            self.hands.close()
            self.pose.close()
            logger.info("✅ Vision processor cleaned up")
        except Exception as e:
            logger.error(f"❌ Error cleaning up vision processor: {e}")
