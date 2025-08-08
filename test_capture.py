#!/usr/bin/env python3
"""
Test script for audio and image capture functionality
"""
import asyncio
import requests
import json
import time

def test_capture_endpoints():
    """Test the capture endpoints"""
    base_url = "http://localhost:8000"
    
    print("🧪 Testing capture endpoints...")
    
    # Test audio capture
    print("\n1. Testing audio capture...")
    try:
        response = requests.post(f"{base_url}/api/capture/audio")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Audio capture: {data['message']}")
            if 'filepath' in data:
                print(f"   📁 Saved to: {data['filepath']}")
        else:
            print(f"❌ Audio capture failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error testing audio capture: {e}")
    
    # Test image capture
    print("\n2. Testing image capture...")
    try:
        response = requests.post(f"{base_url}/api/capture/image")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Image capture: {data['message']}")
        else:
            print(f"❌ Image capture failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error testing image capture: {e}")
    
    # List saved audio files
    print("\n3. Listing saved audio files...")
    try:
        response = requests.get(f"{base_url}/api/storage/audio")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {data['total']} audio files")
            for file in data['files'][:5]:  # Show first 5
                print(f"   📁 {file['filename']} ({file['size']} bytes)")
        else:
            print(f"❌ Failed to list audio files: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing audio files: {e}")
    
    # List saved image files
    print("\n4. Listing saved image files...")
    try:
        response = requests.get(f"{base_url}/api/storage/images")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {data['total']} image files")
            for file in data['files'][:5]:  # Show first 5
                print(f"   📁 {file['filename']} ({file['size']} bytes)")
        else:
            print(f"❌ Failed to list image files: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing image files: {e}")

if __name__ == "__main__":
    test_capture_endpoints()
