"""
System Configuration for Omi Companion App
"""
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, Iterable, Set
import os
from dotenv import load_dotenv

load_dotenv()

# A configuration field whose name ends in one of these holds a credential and
# must never be serialised over the API. The rule is derived from the name rather
# than a hand-written list of fields so that a secret added later is redacted by
# default instead of leaking until somebody remembers to update the list.
SECRET_FIELD_SUFFIXES = ("_key", "_token", "_secret", "_password")

# Escape hatch for a secret whose name does not follow the convention. Declare it
# as `my_credential: str = secret_field(os.getenv("MY_CREDENTIAL", ""))`.
SECRET_FIELD_METADATA_FLAG = "secret"

# Suffix a redacted field carries in serialised output: `omi_api_key` is replaced
# by `omi_api_key_configured: true|false`. A status endpoint needs to know whether
# a credential is present, never what it is.
CONFIGURED_SUFFIX = "_configured"


def secret_field(default: Any = "", **kwargs: Any) -> Any:
    """Declare a dataclass field as holding a credential.

    Only needed when the field name does not end in one of
    `SECRET_FIELD_SUFFIXES`; names that do are detected automatically.
    """
    metadata = dict(kwargs.pop("metadata", {}))
    metadata[SECRET_FIELD_METADATA_FLAG] = True
    return field(default=default, metadata=metadata, **kwargs)


def is_secret_field_name(name: str) -> bool:
    """Whether a field name looks like a credential by naming convention"""
    return name.endswith(SECRET_FIELD_SUFFIXES)


def redact_secrets(
    values: Dict[str, Any], secret_names: Iterable[str]
) -> Dict[str, Any]:
    """Replace each named secret with a boolean "is it set" indicator.

    The key itself is dropped rather than blanked, so a caller cannot mistake a
    masked placeholder for the real value.
    """
    secret_names = set(secret_names)
    redacted: Dict[str, Any] = {}
    for key, value in values.items():
        if key in secret_names:
            redacted[f"{key}{CONFIGURED_SUFFIX}"] = bool(str(value).strip())
        else:
            redacted[key] = value
    return redacted


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
        """Convert configuration to dictionary, secrets included.

        For anything that leaves the process - an API response, a WebSocket
        broadcast, a log line - use `to_public_dict()` instead.
        """
        return {
            key: value for key, value in self.__dict__.items()
            if not key.startswith('_')
        }

    def secret_field_names(self) -> Set[str]:
        """Fields holding credentials, by naming convention or explicit marker"""
        return {
            f.name
            for f in fields(self)
            if f.metadata.get(SECRET_FIELD_METADATA_FLAG)
            or is_secret_field_name(f.name)
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """Serialise for API responses, with every credential redacted.

        `omi_api_key` and any future secret are replaced by a
        `<field>_configured` boolean. Without this, possession of the shared API
        key would hand a caller every other credential the appliance holds - over
        plain HTTP, from a status endpoint that only ever needed to say whether
        the upstream integration is set up.
        """
        return redact_secrets(asdict(self), self.secret_field_names())
