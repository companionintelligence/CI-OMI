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

# API authentication. The backend refuses every endpoint except /health until
# OMI_COMPANION_API_KEY is set, so a generated key has to be *persisted*, not just
# held in a shell variable that dies with this process.
#
# Three cases, in order of precedence:
#   1. Already in the environment - the operator is managing it, leave it alone.
#   2. Already in .env - leave it there for load_dotenv() to pick up, so this
#      script can never shadow the operator's value with a different one.
#   3. Neither - generate one, export it for this run, and write it to .env below.
api_key_was_generated=0
if [ -n "$OMI_COMPANION_API_KEY" ]; then
    export OMI_COMPANION_API_KEY
elif [ -f ".env" ] && grep -q '^[[:space:]]*OMI_COMPANION_API_KEY[[:space:]]*=' .env; then
    if ! grep -q '^[[:space:]]*OMI_COMPANION_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]' .env; then
        echo "⚠️  OMI_COMPANION_API_KEY in .env is empty - every endpoint except /health will return 503."
        echo "   Set it to a random secret, e.g. openssl rand -hex 32"
    fi
else
    OMI_COMPANION_API_KEY=$(openssl rand -hex 32 2>/dev/null \
        || python3 -c "import secrets; print(secrets.token_hex(32))")
    export OMI_COMPANION_API_KEY
    api_key_was_generated=1
fi

announce_generated_api_key() {
    echo ""
    echo "🔑 Generated a new OMI_COMPANION_API_KEY and wrote it to $(pwd)/.env"
    echo "   Clients must send it as the X-API-Key header on every request:"
    echo "     curl -H \"X-API-Key: \$OMI_COMPANION_API_KEY\" http://localhost:8000/api/status"
    echo ""
}

# A .env written before authentication existed has no key at all. Append the
# generated one rather than discarding it - otherwise the upgrade path ends in a
# service that 503s every endpoint with nothing in the file to explain why.
append_generated_api_key_to_env() {
    cat >> .env << EOF

# API Authentication (REQUIRED) - added automatically on upgrade.
# Clients must send this as the X-API-Key header. Rotate by editing this file
# and restarting the service.
OMI_COMPANION_API_KEY=$OMI_COMPANION_API_KEY
EOF
    announce_generated_api_key
}

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
    announce_generated_api_key
elif [ "$api_key_was_generated" = "1" ]; then
    append_generated_api_key_to_env
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
