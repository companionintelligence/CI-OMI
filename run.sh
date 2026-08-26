#!/bin/bash

# Omi Companion Capture App - Run Script
# This script activates the virtual environment and runs the application

set -e

echo "🚀 Starting Omi Companion Capture App..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup.sh first:"
    echo "   ./scripts/setup.sh"
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# Generate an API key if one was not supplied. The backend refuses every
# endpoint except /health until this is set, so a blank value would leave a
# fresh install unusable.
if [ -z "$OMI_COMPANION_API_KEY" ]; then
    OMI_COMPANION_API_KEY=$(openssl rand -hex 32 2>/dev/null \
        || python3 -c "import secrets; print(secrets.token_hex(32))")
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating default configuration..."
    cat > .env << EOF
# API Authentication (REQUIRED)
# Clients must send this as the X-API-Key header. Rotate by editing this file
# and restarting the service.
OMI_COMPANION_API_KEY=$OMI_COMPANION_API_KEY

# Ollama Configuration
OLLAMA_URL=http://localhost:11434
OLLAMA_VISION_MODEL=moondream:1.8b-v2-fp16
OLLAMA_CHAT_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=30

# BLE Configuration
BLE_DEVICE_NAME=Omi
BLE_SCAN_TIMEOUT=10
BLE_CONNECTION_TIMEOUT=10

# Audio Configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
WHISPER_MODEL=base

# Video Configuration
VIDEO_FPS=10
VIDEO_WIDTH=640
VIDEO_HEIGHT=480

# AI Feature Toggles
ENABLE_FACE_RECOGNITION=true
ENABLE_OBJECT_DETECTION=true
ENABLE_OCR=true
ENABLE_GESTURE_DETECTION=true
ENABLE_EMOTION_ANALYSIS=true

# Confidence Thresholds
CONFIDENCE_THRESHOLD=0.7
FACE_RECOGNITION_THRESHOLD=0.8
OBJECT_DETECTION_THRESHOLD=0.6

# Storage Configuration
DATABASE_PATH=data/events.db
JSON_BACKUP_PATH=data/events_backup.json
FACE_DB_PATH=data/face_embeddings.json

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
LOG_FILE=data/logs/omi_companion.log
EOF
fi

# Create data directories if they don't exist
mkdir -p data/{events,audio_samples,face_embeddings,logs}

# Check if Ollama is running
echo "🔍 Checking Ollama server..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama server is not running. Some AI features will be disabled."
    echo "   To start Ollama: ollama serve"
    echo "   To install Ollama: curl -fsSL https://ollama.ai/install.sh | sh"
fi

# Run the application
echo "🎯 Starting backend server..."
echo "   API will be available at: http://localhost:8000"
echo "   API docs: http://localhost:8000/docs"
echo "   Press Ctrl+C to stop"
echo ""

cd backend
python main.py
