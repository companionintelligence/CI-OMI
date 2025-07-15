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

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from ble.manager import BLEManager
from audio.processor import AudioProcessor
from vision.processor import VisionProcessor
from ai.ollama_client import OllamaClient
from utils.event_logger import EventLogger
from utils.config import SystemConfig

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
        
        @self.app.get("/api/status")
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
        
        @self.app.post("/api/start")
        async def start_system(background_tasks: BackgroundTasks):
            """Start the capture system"""
            if not self.system_running:
                background_tasks.add_task(self.start_capture_system)
                return {"status": "starting", "message": "System startup initiated"}
            return {"status": "already_running", "message": "System is already running"}
        
        @self.app.post("/api/stop")
        async def stop_system():
            """Stop the capture system"""
            if self.system_running:
                await self.stop_capture_system()
                return {"status": "stopped", "message": "System stopped successfully"}
            return {"status": "already_stopped", "message": "System is already stopped"}
        
        @self.app.get("/api/devices")
        async def get_devices():
            """Get connected device information"""
            return {"devices": self.connected_devices}
        
        @self.app.post("/api/events")
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
        
        @self.app.get("/api/events")
        async def get_events(limit: int = 100, offset: int = 0):
            """Retrieve event history"""
            try:
                events = await self.event_logger.get_events(limit, offset)
                total = await self.event_logger.get_event_count()
                return {"events": events, "total": total, "limit": limit, "offset": offset}
            except Exception as e:
                logger.error(f"Error retrieving events: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/config")
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
        
        @self.app.websocket("/ws/live")
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
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    
                    # Handle client messages
                    if data.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                        
            except Exception as e:
                logger.info(f"WebSocket disconnected: {e}")
            finally:
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
                logger.info(f"WebSocket removed. Total connections: {len(self.websocket_connections)}")
    
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
                    if device.name and "omi" in device.name.lower():
                        if device.address not in self.connected_devices:
                            logger.info(f"📱 Found Omi device: {device.name} ({device.address})")
                            await self.connect_device(device)
                
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
