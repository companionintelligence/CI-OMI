"""
System Configuration for Omi Companion App
"""
from dataclasses import dataclass
from typing import Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class SystemConfig:
    """System configuration settings"""
    
    # Ollama Configuration
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_vision_model: str = os.getenv("OLLAMA_VISION_MODEL", "moondream:1.8b-v2-fp16")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:3b")
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "30"))
    
    # BLE Configuration
    ble_device_name: str = os.getenv("BLE_DEVICE_NAME", "Omi")
    ble_scan_timeout: int = int(os.getenv("BLE_SCAN_TIMEOUT", "10"))
    ble_connection_timeout: int = int(os.getenv("BLE_CONNECTION_TIMEOUT", "10"))
    
    # Audio Configuration
    audio_sample_rate: int = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    audio_channels: int = int(os.getenv("AUDIO_CHANNELS", "1"))
    audio_buffer_size: int = int(os.getenv("AUDIO_BUFFER_SIZE", "1024"))
    whisper_model: str = os.getenv("WHISPER_MODEL", "base")
    
    # Video Configuration
    video_fps: int = int(os.getenv("VIDEO_FPS", "10"))
    video_width: int = int(os.getenv("VIDEO_WIDTH", "640"))
    video_height: int = int(os.getenv("VIDEO_HEIGHT", "480"))
    
    # AI Feature Toggles
    enable_face_recognition: bool = os.getenv("ENABLE_FACE_RECOGNITION", "true").lower() == "true"
    enable_object_detection: bool = os.getenv("ENABLE_OBJECT_DETECTION", "true").lower() == "true"
    enable_ocr: bool = os.getenv("ENABLE_OCR", "true").lower() == "true"
    enable_gesture_detection: bool = os.getenv("ENABLE_GESTURE_DETECTION", "true").lower() == "true"
    enable_emotion_analysis: bool = os.getenv("ENABLE_EMOTION_ANALYSIS", "true").lower() == "true"
    
    # Confidence Thresholds
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
    face_recognition_threshold: float = float(os.getenv("FACE_RECOGNITION_THRESHOLD", "0.8"))
    object_detection_threshold: float = float(os.getenv("OBJECT_DETECTION_THRESHOLD", "0.6"))
    
    # Storage Configuration
    database_path: str = os.getenv("DATABASE_PATH", "data/events.db")
    json_backup_path: str = os.getenv("JSON_BACKUP_PATH", "data/events_backup.json")
    face_db_path: str = os.getenv("FACE_DB_PATH", "data/face_embeddings.json")
    
    # Processing Configuration
    max_audio_queue_size: int = int(os.getenv("MAX_AUDIO_QUEUE_SIZE", "100"))
    max_video_queue_size: int = int(os.getenv("MAX_VIDEO_QUEUE_SIZE", "50"))
    processing_batch_size: int = int(os.getenv("PROCESSING_BATCH_SIZE", "10"))
    
    # Network Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    websocket_heartbeat: int = int(os.getenv("WEBSOCKET_HEARTBEAT", "30"))
    
    # Omi API Configuration
    omi_api_key: str = os.getenv("OMI_API_KEY", "")
    omi_api_url: str = os.getenv("OMI_API_URL", "https://api.omi.me")
    omi_api_timeout: int = int(os.getenv("OMI_API_TIMEOUT", "30"))
    
    # Logging Configuration
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/omi_companion.log")
    
    def update_from_dict(self, updates: Dict[str, Any]):
        """Update configuration from dictionary"""
        for key, value in updates.items():
            if hasattr(self, key):
                # Type conversion based on current attribute type
                current_value = getattr(self, key)
                if isinstance(current_value, bool):
                    value = str(value).lower() == "true"
                elif isinstance(current_value, int):
                    value = int(value)
                elif isinstance(current_value, float):
                    value = float(value)
                
                setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            key: value for key, value in self.__dict__.items()
            if not key.startswith('_')
        }
