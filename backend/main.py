"""
Omi Companion Capture App - Main Backend Server
Multi-Modal AI System for omiGlass & DevKit 2
"""
import asyncio
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks, APIRouter, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from ble.manager import BLEManager
from audio.processor import AudioProcessor
from vision.processor import VisionProcessor
from ai.ollama_client import OllamaClient
from ai.omi_client import OmiClient
from utils.event_logger import EventLogger
from utils.config import SystemConfig
from utils import auth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OmiCompanionSystem:
    """Main system orchestrator"""
    
    def __init__(self):
        self.config = SystemConfig()
        self.app = FastAPI(title="Omi Companion API", version="1.0.0")
        self.setup_cors()
        self.setup_routes()
        
        # Initialize components
        self.ble_manager = BLEManager()
        self.audio_processor = AudioProcessor(self.config.audio_sample_rate)
        self.vision_processor = VisionProcessor()
        self.ollama_client = OllamaClient(self.config.ollama_url)
        self.omi_client = OmiClient(self.config.omi_api_key, self.config.omi_api_url) if self.config.omi_api_key else None
        self.event_logger = EventLogger()
        
        # System state
        self.connected_devices: Dict[str, dict] = {}
        self.active_sessions: Dict[str, str] = {}
        self.websocket_connections: List[WebSocket] = []
        self.system_running = False
        
    def setup_cors(self):
        """Configure CORS for frontend access"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_routes(self):
        """Setup API routes"""

        # Liveness only, deliberately unauthenticated so nginx and container
        # health checks can still reach the process. Exposes no configuration,
        # device or event data.
        public_router = APIRouter()

        # Everything that reads user data or mutates state sits behind the shared
        # API key. Declared once on the router rather than per-handler so a route
        # added later cannot accidentally ship unauthenticated.
        router = APIRouter(dependencies=[Security(auth.require_api_key)])

        # A WebSocket handshake cannot carry an HTTPException response, so it uses
        # the WebSocket flavour of the same check, which closes with 1008 instead.
        ws_router = APIRouter(dependencies=[Depends(auth.require_api_key_ws)])

        @public_router.get("/health")
        async def health_check():
            """Liveness probe for nginx and process supervisors"""
            return {"status": "ok"}

        @router.get("/api/status")
        async def get_status():
            """Get system status"""
            return {
                "status": "running" if self.system_running else "stopped",
                "timestamp": datetime.now().isoformat(),
                "connected_devices": len(self.connected_devices),
                "active_sessions": len(self.active_sessions),
                "ollama_available": await self.ollama_client.health_check(),
                "config": asdict(self.config)
            }
        
        @router.post("/api/start")
        async def start_system(background_tasks: BackgroundTasks):
            """Start the capture system"""
            if not self.system_running:
                background_tasks.add_task(self.start_capture_system)
                return {"status": "starting", "message": "System startup initiated"}
            return {"status": "already_running", "message": "System is already running"}
        
        @router.post("/api/stop")
        async def stop_system():
            """Stop the capture system"""
            if self.system_running:
                await self.stop_capture_system()
                return {"status": "stopped", "message": "System stopped successfully"}
            return {"status": "already_stopped", "message": "System is already stopped"}
        
        @router.get("/api/devices")
        async def get_devices():
            """Get connected device information"""
            devices = self.connected_devices.copy()
            
            # If Omi API is available, also fetch devices from there
            if self.omi_client:
                try:
                    omi_devices = await self.omi_client.get_devices()
                    for device in omi_devices:
                        device_id = device.get("id", device.get("device_id"))
                        if device_id:
                            devices[f"omi_{device_id}"] = {
                                "name": device.get("name", "Omi Device"),
                                "address": device_id,
                                "type": "omi_api",
                                "connected_at": device.get("last_seen"),
                                "status": device.get("status", "unknown"),
                                "source": "omi_api"
                            }
                except Exception as e:
                    logger.error(f"❌ Error fetching Omi API devices: {e}")
            
            return {"devices": devices}
        
        @router.post("/api/events")
        async def submit_event(event: dict):
            """Submit new event data"""
            try:
                # Add timestamp and ID if not present
                if "timestamp" not in event:
                    event["timestamp"] = datetime.now().isoformat()
                if "id" not in event:
                    event["id"] = str(uuid.uuid4())
                
                await self.event_logger.log_event(event)
                await self.broadcast_to_websockets({"type": "new_event", "data": event})
                return {"status": "success", "event_id": event["id"]}
            except Exception as e:
                logger.error(f"Error submitting event: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/events")
        async def get_events(limit: int = 100, offset: int = 0):
            """Retrieve event history"""
            try:
                events = await self.event_logger.get_events(limit, offset)
                total = await self.event_logger.get_event_count()
                return {"events": events, "total": total, "limit": limit, "offset": offset}
            except Exception as e:
                logger.error(f"Error retrieving events: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.put("/api/config")
        async def update_config(config_updates: dict):
            """Update system configuration"""
            try:
                for key, value in config_updates.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                
                await self.broadcast_to_websockets({
                    "type": "config_updated", 
                    "data": asdict(self.config)
                })
                return {"status": "success", "config": asdict(self.config)}
            except Exception as e:
                logger.error(f"Error updating config: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @ws_router.websocket("/ws/live")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket for real-time updates"""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            logger.info(f"WebSocket connected. Total connections: {len(self.websocket_connections)}")
            
            try:
                # Send initial status
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "data": {
                        "connected": True,
                        "system_running": self.system_running,
                        "devices": self.connected_devices
                    }
                }))
                
                while True:
                    # Keep connection alive
                    await asyncio.sleep(30)
                    
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
                logger.info(f"WebSocket disconnected. Total connections: {len(self.websocket_connections)}")
        
        # Omi API endpoints
        @router.get("/api/omi/devices")
        async def get_omi_devices():
            """Get devices from Omi API"""
            if not self.omi_client:
                raise HTTPException(status_code=400, detail="Omi API not configured")
            
            try:
                devices = await self.omi_client.get_devices()
                return {"devices": devices}
            except Exception as e:
                logger.error(f"Error getting Omi devices: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/omi/devices/{device_id}/status")
        async def get_omi_device_status(device_id: str):
            """Get status of a specific Omi device"""
            if not self.omi_client:
                raise HTTPException(status_code=400, detail="Omi API not configured")
            
            try:
                status = await self.omi_client.get_device_status(device_id)
                if status:
                    return status
                else:
                    raise HTTPException(status_code=404, detail="Device not found")
            except Exception as e:
                logger.error(f"Error getting device status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/omi/devices/{device_id}/transcriptions")
        async def get_omi_device_transcriptions(device_id: str, limit: int = 50):
            """Get transcriptions from a specific Omi device"""
            if not self.omi_client:
                raise HTTPException(status_code=400, detail="Omi API not configured")
            
            try:
                transcriptions = await self.omi_client.get_device_transcriptions(device_id, limit)
                return {"transcriptions": transcriptions}
            except Exception as e:
                logger.error(f"Error getting transcriptions: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/api/omi/devices/{device_id}/command")
        async def send_omi_command(device_id: str, command_data: dict):
            """Send a command to a specific Omi device"""
            if not self.omi_client:
                raise HTTPException(status_code=400, detail="Omi API not configured")
            
            try:
                command = command_data.get("command")
                data = command_data.get("data", {})
                
                if not command:
                    raise HTTPException(status_code=400, detail="Command is required")
                
                success = await self.omi_client.send_command(device_id, command, data)
                if success:
                    return {"status": "success", "message": f"Command '{command}' sent successfully"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to send command")
            except Exception as e:
                logger.error(f"Error sending command: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/omi/user")
        async def get_omi_user_info():
            """Get current user information from Omi API"""
            if not self.omi_client:
                raise HTTPException(status_code=400, detail="Omi API not configured")
            
            try:
                user_info = await self.omi_client.get_user_info()
                if user_info:
                    return user_info
                else:
                    raise HTTPException(status_code=404, detail="User not found")
            except Exception as e:
                logger.error(f"Error getting user info: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Capture and storage endpoints
        @router.post("/api/capture/audio")
        async def capture_audio():
            """Manually trigger audio capture"""
            try:
                # Get current audio buffer if available
                if len(self.audio_processor.audio_buffer) > 0:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"manual_audio_{timestamp}.wav"
                    filepath = await self.audio_processor.save_audio_sample(
                        self.audio_processor.audio_buffer, filename
                    )
                    
                    if filepath:
                        return {
                            "status": "success",
                            "message": "Audio captured successfully",
                            "filepath": filepath,
                            "duration": len(self.audio_processor.audio_buffer) / self.config.audio_sample_rate
                        }
                    else:
                        raise HTTPException(status_code=500, detail="Failed to save audio")
                else:
                    raise HTTPException(status_code=400, detail="No audio data available")
                    
            except Exception as e:
                logger.error(f"Error capturing audio: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/api/capture/image")
        async def capture_image():
            """Manually trigger image capture"""
            try:
                # This would need to be implemented based on your camera setup
                # For now, we'll return a placeholder
                return {
                    "status": "success",
                    "message": "Image capture endpoint ready",
                    "note": "Camera integration needed for actual capture"
                }
            except Exception as e:
                logger.error(f"Error capturing image: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/storage/audio")
        async def list_audio_files(limit: int = 50):
            """List saved audio files"""
            try:
                import os
                audio_dir = "data/audio_samples"
                if not os.path.exists(audio_dir):
                    return {"files": [], "total": 0}
                
                files = []
                for filename in os.listdir(audio_dir):
                    if filename.endswith(('.wav', '.mp3', '.flac')):
                        filepath = os.path.join(audio_dir, filename)
                        stat = os.stat(filepath)
                        files.append({
                            "filename": filename,
                            "filepath": filepath,
                            "size": stat.st_size,
                            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                
                # Sort by creation time (newest first)
                files.sort(key=lambda x: x["created"], reverse=True)
                
                return {
                    "files": files[:limit],
                    "total": len(files)
                }
            except Exception as e:
                logger.error(f"Error listing audio files: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/storage/images")
        async def list_image_files(limit: int = 50):
            """List saved image files"""
            try:
                import os
                image_dir = "data/images"
                if not os.path.exists(image_dir):
                    return {"files": [], "total": 0}
                
                files = []
                for filename in os.listdir(image_dir):
                    if filename.endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        filepath = os.path.join(image_dir, filename)
                        stat = os.stat(filepath)
                        files.append({
                            "filename": filename,
                            "filepath": filepath,
                            "size": stat.st_size,
                            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                
                # Sort by creation time (newest first)
                files.sort(key=lambda x: x["created"], reverse=True)
                
                return {
                    "files": files[:limit],
                    "total": len(files)
                }
            except Exception as e:
                logger.error(f"Error listing image files: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.delete("/api/storage/audio/{filename}")
        async def delete_audio_file(filename: str):
            """Delete a specific audio file"""
            try:
                import os
                filepath = f"data/audio_samples/{filename}"
                if os.path.exists(filepath):
                    os.remove(filepath)
                    return {"status": "success", "message": f"Deleted {filename}"}
                else:
                    raise HTTPException(status_code=404, detail="File not found")
            except Exception as e:
                logger.error(f"Error deleting audio file: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.delete("/api/storage/images/{filename}")
        async def delete_image_file(filename: str):
            """Delete a specific image file"""
            try:
                import os
                filepath = f"data/images/{filename}"
                if os.path.exists(filepath):
                    os.remove(filepath)
                    return {"status": "success", "message": f"Deleted {filename}"}
                else:
                    raise HTTPException(status_code=404, detail="File not found")
            except Exception as e:
                logger.error(f"Error deleting image file: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Streaming and Webhook endpoints
        @router.get("/api/stream/audio/{device_id}")
        async def stream_audio(device_id: str):
            """Stream real-time audio from a specific device"""
            try:
                if device_id not in self.connected_devices:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Return current audio buffer or streaming endpoint
                device_info = self.connected_devices[device_id]
                return {
                    "device_id": device_id,
                    "status": "streaming",
                    "audio_format": "wav",
                    "sample_rate": self.config.audio_sample_rate,
                    "channels": self.config.audio_channels,
                    "stream_url": f"/api/stream/audio/{device_id}/live"
                }
            except Exception as e:
                logger.error(f"Error setting up audio stream: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/stream/audio/{device_id}/live")
        async def stream_audio_live(device_id: str):
            """Live audio streaming endpoint"""
            try:
                if device_id not in self.connected_devices:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # This would be implemented as a streaming response
                # For now, return the current audio buffer
                audio_buffer = self.audio_processor.audio_buffer
                if len(audio_buffer) > 0:
                    return {
                        "device_id": device_id,
                        "audio_data": audio_buffer.tolist(),
                        "timestamp": datetime.now().isoformat(),
                        "duration": len(audio_buffer) / self.config.audio_sample_rate
                    }
                else:
                    return {
                        "device_id": device_id,
                        "audio_data": [],
                        "timestamp": datetime.now().isoformat(),
                        "duration": 0
                    }
            except Exception as e:
                logger.error(f"Error streaming audio: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/stream/transcript/{device_id}")
        async def stream_transcript(device_id: str):
            """Stream real-time transcriptions from a specific device"""
            try:
                if device_id not in self.connected_devices:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Get recent transcriptions for this device
                recent_transcripts = []
                # This would be implemented to get actual transcriptions
                # For now, return placeholder
                
                return {
                    "device_id": device_id,
                    "status": "streaming",
                    "transcripts": recent_transcripts,
                    "stream_url": f"/api/stream/transcript/{device_id}/live"
                }
            except Exception as e:
                logger.error(f"Error setting up transcript stream: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/stream/transcript/{device_id}/live")
        async def stream_transcript_live(device_id: str):
            """Live transcript streaming endpoint"""
            try:
                if device_id not in self.connected_devices:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # This would be implemented as a streaming response
                # For now, return recent transcriptions
                return {
                    "device_id": device_id,
                    "transcript": "Live transcript would appear here",
                    "timestamp": datetime.now().isoformat(),
                    "confidence": 0.95
                }
            except Exception as e:
                logger.error(f"Error streaming transcript: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/api/webhooks/conversation")
        async def conversation_webhook(conversation_data: dict):
            """Webhook endpoint for conversation events"""
            try:
                # Log the conversation event
                event_id = str(uuid.uuid4())
                event = {
                    "id": event_id,
                    "timestamp": datetime.now().isoformat(),
                    "device_id": conversation_data.get("device_id", "unknown"),
                    "source": "webhook",
                    "event_type": "conversation",
                    "data": {
                        "event_id": event_id,
                        "conversation_data": conversation_data,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                await self.event_logger.log_event(event)
                
                # Broadcast to WebSocket clients
                await self.broadcast_to_websockets({
                    "type": "conversation_event",
                    "event_id": event_id,
                    "data": conversation_data,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {
                    "status": "success",
                    "event_id": event_id,
                    "message": "Conversation event logged successfully"
                }
            except Exception as e:
                logger.error(f"Error processing conversation webhook: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/api/webhooks/audio")
        async def audio_webhook(audio_data: dict):
            """Webhook endpoint for real-time audio bytes"""
            try:
                # Process incoming audio data
                device_id = audio_data.get("device_id")
                audio_bytes = audio_data.get("audio_bytes")
                
                if not device_id or not audio_bytes:
                    raise HTTPException(status_code=400, detail="Missing device_id or audio_bytes")
                
                # Convert audio bytes to numpy array and process
                import numpy as np
                audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
                
                # Save audio sample
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"webhook_audio_{device_id}_{timestamp}.wav"
                filepath = await self.audio_processor.save_audio_sample(audio_array, filename)
                
                # Log the audio event
                event_id = str(uuid.uuid4())
                event = {
                    "id": event_id,
                    "timestamp": datetime.now().isoformat(),
                    "device_id": device_id,
                    "source": "webhook",
                    "event_type": "audio_webhook",
                    "data": {
                        "event_id": event_id,
                        "filepath": filepath,
                        "audio_length": len(audio_array),
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                await self.event_logger.log_event(event)
                
                # Broadcast to WebSocket clients
                await self.broadcast_to_websockets({
                    "type": "audio_webhook",
                    "event_id": event_id,
                    "device_id": device_id,
                    "filepath": filepath,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {
                    "status": "success",
                    "event_id": event_id,
                    "filepath": filepath,
                    "message": "Audio webhook processed successfully"
                }
            except Exception as e:
                logger.error(f"Error processing audio webhook: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/api/webhooks/transcript")
        async def transcript_webhook(transcript_data: dict):
            """Webhook endpoint for real-time transcriptions"""
            try:
                # Process incoming transcript data
                device_id = transcript_data.get("device_id")
                transcript_text = transcript_data.get("transcript")
                confidence = transcript_data.get("confidence", 0.0)
                
                if not device_id or not transcript_text:
                    raise HTTPException(status_code=400, detail="Missing device_id or transcript")
                
                # Log the transcript event
                event_id = str(uuid.uuid4())
                event = {
                    "id": event_id,
                    "timestamp": datetime.now().isoformat(),
                    "device_id": device_id,
                    "source": "webhook",
                    "event_type": "transcript_webhook",
                    "data": {
                        "event_id": event_id,
                        "transcript": transcript_text,
                        "confidence": confidence,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                await self.event_logger.log_event(event)
                
                # Broadcast to WebSocket clients
                await self.broadcast_to_websockets({
                    "type": "transcript_webhook",
                    "event_id": event_id,
                    "device_id": device_id,
                    "transcript": transcript_text,
                    "confidence": confidence,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {
                    "status": "success",
                    "event_id": event_id,
                    "message": "Transcript webhook processed successfully"
                }
            except Exception as e:
                logger.error(f"Error processing transcript webhook: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/events/conversations")
        async def get_conversation_events(limit: int = 50, offset: int = 0):
            """Get conversation events"""
            try:
                events = await self.event_logger.get_events_by_type("conversation", limit, offset)
                return {
                    "events": events,
                    "total": len(events),
                    "limit": limit,
                    "offset": offset
                }
            except Exception as e:
                logger.error(f"Error getting conversation events: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/events/audio")
        async def get_audio_events(limit: int = 50, offset: int = 0):
            """Get audio events"""
            try:
                events = await self.event_logger.get_events_by_type("audio_webhook", limit, offset)
                return {
                    "events": events,
                    "total": len(events),
                    "limit": limit,
                    "offset": offset
                }
            except Exception as e:
                logger.error(f"Error getting audio events: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/api/events/transcripts")
        async def get_transcript_events(limit: int = 50, offset: int = 0):
            """Get transcript events"""
            try:
                events = await self.event_logger.get_events_by_type("transcript_webhook", limit, offset)
                return {
                    "events": events,
                    "total": len(events),
                    "limit": limit,
                    "offset": offset
                }
            except Exception as e:
                logger.error(f"Error getting transcript events: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        self.app.include_router(public_router)
        self.app.include_router(router)
        self.app.include_router(ws_router)

    async def broadcast_to_websockets(self, message: dict):
        """Broadcast message to all connected WebSocket clients"""
        if self.websocket_connections:
            disconnected = []
            for websocket in self.websocket_connections:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception:
                    disconnected.append(websocket)
            
            # Remove disconnected clients
            for ws in disconnected:
                if ws in self.websocket_connections:
                    self.websocket_connections.remove(ws)
    
    async def start_capture_system(self):
        """Start the complete capture system"""
        logger.info("🚀 Starting Omi Companion System...")
        self.system_running = True
        
        try:
            # Initialize Ollama connection
            ollama_available = await self.ollama_client.health_check()
            if not ollama_available:
                logger.warning("⚠️  Ollama server not available. Some AI features will be disabled.")
            else:
                logger.info("✅ Ollama server connected successfully")
            
            # Initialize event logger
            await self.event_logger.initialize()
            logger.info("✅ Event logger initialized")
            
            # Start BLE discovery
            asyncio.create_task(self.ble_discovery_loop())
            logger.info("✅ BLE discovery started")
            
            # Start processing loops
            asyncio.create_task(self.audio_processing_loop())
            asyncio.create_task(self.vision_processing_loop())
            logger.info("✅ Processing loops started")
            
            await self.broadcast_to_websockets({
                "type": "system_started",
                "data": {"timestamp": datetime.now().isoformat()}
            })
            
            logger.info("🎉 System started successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error starting system: {e}")
            self.system_running = False
            raise
    
    async def stop_capture_system(self):
        """Stop the capture system"""
        logger.info("🛑 Stopping Omi Companion System...")
        self.system_running = False
        
        # Disconnect all devices
        await self.ble_manager.disconnect_all()
        
        # Clear state
        self.connected_devices.clear()
        self.active_sessions.clear()
        
        await self.broadcast_to_websockets({
            "type": "system_stopped",
            "data": {"timestamp": datetime.now().isoformat()}
        })
        
        logger.info("✅ System stopped successfully")
    
    async def ble_discovery_loop(self):
        """Continuous BLE device discovery and management"""
        logger.info("🔍 Starting BLE discovery loop...")
        
        while self.system_running:
            try:
                devices = await self.ble_manager.discover_devices()
                for device in devices:
                    # Check if device name contains any Omi-related keywords
                    if device.name and any(keyword in device.name.lower() 
                                         for keyword in ["omi", "devkit", "glass"]):
                        if device.address not in self.connected_devices:
                            logger.info(f"🎯 Found Omi device: {device.name} ({device.address})")
                            await self.connect_device(device)
                        else:
                            logger.debug(f"📱 Device {device.name} already connected")
                
                await asyncio.sleep(10)  # Scan every 10 seconds
            except Exception as e:
                logger.error(f"❌ Error in BLE discovery: {e}")
                await asyncio.sleep(5)
    
    async def connect_device(self, device):
        """Connect to an Omi device"""
        try:
            success = await self.ble_manager.connect_device(device)
            if success:
                device_info = {
                    "name": device.name,
                    "address": device.address,
                    "type": "devkit2" if "devkit" in device.name.lower() else "glass",
                    "connected_at": datetime.now().isoformat(),
                    "status": "connected"
                }
                
                self.connected_devices[device.address] = device_info
                
                # Create session ID
                session_id = str(uuid.uuid4())
                self.active_sessions[device.address] = session_id
                
                # Start audio streaming if it's a DevKit 2
                if "devkit" in device.name.lower():
                    asyncio.create_task(self.audio_stream_handler(device.address))
                
                await self.broadcast_to_websockets({
                    "type": "device_connected",
                    "data": device_info
                })
                
                logger.info(f"✅ Connected to {device.name}")
                
        except Exception as e:
            logger.error(f"❌ Error connecting to device {device.address}: {e}")
    
    async def audio_stream_handler(self, device_address: str):
        """Handle audio streaming from DevKit 2"""
        logger.info(f"🎵 Starting audio stream handler for {device_address}")
        
        while device_address in self.connected_devices and self.system_running:
            try:
                audio_data = await self.ble_manager.read_audio_data(device_address)
                if audio_data:
                    # Process audio through pipeline
                    processed_audio = await self.audio_processor.process_opus_stream(audio_data)
                    if processed_audio:
                        # Send to Whisper for transcription
                        transcription = await self.audio_processor.transcribe_audio(processed_audio)
                        if transcription and transcription.strip():
                            await self.handle_transcription(transcription, device_address)
                
                await asyncio.sleep(0.1)  # 100ms processing interval
            except Exception as e:
                logger.error(f"❌ Error in audio stream handler: {e}")
                break
        
        logger.info(f"🎵 Audio stream handler stopped for {device_address}")
    
    async def handle_transcription(self, transcription: str, device_address: str):
        """Handle speech transcription results"""
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "device_id": device_address,
            "source": "microphone",
            "event_type": "speech_transcribed",
            "data": {
                "transcription": transcription,
                "confidence": 0.9,  # Add confidence from Whisper
                "language": "en",  # Add language detection
                "word_count": len(transcription.split())
            },
            "session_id": self.active_sessions.get(device_address, "")
        }
        
        # Send to Ollama for context analysis if available
        if await self.ollama_client.health_check():
            context = await self.ollama_client.analyze_speech(transcription)
            if context:
                event["data"]["context"] = context
        
        await self.event_logger.log_event(event)
        await self.broadcast_to_websockets({"type": "transcription", "data": event})
        
        logger.info(f"💬 Transcription: {transcription[:50]}...")
    
    async def audio_processing_loop(self):
        """Main audio processing loop"""
        logger.info("🎵 Audio processing loop started")
        
        while self.system_running:
            try:
                # Process any queued audio data
                await self.audio_processor.process_queue()
                await asyncio.sleep(0.05)  # 50ms processing interval
            except Exception as e:
                logger.error(f"❌ Error in audio processing loop: {e}")
                await asyncio.sleep(1)
    
    async def vision_processing_loop(self):
        """Main vision processing loop"""
        logger.info("👁️  Vision processing loop started")
        
        while self.system_running:
            try:
                # Process vision data when available
                if self.config.enable_object_detection or self.config.enable_face_recognition:
                    await self.vision_processor.process_frame_queue()
                await asyncio.sleep(0.1)  # 100ms processing interval
            except Exception as e:
                logger.error(f"❌ Error in vision processing loop: {e}")
                await asyncio.sleep(1)

def create_app():
    """Create and configure the FastAPI application"""
    system = OmiCompanionSystem()
    
    # Setup startup event
    @system.app.on_event("startup")
    async def startup_event():
        logger.info("🚀 Application starting up...")
        auth.log_configuration_state()
    
    @system.app.on_event("shutdown")
    async def shutdown_event():
        logger.info("🛑 Application shutting down...")
        if system.system_running:
            await system.stop_capture_system()
    
    return system.app

def main():
    """Main entry point"""
    app = create_app()
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )

if __name__ == "__main__":
    main()
