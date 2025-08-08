"""
BLE Manager for Omi Device Communication
Handles connection, audio streaming, and device management
"""
import asyncio
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from bleak import BleakClient, BleakScanner, BLEDevice
from bleak.exc import BleakError

logger = logging.getLogger(__name__)

@dataclass
class BLECharacteristics:
    """Omi BLE characteristic UUIDs"""
    AUDIO_STREAM = "19B10001-E8F2-537E-4F6C-D104768A1214"
    CODEC_TYPE = "19B10002-E8F2-537E-4F6C-D104768A1214"
    CONTROL = "19B10003-E8F2-537E-4F6C-D104768A1214"
    STATUS = "19B10004-E8F2-537E-4F6C-D104768A1214"

class BLEManager:
    """Manages BLE connections to Omi devices"""
    
    def __init__(self):
        self.characteristics = BLECharacteristics()
        self.connected_clients: Dict[str, BleakClient] = {}
        self.audio_callbacks: Dict[str, Callable] = {}
        self.connection_status: Dict[str, bool] = {}
        self.device_info: Dict[str, Dict] = {}
        
    async def discover_devices(self, timeout: int = 10) -> List[BLEDevice]:
        """Discover nearby BLE devices"""
        try:
            logger.info(f"🔍 Scanning for BLE devices (timeout: {timeout}s)...")
            devices = await BleakScanner.discover(timeout=timeout)
            
            logger.info(f"📱 Found {len(devices)} total BLE devices:")
            for device in devices:
                if device.name:
                    logger.info(f"  📱 {device.name} ({device.address}) RSSI: {device.rssi}")
                else:
                    logger.info(f"  📱 Unknown device ({device.address}) RSSI: {device.rssi}")
            
            omi_devices = []
            for device in devices:
                if device.name and any(keyword in device.name.lower() 
                                     for keyword in ["omi", "devkit", "omi", "glass"]):
                    omi_devices.append(device)
                    logger.info(f"🎯 Found Omi device: {device.name} ({device.address}) RSSI: {device.rssi}")
            
            if not omi_devices:
                logger.info("❌ No Omi devices found. Make sure your device is:")
                logger.info("   - Powered on and in pairing mode")
                logger.info("   - Within range (within 10 meters)")
                logger.info("   - Advertising as 'Omi', 'DevKit', or similar")
                logger.info("   - Not already connected to another device")
            
            return omi_devices
            
        except Exception as e:
            logger.error(f"❌ Error during device discovery: {e}")
            return []
    
    async def connect_device(self, device: BLEDevice) -> bool:
        """Connect to an Omi device"""
        try:
            if device.address in self.connected_clients:
                logger.info(f"✅ Device {device.address} already connected")
                return True
            
            logger.info(f"🔗 Connecting to {device.name} ({device.address})...")
            
            client = BleakClient(device.address)
            await client.connect()
            
            if not client.is_connected:
                logger.error(f"❌ Failed to connect to {device.address}")
                return False
            
            self.connected_clients[device.address] = client
            self.connection_status[device.address] = True
            self.device_info[device.address] = {
                "name": device.name,
                "address": device.address,
                "rssi": device.rssi
            }
            
            # Setup characteristics and notifications
            await self._setup_device_characteristics(device.address)
            
            logger.info(f"✅ Successfully connected to {device.name}")
            return True
            
        except BleakError as e:
            logger.error(f"❌ BLE error connecting to {device.address}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to {device.address}: {e}")
            return False
    
    async def _setup_device_characteristics(self, device_address: str):
        """Setup device characteristics and notifications"""
        client = self.connected_clients.get(device_address)
        if not client:
            return
        
        try:
            # List all services and characteristics
            services = await client.get_services()
            logger.info(f"📋 Device {device_address} services:")
            
            available_characteristics = []
            for service in services:
                logger.info(f"  🔧 Service: {service.uuid}")
                for char in service.characteristics:
                    logger.info(f"    📡 Characteristic: {char.uuid} - {char.properties}")
                    available_characteristics.append(char.uuid)
            
            # Subscribe to audio stream if available
            if self.characteristics.AUDIO_STREAM in available_characteristics:
                try:
                    await client.start_notify(
                        self.characteristics.AUDIO_STREAM,
                        self._create_audio_handler(device_address)
                    )
                    logger.info(f"🎵 Subscribed to audio stream for {device_address}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not subscribe to audio stream: {e}")
            
            # Subscribe to status updates if available
            if self.characteristics.STATUS in available_characteristics:
                try:
                    await client.start_notify(
                        self.characteristics.STATUS,
                        self._create_status_handler(device_address)
                    )
                    logger.info(f"📊 Subscribed to status updates for {device_address}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not subscribe to status updates: {e}")
            
            # Read codec type if available
            if self.characteristics.CODEC_TYPE in available_characteristics:
                try:
                    codec_data = await client.read_gatt_char(self.characteristics.CODEC_TYPE)
                    codec_info = codec_data.decode('utf-8') if codec_data else "unknown"
                    logger.info(f"🎧 Codec type for {device_address}: {codec_info}")
                    self.device_info[device_address]["codec"] = codec_info
                except Exception as e:
                    logger.warning(f"⚠️  Could not read codec type: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error setting up characteristics for {device_address}: {e}")
    
    def _create_audio_handler(self, device_address: str):
        """Create audio notification handler for specific device"""
        def handler(sender: int, data: bytearray):
            if device_address in self.audio_callbacks:
                try:
                    callback = self.audio_callbacks[device_address]
                    asyncio.create_task(callback(bytes(data)))
                except Exception as e:
                    logger.error(f"❌ Error in audio callback for {device_address}: {e}")
        return handler
    
    def _create_status_handler(self, device_address: str):
        """Create status notification handler for specific device"""
        def handler(sender: int, data: bytearray):
            try:
                status_data = data.decode('utf-8')
                logger.info(f"📊 Status update from {device_address}: {status_data}")
                # Update device info
                if device_address in self.device_info:
                    self.device_info[device_address]["last_status"] = status_data
            except Exception as e:
                logger.error(f"❌ Error decoding status from {device_address}: {e}")
        return handler
    
    async def read_audio_data(self, device_address: str) -> Optional[bytes]:
        """Read audio data from device"""
        client = self.connected_clients.get(device_address)
        if not client or not client.is_connected:
            return None
        
        try:
            data = await client.read_gatt_char(self.characteristics.AUDIO_STREAM)
            return bytes(data) if data else None
        except Exception as e:
            logger.error(f"❌ Error reading audio data from {device_address}: {e}")
            return None
    
    async def send_control_command(self, device_address: str, command: bytes) -> bool:
        """Send control command to device"""
        client = self.connected_clients.get(device_address)
        if not client or not client.is_connected:
            logger.warning(f"⚠️  Device {device_address} not connected for control command")
            return False
        
        try:
            await client.write_gatt_char(self.characteristics.CONTROL, command)
            logger.info(f"📤 Sent control command to {device_address}")
            return True
        except Exception as e:
            logger.error(f"❌ Error sending control command to {device_address}: {e}")
            return False
    
    def set_audio_callback(self, device_address: str, callback: Callable):
        """Set audio data callback for device"""
        self.audio_callbacks[device_address] = callback
        logger.info(f"🔗 Audio callback set for {device_address}")
    
    async def disconnect_device(self, device_address: str) -> bool:
        """Disconnect from device"""
        client = self.connected_clients.get(device_address)
        if not client:
            return True
        
        try:
            if client.is_connected:
                await client.disconnect()
            
            # Clean up
            del self.connected_clients[device_address]
            self.connection_status[device_address] = False
            
            if device_address in self.audio_callbacks:
                del self.audio_callbacks[device_address]
            
            if device_address in self.device_info:
                del self.device_info[device_address]
            
            logger.info(f"🔌 Disconnected from {device_address}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error disconnecting from {device_address}: {e}")
            return False
    
    async def disconnect_all(self):
        """Disconnect from all devices"""
        logger.info("🔌 Disconnecting from all devices...")
        
        devices_to_disconnect = list(self.connected_clients.keys())
        for device_address in devices_to_disconnect:
            await self.disconnect_device(device_address)
        
        logger.info("✅ All devices disconnected")
    
    def get_connection_status(self, device_address: str) -> bool:
        """Get connection status for device"""
        client = self.connected_clients.get(device_address)
        return client.is_connected if client else False
    
    def get_connected_devices(self) -> List[str]:
        """Get list of connected device addresses"""
        return [addr for addr, client in self.connected_clients.items() 
                if client.is_connected]
    
    def get_device_info(self, device_address: str) -> Optional[Dict]:
        """Get device information"""
        return self.device_info.get(device_address)
    
    def get_all_device_info(self) -> Dict[str, Dict]:
        """Get all device information"""
        return self.device_info.copy()
    
    async def monitor_connections(self):
        """Monitor connection health"""
        while True:
            try:
                disconnected_devices = []
                for device_address, client in self.connected_clients.items():
                    if not client.is_connected:
                        logger.warning(f"⚠️  Device {device_address} disconnected")
                        disconnected_devices.append(device_address)
                
                # Clean up disconnected devices
                for device_address in disconnected_devices:
                    await self.disconnect_device(device_address)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in connection monitoring: {e}")
                await asyncio.sleep(5)
