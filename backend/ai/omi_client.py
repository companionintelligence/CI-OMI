"""
Omi API Client for Omi Companion App
Handles communication with the Omi API for device management and data retrieval
"""
import asyncio
import logging
import json
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class OmiClient:
    """Client for communicating with Omi API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.omi.me"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Statistics
        self.stats = {
            "requests_made": 0,
            "successful_requests": 0,
            "errors": 0,
            "last_request": None,
            "average_response_time": 0.0
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def initialize(self):
        """Initialize the Omi client"""
        try:
            if self.session is None:
                timeout = aiohttp.ClientTimeout(total=30)
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "OmiCompanion/1.0.0"
                }
                self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
            
            # Test the connection
            await self.health_check()
            
            logger.info("✅ Omi API client initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing Omi API client: {e}")
    
    async def close(self):
        """Close the client session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def health_check(self) -> bool:
        """Check if the Omi API is accessible"""
        try:
            if self.session is None:
                await self.initialize()
            
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    logger.info("✅ Omi API health check passed")
                    return True
                else:
                    logger.warning(f"⚠️  Omi API health check failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Omi API health check error: {e}")
            return False
    
    async def get_devices(self) -> List[Dict[str, Any]]:
        """Get list of user's Omi devices"""
        try:
            if self.session is None:
                await self.initialize()
            
            start_time = datetime.now()
            self.stats["requests_made"] += 1
            
            async with self.session.get(f"{self.base_url}/v1/devices") as response:
                if response.status == 200:
                    data = await response.json()
                    devices = data.get("devices", [])
                    
                    # Update statistics
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    self._update_stats(response_time, True)
                    
                    logger.info(f"📱 Retrieved {len(devices)} devices from Omi API")
                    return devices
                else:
                    logger.error(f"❌ Failed to get devices: {response.status}")
                    self._update_stats(0, False)
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Error getting devices: {e}")
            self._update_stats(0, False)
            return []
    
    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific device"""
        try:
            if self.session is None:
                await self.initialize()
            
            start_time = datetime.now()
            self.stats["requests_made"] += 1
            
            async with self.session.get(f"{self.base_url}/v1/devices/{device_id}/status") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Update statistics
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    self._update_stats(response_time, True)
                    
                    logger.info(f"📊 Retrieved status for device {device_id}")
                    return data
                else:
                    logger.error(f"❌ Failed to get device status: {response.status}")
                    self._update_stats(0, False)
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error getting device status: {e}")
            self._update_stats(0, False)
            return None
    
    async def get_device_transcriptions(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent transcriptions from a device"""
        try:
            if self.session is None:
                await self.initialize()
            
            start_time = datetime.now()
            self.stats["requests_made"] += 1
            
            params = {"limit": limit}
            async with self.session.get(f"{self.base_url}/v1/devices/{device_id}/transcriptions", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    transcriptions = data.get("transcriptions", [])
                    
                    # Update statistics
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    self._update_stats(response_time, True)
                    
                    logger.info(f"💬 Retrieved {len(transcriptions)} transcriptions for device {device_id}")
                    return transcriptions
                else:
                    logger.error(f"❌ Failed to get transcriptions: {response.status}")
                    self._update_stats(0, False)
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Error getting transcriptions: {e}")
            self._update_stats(0, False)
            return []
    
    async def send_command(self, device_id: str, command: str, data: Dict[str, Any] = None) -> bool:
        """Send a command to a device"""
        try:
            if self.session is None:
                await self.initialize()
            
            start_time = datetime.now()
            self.stats["requests_made"] += 1
            
            payload = {
                "command": command,
                "data": data or {}
            }
            
            async with self.session.post(f"{self.base_url}/v1/devices/{device_id}/command", json=payload) as response:
                if response.status == 200:
                    # Update statistics
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    self._update_stats(response_time, True)
                    
                    logger.info(f"📤 Sent command '{command}' to device {device_id}")
                    return True
                else:
                    logger.error(f"❌ Failed to send command: {response.status}")
                    self._update_stats(0, False)
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error sending command: {e}")
            self._update_stats(0, False)
            return False
    
    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get current user information"""
        try:
            if self.session is None:
                await self.initialize()
            
            start_time = datetime.now()
            self.stats["requests_made"] += 1
            
            async with self.session.get(f"{self.base_url}/v1/user") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Update statistics
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    self._update_stats(response_time, True)
                    
                    logger.info("👤 Retrieved user information from Omi API")
                    return data
                else:
                    logger.error(f"❌ Failed to get user info: {response.status}")
                    self._update_stats(0, False)
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error getting user info: {e}")
            self._update_stats(0, False)
            return None
    
    def _update_stats(self, response_time: float, success: bool):
        """Update client statistics"""
        if success:
            self.stats["successful_requests"] += 1
            
            # Update average response time
            current_avg = self.stats["average_response_time"]
            total_successful = self.stats["successful_requests"]
            self.stats["average_response_time"] = (
                (current_avg * (total_successful - 1) + response_time) / total_successful
            )
        else:
            self.stats["errors"] += 1
        
        self.stats["last_request"] = datetime.now().isoformat()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            **self.stats,
            "api_key": self.api_key[:8] + "..." if self.api_key else None,
            "base_url": self.base_url
        }
