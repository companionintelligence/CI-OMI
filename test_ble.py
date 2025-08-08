#!/usr/bin/env python3
"""
Simple BLE discovery test script
"""
import asyncio
import logging
from bleak import BleakScanner, BLEDevice

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ble_discovery():
    """Test BLE device discovery"""
    print("🔍 Testing BLE device discovery...")
    print("Make sure your Omi device is:")
    print("  - Powered on")
    print("  - In pairing mode (if required)")
    print("  - Within range (within 10 meters)")
    print("  - Not connected to another device")
    print()
    
    try:
        print("📱 Scanning for BLE devices (10 seconds)...")
        devices = await BleakScanner.discover(timeout=10)
        
        print(f"\n📊 Found {len(devices)} total BLE devices:")
        print("-" * 50)
        
        omi_devices = []
        for i, device in enumerate(devices, 1):
            name = device.name or "Unknown"
            print(f"{i:2d}. {name} ({device.address}) RSSI: {device.rssi}")
            
            # Check if it's an Omi device
            if device.name and any(keyword in device.name.lower() 
                                 for keyword in ["omi", "devkit", "glass"]):
                omi_devices.append(device)
                print(f"     🎯 This looks like an Omi device!")
        
        print("-" * 50)
        
        if omi_devices:
            print(f"🎉 Found {len(omi_devices)} Omi device(s):")
            for device in omi_devices:
                print(f"  - {device.name} ({device.address})")
        else:
            print("❌ No Omi devices found.")
            print("\n💡 Troubleshooting tips:")
            print("  1. Make sure your Omi device is powered on")
            print("  2. Check if it's in pairing mode")
            print("  3. Move closer to the device")
            print("  4. Check if Bluetooth is enabled on your system")
            print("  5. Try restarting the device")
            print("  6. Check if the device is already connected to another app")
        
    except Exception as e:
        print(f"❌ Error during BLE discovery: {e}")
        print("\n💡 This might be a permission issue. Try:")
        print("  1. Check if Bluetooth permissions are granted")
        print("  2. Restart the application")
        print("  3. Check system Bluetooth settings")

if __name__ == "__main__":
    asyncio.run(test_ble_discovery())
